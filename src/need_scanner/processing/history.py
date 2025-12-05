"""Cluster history management for inter-day deduplication.

Step 5-bis Memory Stabilization:
- Gradual penalty instead of binary filtering
- Shorter history window for discover mode
- Configurable thresholds (tau, alpha, exact_dup)
- Fallback to ensure minimum insights per run
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, NamedTuple
from loguru import logger
from sklearn.metrics.pairwise import cosine_similarity


class SimilarityResult(NamedTuple):
    """Result of similarity computation for a single insight."""
    max_similarity: float
    most_similar_id: Optional[str]
    is_duplicate: bool  # True only for exact duplicates (sim >= exact_dup_threshold)
    is_recurring: bool  # True if similar but not exact duplicate (sim >= tau)


class ClusterHistory:
    """Manage historical clusters for deduplication and similarity tracking."""

    def __init__(self, history_path: Path):
        """
        Initialize cluster history manager.

        Args:
            history_path: Path to JSONL history file
        """
        self.history_path = Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing history
        self.entries = self._load_history()

        logger.info(f"Loaded {len(self.entries)} historical clusters from {self.history_path}")

    def _load_history(self) -> List[Dict]:
        """
        Load history from JSONL file.

        Returns:
            List of history entries
        """
        entries = []

        if not self.history_path.exists():
            logger.info(f"No history file found at {self.history_path}, starting fresh")
            return entries

        with open(self.history_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse history line: {e}")
                    continue

        return entries

    def _save_history(self):
        """Save history to JSONL file."""
        with open(self.history_path, 'w', encoding='utf-8') as f:
            for entry in self.entries:
                f.write(json.dumps(entry) + '\n')

        logger.info(f"Saved {len(self.entries)} clusters to history")

    def add_clusters(
        self,
        cluster_summaries: List[dict],
        embeddings: np.ndarray,
        priority_scores: List[float],
        date: Optional[str] = None
    ):
        """
        Add clusters to history.

        Args:
            cluster_summaries: List of cluster summary objects
            embeddings: Array of cluster embeddings (N, D)
            priority_scores: List of priority scores
            date: Date string (YYYY-MM-DD), defaults to today
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        for i, summary in enumerate(cluster_summaries):
            # Extract fields
            if isinstance(summary, dict):
                cluster_id = summary.get('cluster_id', i)
                title = summary.get('title', '')
                problem = summary.get('problem', summary.get('description', ''))
                sector = summary.get('sector', 'other')
            else:
                # Pydantic model
                cluster_id = summary.cluster_id
                title = summary.title
                problem = summary.problem if hasattr(summary, 'problem') else summary.description
                sector = summary.sector if hasattr(summary, 'sector') else 'other'

            # Create entry
            entry = {
                'id': f"{date}_{cluster_id}",
                'date': date,
                'cluster_id': cluster_id,
                'title': title,
                'problem': problem,
                'sector': sector,
                'priority_score': float(priority_scores[i]) if i < len(priority_scores) else 0.0,
                'embedding': embeddings[i].tolist() if i < len(embeddings) else []
            }

            self.entries.append(entry)

        logger.info(f"Added {len(cluster_summaries)} clusters to history (date: {date})")

    def get_embeddings(self, window_days: Optional[int] = None) -> Tuple[np.ndarray, List[Dict]]:
        """
        Get historical embeddings, optionally filtered by a time window.

        Args:
            window_days: If provided, only return entries from the last N days

        Returns:
            Tuple of (embeddings array (N, D), filtered entries list)
        """
        if window_days is not None:
            cutoff_date = datetime.now() - timedelta(days=window_days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")
            filtered_entries = [
                entry for entry in self.entries
                if entry.get('date', '') >= cutoff_str
            ]
            logger.debug(f"History window: {window_days} days, {len(filtered_entries)}/{len(self.entries)} entries")
        else:
            filtered_entries = self.entries

        embeddings = []
        valid_entries = []

        for entry in filtered_entries:
            embedding = entry.get('embedding', [])
            if embedding:
                embeddings.append(embedding)
                valid_entries.append(entry)

        if not embeddings:
            return np.array([]), []

        return np.array(embeddings), valid_entries

    def compute_detailed_similarity(
        self,
        new_embeddings: np.ndarray,
        tau: float = 0.90,
        exact_dup_threshold: float = 0.985,
        window_days: Optional[int] = None
    ) -> List[SimilarityResult]:
        """
        Compute detailed similarity for each new insight against history.

        Step 5-bis: Gradual penalty instead of binary filtering.
        - is_duplicate: True only for near-clones (sim >= exact_dup_threshold)
        - is_recurring: True for similar insights (sim >= tau) but not exact

        Args:
            new_embeddings: Array of new cluster embeddings (N, D)
            tau: Safe threshold - below this, no memory penalty (default 0.90)
            exact_dup_threshold: Above this = exact duplicate, will be excluded (default 0.985)
            window_days: If provided, only compare against last N days of history

        Returns:
            List of SimilarityResult for each input embedding
        """
        results = []
        historical_embeddings, filtered_entries = self.get_embeddings(window_days=window_days)

        if len(historical_embeddings) == 0:
            logger.info("No historical embeddings, all insights are novel")
            return [SimilarityResult(0.0, None, False, False) for _ in range(len(new_embeddings))]

        # Compute cosine similarity matrix
        similarities = cosine_similarity(new_embeddings, historical_embeddings)

        # For each new embedding, find max similarity and corresponding history entry
        for i in range(len(new_embeddings)):
            row_similarities = similarities[i]
            max_idx = np.argmax(row_similarities)
            max_sim = float(row_similarities[max_idx])

            # Get the ID of the most similar historical entry
            most_similar_id = None
            if max_idx < len(filtered_entries):
                most_similar_id = filtered_entries[max_idx].get('id')

            # Step 5-bis: Distinction between exact duplicate and recurring theme
            is_exact_duplicate = max_sim >= exact_dup_threshold
            is_recurring = (max_sim >= tau) and not is_exact_duplicate

            results.append(SimilarityResult(
                max_similarity=max_sim,
                most_similar_id=most_similar_id,
                is_duplicate=is_exact_duplicate,
                is_recurring=is_recurring
            ))

        # Log summary
        exact_dup_count = sum(1 for r in results if r.is_duplicate)
        recurring_count = sum(1 for r in results if r.is_recurring)
        novel_count = len(results) - exact_dup_count - recurring_count

        if results:
            avg_sim = np.mean([r.max_similarity for r in results])
            logger.info(
                f"Similarity analysis (window={window_days or 'all'} days): "
                f"novel={novel_count}, recurring={recurring_count}, exact_dup={exact_dup_count} "
                f"(tau={tau:.2f}, exact_dup_thresh={exact_dup_threshold:.3f}), avg_sim={avg_sim:.3f}"
            )

        return results

    def compute_similarity_penalty(
        self,
        new_embeddings: np.ndarray,
        tau: float = 0.90,
        alpha: float = 0.5,
        window_days: Optional[int] = None
    ) -> np.ndarray:
        """
        Compute gradual similarity penalty for new clusters based on history.

        Step 5-bis formula:
        penalty = max(0, sim_max - tau)  # Only penalize above safe threshold
        score_adjustment = 1 - alpha * penalty

        Args:
            new_embeddings: Array of new cluster embeddings (N, D)
            tau: Safe threshold - below this, no penalty (default 0.90)
            alpha: Penalty multiplier (0-1), how aggressively to penalize (default 0.5)
            window_days: If provided, only compare against last N days of history

        Returns:
            Array of penalties (N,), in range [0, alpha * (1 - tau)]
        """
        historical_embeddings, _ = self.get_embeddings(window_days=window_days)

        if len(historical_embeddings) == 0:
            logger.info("No historical embeddings, no penalty applied")
            return np.zeros(len(new_embeddings))

        # Compute cosine similarity
        similarities = cosine_similarity(new_embeddings, historical_embeddings)

        # Max similarity to any historical cluster
        max_similarities = np.max(similarities, axis=1)

        # Step 5-bis: Gradual penalty only above tau
        raw_penalties = np.maximum(0.0, max_similarities - tau)
        penalties = alpha * raw_penalties

        # Stats for logging
        above_tau_count = np.sum(max_similarities >= tau)
        logger.info(
            f"Computed gradual penalties (tau={tau:.2f}, alpha={alpha:.2f}): "
            f"{above_tau_count}/{len(new_embeddings)} above tau, "
            f"mean_penalty={np.mean(penalties):.3f}, max_penalty={np.max(penalties):.3f}"
        )

        return penalties

    def apply_penalty_to_scores(
        self,
        priority_scores: np.ndarray,
        new_embeddings: np.ndarray,
        tau: float = 0.90,
        alpha: float = 0.5,
        window_days: Optional[int] = None
    ) -> np.ndarray:
        """
        Apply gradual similarity penalty to priority scores.

        Step 5-bis Formula:
        penalty = max(0, sim_max - tau)
        adjusted_score = priority_score * (1 - alpha * penalty)

        Args:
            priority_scores: Array of priority scores (N,)
            new_embeddings: Array of new cluster embeddings (N, D)
            tau: Safe threshold - below this, no penalty (default 0.90)
            alpha: Penalty multiplier (0-1), default 0.5
            window_days: If provided, only compare against last N days of history

        Returns:
            Array of adjusted priority scores (N,)
        """
        penalties = self.compute_similarity_penalty(
            new_embeddings, tau=tau, alpha=alpha, window_days=window_days
        )

        # Apply multiplicative penalty
        adjusted_scores = priority_scores * (1 - penalties)

        # Log significant penalties
        significant_penalty_indices = np.where(penalties > 0.01)[0]
        if len(significant_penalty_indices) > 0:
            logger.info(f"Applied gradual penalties to {len(significant_penalty_indices)} clusters:")
            for idx in significant_penalty_indices[:5]:  # Show top 5
                logger.info(
                    f"  Cluster {idx}: {priority_scores[idx]:.2f} → {adjusted_scores[idx]:.2f} "
                    f"(penalty: {penalties[idx]:.3f})"
                )

        return adjusted_scores

    def cleanup_old_entries(self, retention_days: int = 30):
        """
        Remove entries older than retention_days.

        Args:
            retention_days: Number of days to retain
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        original_count = len(self.entries)
        self.entries = [
            entry for entry in self.entries
            if entry.get('date', '') >= cutoff_str
        ]

        removed_count = original_count - len(self.entries)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old entries (retention: {retention_days} days)")
            self._save_history()

    def get_history_stats(self) -> Dict:
        """
        Get statistics about the history.

        Returns:
            Dict with stats
        """
        if not self.entries:
            return {
                'total_clusters': 0,
                'date_range': None,
                'sectors': {}
            }

        dates = [entry['date'] for entry in self.entries]
        sectors = [entry.get('sector', 'other') for entry in self.entries]

        from collections import Counter
        sector_counts = Counter(sectors)

        return {
            'total_clusters': len(self.entries),
            'date_range': f"{min(dates)} to {max(dates)}",
            'sectors': dict(sector_counts)
        }

    def save(self):
        """Save current history to disk."""
        self._save_history()


def load_or_create_history(
    history_path: Path = Path("data/history/clusters.jsonl"),
    retention_days: int = 30
) -> ClusterHistory:
    """
    Load existing history or create new one.

    Args:
        history_path: Path to history file
        retention_days: Number of days to retain

    Returns:
        ClusterHistory instance
    """
    history = ClusterHistory(history_path)
    history.cleanup_old_entries(retention_days)

    stats = history.get_history_stats()
    logger.info(f"History stats: {stats}")

    return history
