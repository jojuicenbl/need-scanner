"""FAISS index management with graceful fallback."""

import numpy as np
from pathlib import Path
from typing import Optional
from loguru import logger

# Try to import FAISS, but don't fail if unavailable
FAISS_AVAILABLE = False
try:
    import faiss
    FAISS_AVAILABLE = True
    logger.debug("FAISS is available")
except ImportError:
    logger.warning("FAISS not available. Index building will be skipped (clustering will still work).")


def build_faiss_index(embeddings: np.ndarray, use_gpu: bool = False) -> Optional[object]:
    """
    Build FAISS index from embeddings.

    Args:
        embeddings: Embeddings array (N x D)
        use_gpu: Whether to use GPU (default: False)

    Returns:
        FAISS index or None if FAISS unavailable
    """
    if not FAISS_AVAILABLE:
        logger.warning("FAISS not available, skipping index build")
        return None

    dimension = embeddings.shape[1]
    logger.info(f"Building FAISS index for {len(embeddings)} embeddings (dim={dimension})...")

    # Use flat L2 index for simplicity
    index = faiss.IndexFlatL2(dimension)

    # Add vectors
    index.add(embeddings)

    logger.info(f"FAISS index built with {index.ntotal} vectors")
    return index


def save_index(index: object, path: Path) -> None:
    """Save FAISS index to disk."""
    if not FAISS_AVAILABLE or index is None:
        logger.warning("Cannot save index: FAISS not available or index is None")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(path))
    logger.info(f"Saved FAISS index to {path}")


def load_index(path: Path) -> Optional[object]:
    """Load FAISS index from disk."""
    if not FAISS_AVAILABLE:
        logger.warning("Cannot load index: FAISS not available")
        return None

    if not path.exists():
        logger.warning(f"Index file not found: {path}")
        return None

    index = faiss.read_index(str(path))
    logger.info(f"Loaded FAISS index with {index.ntotal} vectors from {path}")
    return index


def search(
    index: object,
    query_vectors: np.ndarray,
    k: int = 10
) -> tuple:
    """
    Search FAISS index.

    Args:
        index: FAISS index
        query_vectors: Query vectors (N x D)
        k: Number of nearest neighbors

    Returns:
        Tuple of (distances, indices)
    """
    if not FAISS_AVAILABLE or index is None:
        logger.warning("Cannot search: FAISS not available or index is None")
        return None, None

    distances, indices = index.search(query_vectors, k)
    return distances, indices
