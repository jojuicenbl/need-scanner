"""Maximal Marginal Relevance (MMR) reranking for diversity."""

import numpy as np
from typing import List, Tuple
from loguru import logger
from sklearn.metrics.pairwise import cosine_similarity


def normalize_scores(scores: np.ndarray) -> np.ndarray:
    """
    Normalize scores to [0, 1] range.

    Args:
        scores: Array of scores

    Returns:
        Normalized scores
    """
    min_score = np.min(scores)
    max_score = np.max(scores)

    if max_score == min_score:
        return np.ones_like(scores)

    return (scores - min_score) / (max_score - min_score)


def compute_mmr_scores(
    priority_scores: np.ndarray,
    embeddings: np.ndarray,
    selected_indices: List[int],
    lambda_param: float = 0.7
) -> np.ndarray:
    """
    Compute MMR scores for candidate items.

    MMR formula:
    MMR(d) = λ * Relevance(d) - (1 - λ) * max[Similarity(d, d_i) for d_i in Selected]

    Args:
        priority_scores: Array of priority scores (N,)
        embeddings: Array of embeddings (N, D)
        selected_indices: List of already selected indices
        lambda_param: Balance between relevance and diversity (0-1)
                     Higher = more relevance, lower = more diversity

    Returns:
        MMR scores for all candidates (N,)
    """
    # Normalize priority scores to [0, 1]
    normalized_scores = normalize_scores(priority_scores)

    # If no items selected yet, return priority scores
    if not selected_indices:
        return normalized_scores

    # Compute similarity matrix between candidates and selected items
    selected_embeddings = embeddings[selected_indices]
    similarities = cosine_similarity(embeddings, selected_embeddings)

    # Max similarity to any selected item
    max_similarities = np.max(similarities, axis=1)

    # MMR formula
    mmr_scores = lambda_param * normalized_scores - (1 - lambda_param) * max_similarities

    # Set already selected items to -inf so they won't be selected again
    mmr_scores[selected_indices] = -np.inf

    return mmr_scores


def mmr_rerank(
    items: List[dict],
    embeddings: np.ndarray,
    priority_scores: np.ndarray,
    top_k: int,
    lambda_param: float = 0.7
) -> Tuple[List[dict], List[int]]:
    """
    Rerank items using Maximal Marginal Relevance (MMR).

    Args:
        items: List of item dictionaries (clusters/insights)
        embeddings: Array of embeddings (N, D)
        priority_scores: Array of priority scores (N,)
        top_k: Number of items to select
        lambda_param: Balance between relevance and diversity (0-1)

    Returns:
        Tuple of (reranked items, selected indices)
    """
    n_items = len(items)
    top_k = min(top_k, n_items)

    logger.info(f"MMR reranking: selecting top {top_k} from {n_items} items (λ={lambda_param})")

    selected_indices = []
    reranked_items = []

    for rank in range(top_k):
        # Compute MMR scores for all candidates
        mmr_scores = compute_mmr_scores(
            priority_scores=priority_scores,
            embeddings=embeddings,
            selected_indices=selected_indices,
            lambda_param=lambda_param
        )

        # Select item with highest MMR score
        best_idx = int(np.argmax(mmr_scores))
        selected_indices.append(best_idx)

        # Add MMR rank to item
        item = items[best_idx].copy() if isinstance(items[best_idx], dict) else items[best_idx]
        if isinstance(item, dict):
            item['mmr_rank'] = rank + 1
        else:
            # For pydantic models
            item.mmr_rank = rank + 1

        reranked_items.append(item)

        logger.debug(
            f"MMR rank {rank + 1}: selected item {best_idx} "
            f"(priority: {priority_scores[best_idx]:.2f}, mmr: {mmr_scores[best_idx]:.3f})"
        )

    logger.info(f"MMR reranking complete. Selected {len(reranked_items)} diverse items.")

    return reranked_items, selected_indices


def mmr_rerank_by_sector(
    items: List[dict],
    embeddings: np.ndarray,
    priority_scores: np.ndarray,
    sectors: List[str],
    top_k_per_sector: int = 2,
    lambda_param: float = 0.7
) -> Tuple[List[dict], List[int]]:
    """
    Rerank items using MMR with sector diversity constraint.

    Ensures representation from multiple sectors.

    Args:
        items: List of item dictionaries (clusters/insights)
        embeddings: Array of embeddings (N, D)
        priority_scores: Array of priority scores (N,)
        sectors: List of sector labels for each item (N,)
        top_k_per_sector: Max items per sector
        lambda_param: Balance between relevance and diversity

    Returns:
        Tuple of (reranked items, selected indices)
    """
    from collections import defaultdict

    logger.info(f"MMR reranking by sector: max {top_k_per_sector} per sector (λ={lambda_param})")

    # Group items by sector
    sector_to_indices = defaultdict(list)
    for idx, sector in enumerate(sectors):
        sector_to_indices[sector].append(idx)

    selected_indices = []
    reranked_items = []
    sector_counts = defaultdict(int)

    # Sort sectors by average priority score (descending)
    sector_priorities = {}
    for sector, indices in sector_to_indices.items():
        avg_priority = np.mean(priority_scores[indices])
        sector_priorities[sector] = avg_priority

    sorted_sectors = sorted(sector_priorities.items(), key=lambda x: x[1], reverse=True)

    # Iterate through sectors and select top items from each
    for sector, _ in sorted_sectors:
        indices = sector_to_indices[sector]

        # Filter to items not yet selected
        available_indices = [idx for idx in indices if idx not in selected_indices]

        if not available_indices:
            continue

        # Limit per sector
        k = min(top_k_per_sector, len(available_indices))

        # MMR within this sector
        for _ in range(k):
            # Compute MMR scores for candidates in this sector
            sector_mmr_scores = compute_mmr_scores(
                priority_scores=priority_scores,
                embeddings=embeddings,
                selected_indices=selected_indices,
                lambda_param=lambda_param
            )

            # Filter to available indices in this sector
            sector_mmr_scores = np.array([
                sector_mmr_scores[idx] if idx in available_indices else -np.inf
                for idx in range(len(items))
            ])

            best_idx = int(np.argmax(sector_mmr_scores))

            if sector_mmr_scores[best_idx] == -np.inf:
                break

            selected_indices.append(best_idx)
            available_indices.remove(best_idx)

            # Add MMR rank to item
            item = items[best_idx].copy() if isinstance(items[best_idx], dict) else items[best_idx]
            if isinstance(item, dict):
                item['mmr_rank'] = len(reranked_items) + 1
            else:
                item.mmr_rank = len(reranked_items) + 1

            reranked_items.append(item)
            sector_counts[sector] += 1

    logger.info(f"MMR reranking by sector complete. Selected {len(reranked_items)} items:")
    for sector, count in sorted(sector_counts.items()):
        logger.info(f"  {sector}: {count}")

    return reranked_items, selected_indices
