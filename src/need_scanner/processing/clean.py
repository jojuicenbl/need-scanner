"""Text cleaning and normalization."""

import re
from typing import List
from loguru import logger

from ..schemas import Post


def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespaces into single space."""
    return re.sub(r'\s+', ' ', text).strip()


def normalize_post(post: Post, max_selftext_chars: int = 2000) -> Post:
    """
    Normalize a single post.

    Args:
        post: Post to normalize
        max_selftext_chars: Maximum characters for selftext

    Returns:
        Normalized Post
    """
    # Clean title
    title = normalize_whitespace(post.title)

    # Clean and truncate selftext
    selftext = normalize_whitespace(post.selftext)
    if len(selftext) > max_selftext_chars:
        selftext = selftext[:max_selftext_chars]

    # Create new post with cleaned data
    return Post(
        id=post.id,
        source=post.source,
        title=title,
        selftext=selftext,
        created_utc=post.created_utc,
        permalink=post.permalink,
        score=post.score,
        num_comments=post.num_comments,
        raw=post.raw
    )


def normalize(posts: List[Post], max_selftext_chars: int = 2000) -> List[Post]:
    """
    Normalize a list of posts.

    Args:
        posts: List of posts to normalize
        max_selftext_chars: Maximum characters for selftext

    Returns:
        List of normalized posts
    """
    logger.info(f"Normalizing {len(posts)} posts...")

    normalized = [normalize_post(p, max_selftext_chars) for p in posts]

    logger.info(f"Normalized {len(normalized)} posts")
    return normalized
