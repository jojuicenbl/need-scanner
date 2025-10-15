"""Clustering using KMeans."""

import numpy as np
from typing import Tuple
from loguru import logger
from sklearn.cluster import KMeans


def cluster(
    embeddings: np.ndarray,
    n_clusters: int,
    random_state: int = 42,
    max_iter: int = 300
) -> Tuple[np.ndarray, KMeans]:
    """
    Cluster embeddings using KMeans.

    Args:
        embeddings: Embeddings array (N x D)
        n_clusters: Number of clusters
        random_state: Random seed
        max_iter: Maximum iterations

    Returns:
        Tuple of (cluster labels, KMeans model)
    """
    # Adjust n_clusters if we have fewer samples
    n_samples = len(embeddings)
    n_clusters = min(n_clusters, n_samples)

    logger.info(f"Clustering {n_samples} embeddings into {n_clusters} clusters...")

    # Fit KMeans
    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        max_iter=max_iter,
        n_init=10
    )
    labels = kmeans.fit_predict(embeddings)

    # Log statistics
    logger.info(f"Clustering complete. Inertia: {kmeans.inertia_:.2f}")

    # Count cluster sizes
    unique, counts = np.unique(labels, return_counts=True)
    for cluster_id, count in zip(unique, counts):
        logger.info(f"  Cluster {cluster_id}: {count} items")

    return labels, kmeans


def get_cluster_data(
    labels: np.ndarray,
    metadata: list,
    embeddings: np.ndarray = None
) -> dict:
    """
    Organize data by cluster.

    Args:
        labels: Cluster labels (N,)
        metadata: List of metadata dicts
        embeddings: Optional embeddings array

    Returns:
        Dict mapping cluster_id to list of (index, metadata, embedding) tuples
    """
    clusters = {}

    for idx, label in enumerate(labels):
        label = int(label)
        if label not in clusters:
            clusters[label] = []

        item = {
            "index": idx,
            "meta": metadata[idx]
        }

        if embeddings is not None:
            item["embedding"] = embeddings[idx]

        clusters[label].append(item)

    logger.info(f"Organized data into {len(clusters)} clusters")
    return clusters
