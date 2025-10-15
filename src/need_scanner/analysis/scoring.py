"""Heuristic pain scoring based on engagement metrics and keywords."""

import re
from typing import List
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
