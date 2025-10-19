"""Heuristic pain scoring and advanced priority scoring for market discovery."""

import re
from typing import List, Dict, Set
from loguru import logger


# Keywords indicating pain points
PAIN_KEYWORDS = [
    "help", "tool", "pay", "automate", "stuck", "urgence", "urgent",
    "devis", "facture", "invoice", "bill", "problem", "issue", "difficult",
    "hard", "struggle", "need", "looking for", "cherche", "besoin",
    "comment", "how to", "frustrat", "annoying", "time-consuming",
    "manuel", "manual", "répétit", "repetitive", "tedious"
]


def count_pain_keywords(text: str) -> int:
    """Count pain-related keywords in text."""
    text_lower = text.lower()
    count = sum(1 for keyword in PAIN_KEYWORDS if keyword in text_lower)
    return count


def compute_pain_score(meta_items: List[dict]) -> int:
    """
    Compute heuristic pain score (0-10) based on engagement metrics.

    Args:
        meta_items: List of metadata dicts with score, num_comments, title

    Returns:
        Pain score from 0 to 10
    """
    if not meta_items:
        return 0

    # Extract metrics
    scores = [item.get("score", 0) for item in meta_items]
    comments = [item.get("num_comments", 0) for item in meta_items]
    titles = [item.get("title", "") for item in meta_items]

    # Average engagement
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_comments = sum(comments) / len(comments) if comments else 0

    # Keyword density
    total_keywords = sum(count_pain_keywords(title) for title in titles)
    keyword_density = total_keywords / len(titles) if titles else 0

    # Normalize components to 0-10 scale
    # Score: 0-50 maps to 0-5
    score_component = min(avg_score / 10, 5)

    # Comments: 0-20 maps to 0-3
    comment_component = min(avg_comments / 7, 3)

    # Keywords: 0-3+ maps to 0-2
    keyword_component = min(keyword_density * 2, 2)

    # Combine
    total = score_component + comment_component + keyword_component
    pain_score = int(round(total))

    # Clamp to 0-10
    return max(0, min(10, pain_score))


def combine_scores(llm_score: int, heuristic_score: int, llm_weight: float = 0.6) -> int:
    """
    Combine LLM and heuristic scores.

    Args:
        llm_score: Score from LLM (1-10)
        heuristic_score: Score from heuristics (0-10)
        llm_weight: Weight for LLM score (default: 0.6)

    Returns:
        Combined score (0-10)
    """
    if llm_score is None:
        return heuristic_score

    combined = llm_weight * llm_score + (1 - llm_weight) * heuristic_score
    return int(round(combined))


def compute_traction_score(meta_items: List[dict]) -> float:
    """
    Compute traction score (0-10) based on engagement and virality.

    Factors:
    - Average score/upvotes per post
    - Average comments per post
    - Cluster size (more posts = more evidence of need)
    - Peak engagement (highest performing post)

    Args:
        meta_items: List of metadata dicts with score, comments_count

    Returns:
        Traction score from 0.0 to 10.0
    """
    if not meta_items:
        return 0.0

    # Extract metrics (use unified field names)
    scores = [item.get("score", 0) for item in meta_items]
    comments = [item.get("comments_count", 0) or item.get("num_comments", 0) for item in meta_items]

    # Average engagement
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_comments = sum(comments) / len(comments) if comments else 0

    # Peak engagement
    max_score = max(scores) if scores else 0
    max_comments = max(comments) if comments else 0

    # Cluster size (number of posts)
    cluster_size = len(meta_items)

    # Normalize components to 0-10 scale
    # Average score: 0-100 maps to 0-3
    avg_score_component = min(avg_score / 33.3, 3.0)

    # Average comments: 0-50 maps to 0-2
    avg_comments_component = min(avg_comments / 25.0, 2.0)

    # Peak engagement: 0-200 score + 0-100 comments maps to 0-3
    peak_component = min((max_score / 100.0) + (max_comments / 100.0), 3.0)

    # Cluster size: 3-20+ posts maps to 0-2
    size_component = min((cluster_size - 2) / 9.0, 2.0) if cluster_size >= 3 else 0.0

    # Combine
    traction_score = avg_score_component + avg_comments_component + peak_component + size_component

    # Clamp to 0-10
    return max(0.0, min(10.0, traction_score))


def compute_novelty_score(alternatives: List[str], willingness_to_pay_signal: str) -> float:
    """
    Compute novelty score (0-10) based on market saturation and WTP signals.

    Lower alternatives = higher novelty (less saturated market)
    Strong WTP signals = higher novelty (validated demand)

    Args:
        alternatives: List of alternative tools/solutions mentioned
        willingness_to_pay_signal: Willingness-to-pay signal detected

    Returns:
        Novelty score from 0.0 to 10.0
    """
    # Fewer alternatives = less saturated market = higher score
    # 0 alternatives = 6.0, 1-2 = 5.0, 3-5 = 3.0, 6+ = 1.0
    num_alternatives = len(alternatives) if alternatives else 0

    if num_alternatives == 0:
        alternative_component = 6.0
    elif num_alternatives <= 2:
        alternative_component = 5.0
    elif num_alternatives <= 5:
        alternative_component = 3.0
    else:
        alternative_component = 1.0

    # WTP signal strength
    wtp_signal = willingness_to_pay_signal.lower() if willingness_to_pay_signal else ""

    if any(phrase in wtp_signal for phrase in ["currently paying", "willing to pay", "would pay", "subscription"]):
        wtp_component = 4.0  # Strong signal
    elif any(phrase in wtp_signal for phrase in ["expensive", "cost", "price", "budget"]):
        wtp_component = 2.0  # Moderate signal
    elif wtp_signal:
        wtp_component = 1.0  # Weak signal
    else:
        wtp_component = 0.0  # No signal

    # Combine
    novelty_score = alternative_component + wtp_component

    # Clamp to 0-10
    return max(0.0, min(10.0, novelty_score))


def compute_source_diversity_bonus(sources: List[str]) -> float:
    """
    Compute bonus for appearing across multiple sources.

    Multi-source problems are more validated.

    Args:
        sources: List of sources (e.g., ["reddit", "hn", "rss"])

    Returns:
        Bonus multiplier (1.0 to 1.2)
    """
    unique_sources = len(set(sources)) if sources else 0

    if unique_sources >= 3:
        return 1.2  # 20% bonus for 3+ sources
    elif unique_sources == 2:
        return 1.1  # 10% bonus for 2 sources
    else:
        return 1.0  # No bonus for single source


def compute_priority_score(
    pain_score_llm: int,
    heuristic_score: float,
    traction_score: float,
    novelty_score: float,
    sources: List[str] = None
) -> float:
    """
    Compute advanced priority score using weighted formula.

    Formula: priority = (0.45 * pain_llm + 0.25 * heuristic + 0.20 * traction + 0.10 * novelty) * source_bonus

    Args:
        pain_score_llm: Pain score from LLM (0-10)
        heuristic_score: Heuristic score (0-10)
        traction_score: Traction score (0-10)
        novelty_score: Novelty score (0-10)
        sources: List of sources for diversity bonus

    Returns:
        Priority score (0-12, with bonus can exceed 10)
    """
    # Default to 5 if no LLM score
    pain_llm = pain_score_llm if pain_score_llm is not None else 5.0

    # Weighted combination
    base_score = (
        0.45 * pain_llm +
        0.25 * heuristic_score +
        0.20 * traction_score +
        0.10 * novelty_score
    )

    # Apply source diversity bonus
    if sources:
        source_bonus = compute_source_diversity_bonus(sources)
        priority_score = base_score * source_bonus
    else:
        priority_score = base_score

    return round(priority_score, 2)


def rank_insights_by_priority(insights: List[Dict]) -> List[Dict]:
    """
    Rank insights by priority score (highest first).

    Args:
        insights: List of insight dicts with priority_score field

    Returns:
        Sorted list of insights with rank field added
    """
    # Sort by priority_score descending
    sorted_insights = sorted(
        insights,
        key=lambda x: x.get("priority_score", 0),
        reverse=True
    )

    # Add rank field
    for rank, insight in enumerate(sorted_insights, start=1):
        insight["rank"] = rank

    return sorted_insights
