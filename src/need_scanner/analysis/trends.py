"""Trend analysis - detect emerging topics via week-over-week growth and LLM market trend assessment."""

import time
from typing import Dict, List, Optional
from collections import defaultdict
from pathlib import Path
import json
import numpy as np
from loguru import logger
from openai import OpenAI


def sigmoid(x: float) -> float:
    """Sigmoid function to normalize trend scores to 0-1 range."""
    return 1 / (1 + np.exp(-x))


def calculate_cluster_trends(
    cluster_data: Dict[int, List[dict]],
    history_path: Optional[Path] = None,
    weeks_lookback: int = 4
) -> Dict[int, float]:
    """
    Calculate trend scores for clusters based on week-over-week growth.

    Compares current week's cluster sizes with historical data.

    Args:
        cluster_data: Dict mapping cluster_id to list of post metadata
        history_path: Path to historical cluster data (optional)
        weeks_lookback: Number of weeks to look back for comparison

    Returns:
        Dict mapping cluster_id to trend_score (0.0 to 10.0)
    """
    logger.info("Calculating cluster trends...")

    # Current week cluster sizes
    current_sizes = {
        cluster_id: len(posts)
        for cluster_id, posts in cluster_data.items()
    }

    # Load historical data if available
    historical_sizes = defaultdict(lambda: defaultdict(int))

    if history_path and history_path.exists():
        try:
            with open(history_path, 'r') as f:
                historical_sizes = json.load(f)
            logger.info(f"Loaded historical trend data from {history_path}")
        except Exception as e:
            logger.warning(f"Failed to load historical data: {e}")

    # Calculate trends
    trend_scores = {}

    for cluster_id, current_count in current_sizes.items():
        # Get previous week's count (or average of last N weeks)
        prev_counts = []
        for week_offset in range(1, weeks_lookback + 1):
            week_key = f"week_minus_{week_offset}"
            if week_key in historical_sizes:
                prev_counts.append(historical_sizes[week_key].get(str(cluster_id), 0))

        if not prev_counts:
            # No historical data - assign neutral score
            trend_scores[cluster_id] = 5.0
            continue

        prev_avg = sum(prev_counts) / len(prev_counts) if prev_counts else 1

        # Calculate growth rate
        if prev_avg == 0:
            # New cluster - high trend score
            growth_rate = 2.0
        else:
            growth_rate = (current_count - prev_avg) / prev_avg

        # Normalize with sigmoid
        normalized_growth = sigmoid(growth_rate * 2)  # Scale for sensitivity

        # Scale to 0-10
        trend_score = normalized_growth * 10.0

        trend_scores[cluster_id] = round(trend_score, 1)

    logger.info(f"Calculated trends for {len(trend_scores)} clusters")

    # Show top trending clusters
    sorted_trends = sorted(trend_scores.items(), key=lambda x: x[1], reverse=True)
    logger.info("Top 5 trending clusters:")
    for cluster_id, score in sorted_trends[:5]:
        size = current_sizes.get(cluster_id, 0)
        logger.info(f"  Cluster {cluster_id}: trend={score:.1f}, size={size}")

    return trend_scores


def save_trend_history(
    cluster_data: Dict[int, List[dict]],
    output_path: Path,
    max_weeks: int = 12
) -> None:
    """
    Save current cluster sizes to trend history.

    Maintains a rolling window of cluster sizes for trend analysis.

    Args:
        cluster_data: Dict mapping cluster_id to list of post metadata
        output_path: Path to save history JSON
        max_weeks: Maximum number of weeks to keep in history
    """
    # Load existing history
    history = defaultdict(lambda: defaultdict(int))

    if output_path.exists():
        try:
            with open(output_path, 'r') as f:
                history = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load existing history: {e}")

    # Shift existing weeks
    for week_offset in range(max_weeks - 1, 0, -1):
        old_key = f"week_minus_{week_offset - 1}"
        new_key = f"week_minus_{week_offset}"
        if old_key in history:
            history[new_key] = history[old_key]

    # Save current week as week_minus_0
    current_sizes = {
        str(cluster_id): len(posts)
        for cluster_id, posts in cluster_data.items()
    }
    history["week_minus_0"] = current_sizes

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(history, f, indent=2)

    logger.info(f"Saved trend history to {output_path}")


def calculate_post_recency_score(
    posts: List[dict],
    max_age_days: int = 7
) -> float:
    """
    Calculate recency score based on post timestamps.

    More recent posts get higher scores.

    Args:
        posts: List of post metadata dicts with 'created_ts' field
        max_age_days: Maximum age in days for full score

    Returns:
        Recency score (0.0 to 10.0)
    """
    if not posts:
        return 0.0

    current_time = time.time()
    max_age_seconds = max_age_days * 86400

    recency_scores = []

    for post in posts:
        ts = post.get('created_ts')
        if not ts:
            continue

        age_seconds = current_time - ts
        if age_seconds < 0:
            age_seconds = 0

        # Normalize to 0-1 (newer = higher score)
        normalized = max(0, 1 - (age_seconds / max_age_seconds))
        recency_scores.append(normalized)

    if not recency_scores:
        return 5.0  # Neutral if no timestamps

    avg_recency = sum(recency_scores) / len(recency_scores)
    return round(avg_recency * 10.0, 1)


def calculate_llm_trend_score(
    cluster_title: str,
    cluster_problem: str,
    cluster_sector: Optional[str],
    model: str,
    api_key: str,
    max_retries: int = 2
) -> Optional[float]:
    """
    Calculate trend score using LLM to assess market momentum.

    Evaluates if the problem/need is growing in the market based on:
    - Emergence of new tools/solutions in this space
    - Technology evolution (AI, automation, etc.)
    - Market shifts (remote work, privacy concerns, etc.)
    - Social/media buzz

    Args:
        cluster_title: Short title of the problem
        cluster_problem: Problem description
        cluster_sector: Sector classification (optional)
        model: LLM model name (recommend gpt-4o-mini for cost)
        api_key: OpenAI API key
        max_retries: Maximum retry attempts

    Returns:
        Trend score (1.0 to 10.0) or None if failed
    """
    system_prompt = """Tu es un analyste de tendances marché qui évalue la dynamique de croissance des besoins utilisateurs.
Réponds uniquement en JSON strict avec un score de tendance."""

    user_prompt = f"""Évalue la TENDANCE MARCHÉ de ce problème utilisateur :

Titre : {cluster_title}
Problème : {cluster_problem}
Secteur : {cluster_sector or 'Non spécifié'}

Score de tendance (1-10) basé sur :
- **Émergence** : De nouveaux outils/solutions apparaissent dans cet espace ?
- **Tech evolution** : Technologies facilitantes (AI, automation, no-code) rendent la solution plus accessible ?
- **Market shifts** : Changements macro (remote work, privacy, coûts) augmentent le besoin ?
- **Buzz** : Le sujet génère de l'attention médias/réseaux sociaux ?

Échelle DISCRIMINANTE (utilise TOUTE l'échelle 1-10) :
- 1-3 : Tendance décroissante, marché saturé ou en déclin
- 4-6 : Stable, croissance modérée ou incertaine
- 7-8 : Croissance nette, momentum visible
- 9-10 : Forte croissance / hype (RARE - réserve pour vrais phénomènes émergents)

Sois EXIGEANT : la plupart des problèmes sont entre 4-7. Seuls les vrais sujets émergents méritent 8+.

Réponds UNIQUEMENT en JSON strict :
{{"trend_score": 6, "justification": "Une phrase expliquant le score"}}"""

    client = OpenAI(api_key=api_key)

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )

            response_text = response.choices[0].message.content

            # Parse JSON
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract from markdown
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    json_str = response_text[start:end].strip()
                    data = json.loads(json_str)
                elif "```" in response_text:
                    start = response_text.find("```") + 3
                    end = response_text.find("```", start)
                    json_str = response_text[start:end].strip()
                    data = json.loads(json_str)
                else:
                    raise

            if "trend_score" not in data:
                logger.warning(f"Missing trend_score in LLM response")
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return None

            trend_score = float(data["trend_score"])
            justification = data.get("justification", "")

            # Clamp to 1-10
            trend_score = max(1.0, min(10.0, trend_score))

            logger.debug(f"LLM Trend: {trend_score:.1f} - {justification}")
            return trend_score

        except Exception as e:
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.warning(f"LLM trend scoring error (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to calculate LLM trend score after {max_retries + 1} attempts: {e}")
                return None

    return None


def calculate_hybrid_trend_score(
    cluster_data: Dict[int, List[dict]],
    cluster_summaries: Dict[int, dict],
    history_path: Optional[Path] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    use_llm: bool = True,
    llm_weight: float = 0.7
) -> Dict[int, float]:
    """
    Calculate hybrid trend scores combining historical growth + LLM market assessment.

    Args:
        cluster_data: Dict mapping cluster_id to list of post metadata
        cluster_summaries: Dict mapping cluster_id to summary dict (title, problem, sector)
        history_path: Path to historical cluster data (optional)
        model: LLM model for trend assessment (optional, needed if use_llm=True)
        api_key: OpenAI API key (optional, needed if use_llm=True)
        use_llm: Whether to use LLM scoring (default True)
        llm_weight: Weight for LLM score vs historical (default 0.7)

    Returns:
        Dict mapping cluster_id to hybrid trend_score (1.0 to 10.0)
    """
    logger.info("Calculating hybrid trend scores...")

    # Calculate historical growth scores
    historical_scores = calculate_cluster_trends(
        cluster_data=cluster_data,
        history_path=history_path,
        weeks_lookback=4
    )

    # If LLM not enabled, return historical only
    if not use_llm or not model or not api_key:
        logger.info("Using historical trend scores only (LLM disabled)")
        return historical_scores

    # Calculate LLM market trend scores
    logger.info("Calculating LLM market trend scores...")
    hybrid_scores = {}

    for cluster_id in cluster_data.keys():
        historical_score = historical_scores.get(cluster_id, 5.0)

        # Get cluster summary info
        summary = cluster_summaries.get(cluster_id)
        if not summary:
            logger.warning(f"Cluster {cluster_id}: No summary found, using historical score only")
            hybrid_scores[cluster_id] = historical_score
            continue

        # Calculate LLM trend
        llm_score = calculate_llm_trend_score(
            cluster_title=summary.get("title", ""),
            cluster_problem=summary.get("problem", summary.get("description", "")),
            cluster_sector=summary.get("sector"),
            model=model,
            api_key=api_key
        )

        if llm_score is None:
            logger.warning(f"Cluster {cluster_id}: LLM scoring failed, using historical score only")
            hybrid_scores[cluster_id] = historical_score
        else:
            # Combine scores
            # Historical is 0-10, normalize to 1-10 first
            normalized_historical = max(1.0, historical_score)
            combined = llm_weight * llm_score + (1 - llm_weight) * normalized_historical
            hybrid_scores[cluster_id] = round(combined, 1)

            logger.info(
                f"Cluster {cluster_id}: Trend={hybrid_scores[cluster_id]:.1f} "
                f"(LLM={llm_score:.1f} @ {llm_weight*100:.0f}%, hist={normalized_historical:.1f})"
            )

        # Small delay to avoid rate limits
        time.sleep(0.3)

    logger.info(f"Calculated hybrid trends for {len(hybrid_scores)} clusters")

    # Show top trending
    sorted_trends = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)
    logger.info("Top 5 trending clusters (hybrid):")
    for cluster_id, score in sorted_trends[:5]:
        summary = cluster_summaries.get(cluster_id, {})
        title = summary.get("title", f"Cluster {cluster_id}")
        logger.info(f"  {title}: {score:.1f}")

    return hybrid_scores
