"""Novelty scoring - detect new/unique topics vs historical clusters."""

import json
from typing import Dict, List, Optional
from pathlib import Path
import numpy as np
from loguru import logger


def calculate_cluster_novelty(
    cluster_data: Dict[int, List[dict]],
    embeddings_by_cluster: Dict[int, np.ndarray],
    history_path: Optional[Path] = None
) -> Dict[int, float]:
    """
    Calculate novelty scores for clusters based on similarity to historical data.

    High novelty = cluster is different from what we've seen before.

    Args:
        cluster_data: Dict mapping cluster_id to list of post metadata
        embeddings_by_cluster: Dict mapping cluster_id to array of embeddings
        history_path: Path to historical embeddings (optional)

    Returns:
        Dict mapping cluster_id to novelty_score (0.0 to 10.0)
    """
    logger.info("Calculating cluster novelty...")

    novelty_scores = {}

    # Load historical cluster centroids if available
    historical_centroids = []

    if history_path and history_path.exists():
        try:
            with open(history_path, 'r') as f:
                history_data = json.load(f)
                # Convert stored centroids back to numpy arrays
                historical_centroids = [
                    np.array(centroid)
                    for centroid in history_data.get("centroids", [])
                ]
            logger.info(f"Loaded {len(historical_centroids)} historical centroids")
        except Exception as e:
            logger.warning(f"Failed to load historical centroids: {e}")

    # Calculate novelty for each cluster
    for cluster_id, embeddings in embeddings_by_cluster.items():
        if len(embeddings) == 0:
            novelty_scores[cluster_id] = 5.0
            continue

        # Calculate cluster centroid
        centroid = np.mean(embeddings, axis=0)

        if not historical_centroids:
            # No historical data - assign high novelty
            novelty_scores[cluster_id] = 8.0
            continue

        # Calculate max similarity with historical centroids
        similarities = []
        for hist_centroid in historical_centroids:
            # Cosine similarity
            similarity = np.dot(centroid, hist_centroid) / (
                np.linalg.norm(centroid) * np.linalg.norm(hist_centroid)
            )
            similarities.append(similarity)

        max_similarity = max(similarities)

        # Novelty = 1 - max_similarity (0 to 1)
        # Then scale to 0-10
        novelty = (1 - max_similarity) * 10.0

        novelty_scores[cluster_id] = round(max(0, min(novelty, 10.0)), 1)

    logger.info(f"Calculated novelty for {len(novelty_scores)} clusters")

    # Show most novel clusters
    sorted_novelty = sorted(novelty_scores.items(), key=lambda x: x[1], reverse=True)
    logger.info("Top 5 most novel clusters:")
    for cluster_id, score in sorted_novelty[:5]:
        size = len(cluster_data.get(cluster_id, []))
        logger.info(f"  Cluster {cluster_id}: novelty={score:.1f}, size={size}")

    return novelty_scores


def save_novelty_history(
    embeddings_by_cluster: Dict[int, np.ndarray],
    output_path: Path,
    max_centroids: int = 100
) -> None:
    """
    Save cluster centroids to history for future novelty comparisons.

    Args:
        embeddings_by_cluster: Dict mapping cluster_id to array of embeddings
        output_path: Path to save history JSON
        max_centroids: Maximum number of centroids to keep in history
    """
    # Load existing history
    historical_centroids = []

    if output_path.exists():
        try:
            with open(output_path, 'r') as f:
                history_data = json.load(f)
                historical_centroids = [
                    np.array(centroid)
                    for centroid in history_data.get("centroids", [])
                ]
        except Exception as e:
            logger.warning(f"Failed to load existing novelty history: {e}")

    # Calculate current centroids
    current_centroids = []
    for cluster_id, embeddings in embeddings_by_cluster.items():
        if len(embeddings) > 0:
            centroid = np.mean(embeddings, axis=0)
            current_centroids.append(centroid.tolist())

    # Combine with historical (keep most recent)
    all_centroids = current_centroids + [
        c.tolist() if isinstance(c, np.ndarray) else c
        for c in historical_centroids
    ]
    all_centroids = all_centroids[:max_centroids]

    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump({"centroids": all_centroids}, f)

    logger.info(f"Saved {len(all_centroids)} centroids to {output_path}")


def calculate_term_novelty(
    cluster_data: Dict[int, List[dict]],
    history_path: Optional[Path] = None
) -> Dict[int, float]:
    """
    Calculate term-based novelty using simple TF-IDF approach.

    Clusters with rare terms get higher novelty scores.

    Args:
        cluster_data: Dict mapping cluster_id to list of post metadata
        history_path: Path to historical term frequencies (optional)

    Returns:
        Dict mapping cluster_id to novelty_score (0.0 to 10.0)
    """
    logger.info("Calculating term-based novelty...")

    # Build current term frequencies
    from collections import Counter

    cluster_terms = {}
    for cluster_id, posts in cluster_data.items():
        terms = []
        for post in posts:
            title = post.get('title', '').lower()
            body = post.get('body', '').lower()
            # Simple tokenization
            words = title.split() + body.split()
            # Filter short words
            words = [w for w in words if len(w) > 3]
            terms.extend(words)

        cluster_terms[cluster_id] = Counter(terms)

    # Load historical term frequencies
    historical_freqs = Counter()

    if history_path and history_path.exists():
        try:
            with open(history_path, 'r') as f:
                historical_freqs = Counter(json.load(f))
            logger.info(f"Loaded historical term frequencies")
        except Exception as e:
            logger.warning(f"Failed to load historical term freqs: {e}")

    # Calculate novelty based on rare terms
    novelty_scores = {}

    for cluster_id, terms in cluster_terms.items():
        if not terms:
            novelty_scores[cluster_id] = 5.0
            continue

        # Calculate average rarity
        total_freq = sum(historical_freqs.values()) or 1
        rarities = []

        for term, count in terms.most_common(20):  # Top 20 terms
            hist_freq = historical_freqs.get(term, 0)
            # Inverse frequency (rare = high score)
            rarity = 1 / (1 + hist_freq / total_freq * 1000)
            rarities.append(rarity)

        avg_rarity = sum(rarities) / len(rarities) if rarities else 0.5
        novelty = avg_rarity * 10.0

        novelty_scores[cluster_id] = round(max(0, min(novelty, 10.0)), 1)

    logger.info(f"Calculated term novelty for {len(novelty_scores)} clusters")

    return novelty_scores


def save_term_history(
    cluster_data: Dict[int, List[dict]],
    output_path: Path,
    max_terms: int = 10000
) -> None:
    """
    Save term frequencies to history for future novelty comparisons.

    Args:
        cluster_data: Dict mapping cluster_id to list of post metadata
        output_path: Path to save history JSON
        max_terms: Maximum number of terms to keep
    """
    from collections import Counter

    # Load existing history
    historical_freqs = Counter()

    if output_path.exists():
        try:
            with open(output_path, 'r') as f:
                historical_freqs = Counter(json.load(f))
        except Exception as e:
            logger.warning(f"Failed to load existing term history: {e}")

    # Add current terms
    for cluster_id, posts in cluster_data.items():
        for post in posts:
            title = post.get('title', '').lower()
            body = post.get('body', '').lower()
            words = title.split() + body.split()
            words = [w for w in words if len(w) > 3]
            historical_freqs.update(words)

    # Keep only top terms
    top_terms = dict(historical_freqs.most_common(max_terms))

    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(top_terms, f)

    logger.info(f"Saved {len(top_terms)} terms to {output_path}")
