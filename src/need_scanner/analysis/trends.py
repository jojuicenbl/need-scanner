"""Trend analysis - detect emerging topics via week-over-week growth."""

import time
from typing import Dict, List, Optional
from collections import defaultdict
from pathlib import Path
import json
import numpy as np
from loguru import logger


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
