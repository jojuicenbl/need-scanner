"""Deduplication using hashing and fuzzy matching."""

import hashlib
from typing import List, Set
from loguru import logger
from rapidfuzz import fuzz

from ..schemas import Post


def compute_hash(post: Post) -> str:
    """Compute hash from post ID and permalink."""
    key = f"{post.id}:{post.permalink}"
    return hashlib.md5(key.encode()).hexdigest()


def is_fuzzy_duplicate(title1: str, title2: str, threshold: int = 90) -> bool:
    """Check if two titles are fuzzy duplicates."""
    ratio = fuzz.ratio(title1.lower(), title2.lower())
    return ratio >= threshold


def dedupe(posts: List[Post], fuzzy_threshold: int = 90) -> List[Post]:
    """
    Deduplicate posts using exact hash and fuzzy title matching.

    Args:
        posts: List of posts to deduplicate
        fuzzy_threshold: Fuzzy matching threshold (0-100)

    Returns:
        Deduplicated list of posts
    """
    logger.info(f"Deduplicating {len(posts)} posts...")

    seen_hashes: Set[str] = set()
    seen_titles: List[str] = []
    unique_posts: List[Post] = []

    for post in posts:
        # Check exact hash
        post_hash = compute_hash(post)
        if post_hash in seen_hashes:
            continue

        # Check fuzzy title match
        is_duplicate = False
        for seen_title in seen_titles:
            if is_fuzzy_duplicate(post.title, seen_title, fuzzy_threshold):
                is_duplicate = True
                break

        if is_duplicate:
            continue

        # Keep this post
        seen_hashes.add(post_hash)
        seen_titles.append(post.title)
        unique_posts.append(post)

    removed = len(posts) - len(unique_posts)
    logger.info(f"Removed {removed} duplicates, kept {len(unique_posts)} unique posts")

    return unique_posts
