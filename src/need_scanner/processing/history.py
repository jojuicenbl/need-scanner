"""Cluster history management for inter-day deduplication."""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from loguru import logger
from sklearn.metrics.pairwise import cosine_similarity


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

    def get_embeddings(self) -> np.ndarray:
        """
        Get all historical embeddings.

        Returns:
            Array of embeddings (N, D)
        """
        embeddings = []

        for entry in self.entries:
            embedding = entry.get('embedding', [])
            if embedding:
                embeddings.append(embedding)

        if not embeddings:
            return np.array([])

        return np.array(embeddings)

    def compute_similarity_penalty(
        self,
        new_embeddings: np.ndarray,
        penalty_factor: float = 0.3
    ) -> np.ndarray:
        """
        Compute similarity penalty for new clusters based on history.

        Penalty formula:
        penalty = penalty_factor * max_similarity_to_history

        Args:
            new_embeddings: Array of new cluster embeddings (N, D)
            penalty_factor: Penalty strength (0-1), default 0.3

        Returns:
            Array of penalties (N,), in range [0, penalty_factor]
        """
        historical_embeddings = self.get_embeddings()

        if len(historical_embeddings) == 0:
            logger.info("No historical embeddings, no penalty applied")
            return np.zeros(len(new_embeddings))

        # Compute cosine similarity
        similarities = cosine_similarity(new_embeddings, historical_embeddings)

        # Max similarity to any historical cluster
        max_similarities = np.max(similarities, axis=1)

        # Compute penalty
        penalties = penalty_factor * max_similarities

        logger.info(
            f"Computed similarity penalties: "
            f"mean={np.mean(penalties):.3f}, "
            f"max={np.max(penalties):.3f}, "
            f"min={np.min(penalties):.3f}"
        )

        return penalties

    def apply_penalty_to_scores(
        self,
        priority_scores: np.ndarray,
        new_embeddings: np.ndarray,
        penalty_factor: float = 0.3
    ) -> np.ndarray:
        """
        Apply similarity penalty to priority scores.

        Formula:
        adjusted_score = priority_score * (1 - penalty_factor * max_similarity)

        Args:
            priority_scores: Array of priority scores (N,)
            new_embeddings: Array of new cluster embeddings (N, D)
            penalty_factor: Penalty strength (0-1)

        Returns:
            Array of adjusted priority scores (N,)
        """
        penalties = self.compute_similarity_penalty(new_embeddings, penalty_factor)

        # Apply multiplicative penalty
        adjusted_scores = priority_scores * (1 - penalties)

        # Log significant penalties
        significant_penalty_indices = np.where(penalties > 0.1)[0]
        if len(significant_penalty_indices) > 0:
            logger.info(f"Applied significant penalties to {len(significant_penalty_indices)} clusters:")
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
