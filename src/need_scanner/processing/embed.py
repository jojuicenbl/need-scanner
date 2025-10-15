"""Embeddings generation using OpenAI API."""

import time
import numpy as np
from typing import List, Tuple
from pathlib import Path
from loguru import logger
from openai import OpenAI

from ..schemas import Post
from ..utils import estimate_tokens_batch, calculate_cost, write_json, format_cost


def create_text_for_embedding(post: Post) -> str:
    """Create text representation of post for embedding."""
    # Combine title and selftext
    parts = [post.title]
    if post.selftext:
        parts.append(post.selftext)
    return " ".join(parts)


def embed_texts(
    texts: List[str],
    model: str,
    api_key: str,
    batch_size: int = 64,
    max_retries: int = 3
) -> Tuple[np.ndarray, float]:
    """
    Generate embeddings for texts using OpenAI API.

    Args:
        texts: List of texts to embed
        model: Embedding model name
        api_key: OpenAI API key
        batch_size: Batch size for API calls
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (embeddings array, cost in USD)
    """
    client = OpenAI(api_key=api_key)
    all_embeddings = []
    total_tokens = 0

    logger.info(f"Generating embeddings for {len(texts)} texts using {model}...")

    # Estimate cost
    estimated_tokens = estimate_tokens_batch(texts)
    estimated_cost = calculate_cost(estimated_tokens, 0, model)
    logger.info(f"Estimated cost: {format_cost(estimated_cost)} ({estimated_tokens} tokens)")

    # Process in batches
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(texts) + batch_size - 1) // batch_size

        logger.info(f"Processing batch {batch_num}/{total_batches}...")

        for attempt in range(max_retries):
            try:
                response = client.embeddings.create(
                    model=model,
                    input=batch
                )

                # Extract embeddings
                embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(embeddings)

                # Track tokens
                total_tokens += response.usage.total_tokens

                break  # Success

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed after {max_retries} attempts: {e}")
                    raise

        # Small delay between batches
        time.sleep(0.5)

    # Convert to numpy array
    embeddings_array = np.array(all_embeddings, dtype=np.float32)

    # Calculate actual cost
    actual_cost = calculate_cost(total_tokens, 0, model)
    logger.info(f"Generated {len(embeddings_array)} embeddings. Actual cost: {format_cost(actual_cost)} ({total_tokens} tokens)")

    return embeddings_array, actual_cost


def embed_posts(
    posts: List[Post],
    model: str,
    api_key: str,
    output_dir: Path,
    batch_size: int = 64
) -> Tuple[np.ndarray, List[dict], float]:
    """
    Generate embeddings for posts and save to disk.

    Args:
        posts: List of posts
        model: Embedding model name
        api_key: OpenAI API key
        output_dir: Directory to save embeddings
        batch_size: Batch size for API calls

    Returns:
        Tuple of (embeddings array, metadata list, cost in USD)
    """
    # Create texts for embedding
    texts = [create_text_for_embedding(p) for p in posts]

    # Generate embeddings
    embeddings, cost = embed_texts(texts, model, api_key, batch_size)

    # Create metadata
    metadata = [
        {
            "id": p.id,
            "url": p.permalink,
            "score": p.score,
            "num_comments": p.num_comments,
            "title": p.title
        }
        for p in posts
    ]

    # Save to disk
    embeddings_path = output_dir / "embeddings.npy"
    metadata_path = output_dir / "meta.json"

    np.save(embeddings_path, embeddings)
    logger.info(f"Saved embeddings to {embeddings_path}")

    write_json(metadata_path, metadata)

    return embeddings, metadata, cost


def load_embeddings(embeddings_path: Path) -> np.ndarray:
    """Load embeddings from disk."""
    embeddings = np.load(embeddings_path)
    logger.info(f"Loaded {len(embeddings)} embeddings from {embeddings_path}")
    return embeddings
