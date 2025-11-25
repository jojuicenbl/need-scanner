"""Sector classification for clusters using LLM."""

import json
import time
from typing import Optional
from loguru import logger
from openai import OpenAI


# Pre-defined sector labels
SECTORS = [
    "dev_tools",
    "ai_llm",
    "business_pme",
    "education_learning",
    "health_wellbeing",
    "consumer_lifestyle",
    "creator_economy",
    "workplace_hr",
    "finance_accounting",
    "legal_compliance",
    "marketing_sales",
    "ecommerce_retail",
    "other"
]


SYSTEM_PROMPT = """Tu es un analyste qui classifie des clusters thématiques dans des secteurs prédéfinis.
Réponds uniquement avec un JSON strict contenant le champ "sector"."""


def build_sector_prompt(cluster_title: str, cluster_summary: str) -> str:
    """
    Build prompt for sector classification.

    Args:
        cluster_title: Title of the cluster
        cluster_summary: Summary/description of the cluster

    Returns:
        User prompt string
    """
    sectors_list = ", ".join(SECTORS)

    prompt = f"""Voici un cluster thématique représentant un besoin utilisateur :

**Titre** : {cluster_title}
**Résumé** : {cluster_summary}

**Tâche** : Classifie ce cluster dans UN SEUL secteur parmi cette liste fermée :
{sectors_list}

**Instructions** :
- Choisis le secteur le plus pertinent
- Si aucun secteur ne correspond vraiment, utilise "other"
- Réponds UNIQUEMENT en JSON avec la clé "sector"

**Format attendu** :
{{"sector": "dev_tools"}}
"""

    return prompt


def classify_cluster_sector(
    cluster_title: str,
    cluster_summary: str,
    model: str,
    api_key: str,
    max_retries: int = 2
) -> str:
    """
    Classify a cluster into a sector using LLM.

    Args:
        cluster_title: Title of the cluster
        cluster_summary: Summary/description of the cluster
        model: LLM model name (should be light model)
        api_key: OpenAI API key
        max_retries: Maximum retry attempts

    Returns:
        Sector label (one of SECTORS)
    """
    user_prompt = build_sector_prompt(cluster_title, cluster_summary)

    client = OpenAI(api_key=api_key)

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=50,
                temperature=0.3  # Low temperature for consistent classification
            )

            # Parse response
            response_text = response.choices[0].message.content
            data = json.loads(response_text)

            # Validate sector
            sector = data.get("sector", "other")
            if sector not in SECTORS:
                logger.warning(f"Invalid sector '{sector}' returned by LLM, defaulting to 'other'")
                sector = "other"

            logger.debug(f"Cluster '{cluster_title}' classified as '{sector}'")
            return sector

        except json.JSONDecodeError:
            # Try to extract sector from text if JSON parsing fails
            response_text = response.choices[0].message.content.lower()
            for sector in SECTORS:
                if sector in response_text:
                    logger.warning(f"JSON parsing failed, extracted sector '{sector}' from text")
                    return sector

            if attempt < max_retries:
                logger.warning(f"Sector classification failed, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(1)
                continue
            else:
                logger.error(f"Failed to classify sector after {max_retries} retries, defaulting to 'other'")
                return "other"

        except Exception as e:
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.warning(
                    f"Sector classification error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to classify sector after {max_retries + 1} attempts: {e}")
                return "other"

    return "other"


def classify_all_clusters_sectors(
    clusters_summaries: list,
    model: str,
    api_key: str
) -> dict:
    """
    Classify all clusters into sectors.

    Args:
        clusters_summaries: List of cluster summary objects (with cluster_id, title, problem/description)
        model: LLM model name (should be light model)
        api_key: OpenAI API key

    Returns:
        Dict mapping cluster_id to sector label
    """
    sectors_map = {}

    logger.info(f"Classifying {len(clusters_summaries)} clusters into sectors...")

    for summary in clusters_summaries:
        cluster_id = summary.cluster_id
        title = summary.title

        # Get description/problem field
        if hasattr(summary, 'problem'):
            description = summary.problem
        else:
            description = summary.description

        # Classify
        sector = classify_cluster_sector(
            cluster_title=title,
            cluster_summary=description,
            model=model,
            api_key=api_key
        )

        sectors_map[cluster_id] = sector

        # Small delay between calls
        time.sleep(0.3)

    # Log distribution
    from collections import Counter
    sector_counts = Counter(sectors_map.values())
    logger.info("Sector distribution:")
    for sector, count in sector_counts.most_common():
        logger.info(f"  {sector}: {count}")

    return sectors_map
