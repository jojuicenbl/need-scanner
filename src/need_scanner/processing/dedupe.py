"""Deduplication using hashing, fuzzy matching, and Jaccard similarity."""

import hashlib
import re
import json
import time
from typing import List, Set, Optional
from pathlib import Path
from loguru import logger
from rapidfuzz import fuzz

from ..schemas import Post


def compute_hash(post: Post) -> str:
    """Compute hash from post ID and URL."""
    key = f"{post.id}:{post.url}"
    return hashlib.md5(key.encode()).hexdigest()


def compute_content_hash(post: Post) -> str:
    """Compute hash from normalized content (cross-source duplicate detection)."""
    # Normalize: lowercase, remove extra whitespace
    text = f"{post.title} {post.body}".lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return hashlib.md5(text.encode()).hexdigest()


def is_fuzzy_duplicate(title1: str, title2: str, threshold: int = 90) -> bool:
    """Check if two titles are fuzzy duplicates."""
    ratio = fuzz.ratio(title1.lower(), title2.lower())
    return ratio >= threshold


def tokenize(text: str) -> Set[str]:
    """Tokenize text into words for Jaccard similarity."""
    # Lowercase and split on non-alphanumeric
    tokens = re.findall(r'\w+', text.lower())
    return set(tokens)


def jaccard_similarity(text1: str, text2: str) -> float:
    """
    Calculate Jaccard similarity between two texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Jaccard similarity score (0.0 to 1.0)
    """
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0


def is_jaccard_duplicate(
    post1: Post,
    post2: Post,
    threshold: float = 0.7
) -> bool:
    """
    Check if two posts are duplicates using Jaccard similarity.

    Args:
        post1: First post
        post2: Second post
        threshold: Jaccard threshold (0.0 to 1.0)

    Returns:
        True if posts are considered duplicates
    """
    # Combine title and body for comparison
    text1 = f"{post1.title} {post1.body}".strip()
    text2 = f"{post2.title} {post2.body}".strip()

    similarity = jaccard_similarity(text1, text2)
    return similarity >= threshold


def load_history_hashes(
    history_path: Optional[Path],
    history_days: int = 0
) -> Set[str]:
    """
    Load historical post hashes from previous runs.

    Args:
        history_path: Path to history file (JSON)
        history_days: Maximum age of historical data to load (0 = no history)

    Returns:
        Set of historical post hashes
    """
    if not history_path or history_days == 0 or not history_path.exists():
        return set()

    try:
        with open(history_path, 'r') as f:
            history_data = json.load(f)

        cutoff_ts = time.time() - (history_days * 86400)
        historical_hashes = set()

        for item in history_data.get("posts", []):
            ts = item.get("timestamp", 0)
            if ts >= cutoff_ts:
                historical_hashes.add(item.get("hash", ""))

        logger.info(f"Loaded {len(historical_hashes)} historical hashes ({history_days} days)")
        return historical_hashes

    except Exception as e:
        logger.warning(f"Failed to load history: {e}")
        return set()


def save_history_hashes(
    posts: List[Post],
    history_path: Path,
    max_age_days: int = 60
) -> None:
    """
    Save current post hashes to history for future deduplication.

    Args:
        posts: List of posts to save
        history_path: Path to history file
        max_age_days: Maximum age to keep in history
    """
    # Load existing history
    existing_history = []

    if history_path.exists():
        try:
            with open(history_path, 'r') as f:
                existing_history = json.load(f).get("posts", [])
        except Exception as e:
            logger.warning(f"Failed to load existing history: {e}")

    # Add current posts
    cutoff_ts = time.time() - (max_age_days * 86400)
    current_ts = time.time()

    all_posts = []

    # Keep historical posts within max_age
    for item in existing_history:
        if item.get("timestamp", 0) >= cutoff_ts:
            all_posts.append(item)

    # Add new posts
    for post in posts:
        all_posts.append({
            "hash": compute_hash(post),
            "content_hash": compute_content_hash(post),
            "title": post.title[:100],
            "timestamp": current_ts
        })

    # Save to file
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, 'w') as f:
        json.dump({"posts": all_posts}, f, indent=2)

    logger.info(f"Saved {len(all_posts)} posts to history ({history_path})")


def dedupe(
    posts: List[Post],
    fuzzy_threshold: int = 90,
    jaccard_threshold: float = 0.7,
    cross_source: bool = True,
    history_path: Optional[Path] = None,
    history_days: int = 0
) -> List[Post]:
    """
    Deduplicate posts using multiple strategies:
    1. Exact hash matching (same ID + URL)
    2. Content hash matching (same normalized content across sources)
    3. Fuzzy title matching (similar titles)
    4. Jaccard similarity (similar content)
    5. Historical deduplication (against N days of previous posts)

    Args:
        posts: List of posts to deduplicate
        fuzzy_threshold: Fuzzy matching threshold for titles (0-100)
        jaccard_threshold: Jaccard similarity threshold for content (0.0-1.0)
        cross_source: Enable cross-source deduplication (content hash + Jaccard)
        history_path: Path to history file for multi-week deduplication
        history_days: Number of days of history to check (0 = no history)

    Returns:
        Deduplicated list of posts
    """
    logger.info(f"Deduplicating {len(posts)} posts...")
    logger.info(f"Cross-source deduplication: {'enabled' if cross_source else 'disabled'}")

    # Load historical hashes
    historical_hashes = load_history_hashes(history_path, history_days)

    seen_hashes: Set[str] = set()
    seen_content_hashes: Set[str] = set()
    unique_posts: List[Post] = []

    duplicate_count = 0
    historical_duplicate_count = 0

    for post in posts:
        is_duplicate = False

        # 0. Check against historical hashes
        post_hash = compute_hash(post)
        if post_hash in historical_hashes:
            logger.debug(f"Historical duplicate: {post.id}")
            historical_duplicate_count += 1
            continue

        # 1. Check exact hash (same ID + URL)
        if post_hash in seen_hashes:
            duplicate_count += 1
            continue

        # 2. Check content hash (cross-source exact content match)
        if cross_source:
            content_hash = compute_content_hash(post)
            if content_hash in seen_content_hashes:
                logger.debug(f"Content hash duplicate: {post.id} (source: {post.source})")
                duplicate_count += 1
                continue

        # 3. Check fuzzy title match against existing posts
        for existing_post in unique_posts:
            if is_fuzzy_duplicate(post.title, existing_post.title, fuzzy_threshold):
                logger.debug(f"Fuzzy title duplicate: {post.id} vs {existing_post.id}")
                is_duplicate = True
                break

        if is_duplicate:
            duplicate_count += 1
            continue

        # 4. Check Jaccard similarity (cross-source semantic match)
        if cross_source:
            for existing_post in unique_posts:
                if is_jaccard_duplicate(post, existing_post, jaccard_threshold):
                    logger.debug(f"Jaccard duplicate: {post.id} vs {existing_post.id} (sources: {post.source}, {existing_post.source})")
                    is_duplicate = True
                    break

        if is_duplicate:
            duplicate_count += 1
            continue

        # Keep this post
        seen_hashes.add(post_hash)
        if cross_source:
            seen_content_hashes.add(compute_content_hash(post))
        unique_posts.append(post)

    total_removed = duplicate_count + historical_duplicate_count
    logger.info(f"Removed {total_removed} duplicates ({historical_duplicate_count} historical), kept {len(unique_posts)} unique posts")

    # Save to history for future runs
    if history_path and history_days > 0:
        save_history_hashes(unique_posts, history_path)

    return unique_posts
