"""Priority scoring system for insights ranking."""

from typing import List, Dict
from loguru import logger

from ..schemas import Post, EnrichedClusterSummary, EnrichedInsight


def calculate_traction_score(posts: List[Dict]) -> float:
    """
    Calculate traction score based on engagement metrics.

    Args:
        posts: List of post metadata dictionaries

    Returns:
        Traction score (0.0 to 10.0)
    """
    if not posts:
        return 0.0

    # Extract metrics
    total_score = sum(p.get('score', 0) for p in posts)
    total_comments = sum(p.get('comments_count', p.get('num_comments', 0)) for p in posts)
    avg_score = total_score / len(posts)
    avg_comments = total_comments / len(posts)

    # Normalize to 0-10 scale
    # High traction: avg_score > 50, avg_comments > 20
    score_component = min(avg_score / 10.0, 5.0)  # Max 5.0 from score
    comments_component = min(avg_comments / 4.0, 5.0)  # Max 5.0 from comments

    total = score_component + comments_component

    return round(min(total, 10.0), 1)


def calculate_novelty_score(summary: EnrichedClusterSummary, posts: List[Dict]) -> float:
    """
    Calculate novelty score based on alternatives and uniqueness.

    Args:
        summary: EnrichedClusterSummary with alternatives field
        posts: List of post metadata

    Returns:
        Novelty score (0.0 to 10.0)
    """
    # Base score
    base_score = 5.0

    # Fewer alternatives = more novel
    num_alternatives = len(summary.alternatives) if summary.alternatives else 0
    if num_alternatives == 0:
        alternative_bonus = 4.0  # No existing solutions mentioned
    elif num_alternatives == 1:
        alternative_bonus = 2.0
    elif num_alternatives == 2:
        alternative_bonus = 1.0
    else:
        alternative_bonus = -1.0  # Many alternatives = crowded space

    # Recency bonus: newer posts = more novel/trending
    # (Not implemented yet, would need timestamp analysis)
    recency_bonus = 0.0

    # Cluster size penalty: very large clusters might be generic
    cluster_size = summary.size
    if cluster_size > 20:
        size_penalty = -2.0
    elif cluster_size > 10:
        size_penalty = -1.0
    else:
        size_penalty = 1.0  # Small focused clusters = more specific need

    total = base_score + alternative_bonus + recency_bonus + size_penalty

    return round(min(max(total, 0.0), 10.0), 1)


def calculate_priority_score(
    pain_score_llm: float,
    heuristic_score: float,
    traction_score: float,
    novelty_score: float,
    wtp_score: float = 0.0,
    trend_score: float = 5.0,
    # Configurable weights (default formula)
    pain_weight: float = 0.30,
    traction_weight: float = 0.25,
    novelty_weight: float = 0.15,
    wtp_weight: float = 0.20,
    trend_weight: float = 0.10
) -> float:
    """
    Calculate final priority score using weighted combination.

    Default formula (customizable):
    - 30% Pain Score (LLM + heuristic combined)
    - 25% Traction (engagement metrics)
    - 15% Novelty (uniqueness vs history)
    - 20% WTP signals (willingness to pay)
    - 10% Trend (week-over-week growth)

    Args:
        pain_score_llm: Pain score from LLM (0-10)
        heuristic_score: Heuristic pain score (0-10)
        traction_score: Engagement score (0-10)
        novelty_score: Novelty score (0-10)
        wtp_score: WTP signal score (0-10)
        trend_score: Trend growth score (0-10)
        pain_weight: Weight for pain score (default 0.30)
        traction_weight: Weight for traction score (default 0.25)
        novelty_weight: Weight for novelty score (default 0.15)
        wtp_weight: Weight for WTP score (default 0.20)
        trend_weight: Weight for trend score (default 0.10)

    Returns:
        Priority score (0.0 to 10.0)
    """
    # Combine LLM and heuristic pain scores
    combined_pain = (pain_score_llm * 0.7 + heuristic_score * 0.3)

    # Normalize weights to sum to 1.0
    total_weight = pain_weight + traction_weight + novelty_weight + wtp_weight + trend_weight
    if total_weight == 0:
        total_weight = 1.0

    # Weighted combination
    priority = (
        combined_pain * (pain_weight / total_weight) +
        traction_score * (traction_weight / total_weight) +
        novelty_score * (novelty_weight / total_weight) +
        wtp_score * (wtp_weight / total_weight) +
        trend_score * (trend_weight / total_weight)
    )

    return round(min(priority, 10.0), 2)


def enrich_insight_with_priority(
    insight: EnrichedInsight,
    posts: List[Dict],
    wtp_score: float = 0.0
) -> EnrichedInsight:
    """
    Enrich an insight with priority scoring.

    Args:
        insight: EnrichedInsight to enrich
        posts: List of post metadata for this cluster
        wtp_score: Average WTP score for posts in cluster

    Returns:
        Updated EnrichedInsight with priority scores
    """
    # Calculate component scores
    traction_score = calculate_traction_score(posts)
    novelty_score = calculate_novelty_score(insight.summary, posts)

    # Use existing scores from insight
    pain_llm = insight.summary.pain_score_llm or 5.0
    heuristic = insight.heuristic_score or 5.0

    # Calculate priority
    priority_score = calculate_priority_score(
        pain_score_llm=pain_llm,
        heuristic_score=heuristic,
        traction_score=traction_score,
        novelty_score=novelty_score,
        wtp_score=wtp_score
    )

    # Update insight
    insight.traction_score = traction_score
    insight.novelty_score = novelty_score
    insight.priority_score = priority_score

    return insight


def rank_insights(insights: List[EnrichedInsight]) -> List[EnrichedInsight]:
    """
    Rank insights by priority score and assign rank numbers.

    Args:
        insights: List of EnrichedInsight objects

    Returns:
        Sorted list with rank field populated (1 = highest priority)
    """
    # Sort by priority score (descending)
    sorted_insights = sorted(
        insights,
        key=lambda x: x.priority_score if x.priority_score is not None else 0.0,
        reverse=True
    )

    # Assign ranks
    for rank, insight in enumerate(sorted_insights, 1):
        insight.rank = rank

    logger.info(f"Ranked {len(sorted_insights)} insights by priority score")

    # Show top 3
    if sorted_insights:
        logger.info("Top 3 priorities:")
        for insight in sorted_insights[:3]:
            logger.info(
                f"  #{insight.rank}: {insight.summary.title} "
                f"(priority: {insight.priority_score:.2f}, "
                f"pain: {insight.summary.pain_score_llm}, "
                f"traction: {insight.traction_score:.1f})"
            )

    return sorted_insights


def calculate_avg_wtp_score(posts: List[Post]) -> float:
    """
    Calculate average WTP score for a list of posts.

    Args:
        posts: List of Post objects with wtp_signals

    Returns:
        Average WTP score (0.0 to 10.0)
    """
    from .wtp import get_wtp_score

    if not posts:
        return 0.0

    total_score = sum(get_wtp_score(p) for p in posts)
    avg_score = total_score / len(posts)

    return round(avg_score, 1)
