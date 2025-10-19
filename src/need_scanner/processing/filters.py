"""Filtering utilities for posts (language detection, intent, etc.)."""

from typing import List, Optional
from loguru import logger
from langdetect import detect, LangDetectException

from ..schemas import Post


def detect_language(text: str) -> Optional[str]:
    """
    Detect the language of a text.

    Args:
        text: Text to analyze

    Returns:
        ISO 639-1 language code (e.g., "en", "fr") or None if detection fails
    """
    if not text or len(text.strip()) < 10:
        return None

    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        return None


def tag_language(post: Post) -> str:
    """
    Detect and tag the language of a post.

    Args:
        post: Post object

    Returns:
        Language code (or "unknown" if detection fails)
    """
    # Combine title and body for better detection
    text = f"{post.title} {post.body}".strip()

    lang = detect_language(text)

    if lang is None:
        lang = "unknown"

    return lang


def filter_by_language(
    posts: List[Post],
    allowed_languages: List[str] = None,
    tag_all: bool = True
) -> List[Post]:
    """
    Tag and optionally filter posts by language.

    Args:
        posts: List of posts
        allowed_languages: List of language codes to keep (e.g., ["en", "fr"]).
                          If None, all posts are kept but still tagged.
        tag_all: Whether to tag all posts with language (even if filtered out)

    Returns:
        Filtered list of posts with lang field populated
    """
    if allowed_languages is None:
        allowed_languages = []  # Keep all if not specified

    logger.info(f"Detecting language for {len(posts)} posts...")
    if allowed_languages:
        logger.info(f"Filtering for languages: {allowed_languages}")
    else:
        logger.info("No language filtering (tagging only)")

    filtered_posts = []
    lang_counts = {}

    for post in posts:
        lang = tag_language(post)
        post.lang = lang

        # Count languages
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # Filter by allowed languages
        if not allowed_languages or lang in allowed_languages:
            filtered_posts.append(post)

    logger.info(f"Language distribution: {lang_counts}")
    if allowed_languages:
        logger.info(f"Kept {len(filtered_posts)}/{len(posts)} posts with languages: {allowed_languages}")
    else:
        logger.info(f"All {len(posts)} posts tagged with language")

    return filtered_posts


def filter_by_score(
    posts: List[Post],
    min_score: int = 0
) -> List[Post]:
    """
    Filter posts by minimum score/upvotes.

    Args:
        posts: List of posts
        min_score: Minimum score threshold

    Returns:
        Filtered list of posts
    """
    if min_score <= 0:
        return posts

    filtered_posts = [p for p in posts if (p.score or 0) >= min_score]

    logger.info(f"Filtered by min_score={min_score}: {len(filtered_posts)}/{len(posts)} posts kept")

    return filtered_posts


def filter_by_comments(
    posts: List[Post],
    min_comments: int = 0
) -> List[Post]:
    """
    Filter posts by minimum comment count.

    Args:
        posts: List of posts
        min_comments: Minimum comment count threshold

    Returns:
        Filtered list of posts
    """
    if min_comments <= 0:
        return posts

    filtered_posts = [p for p in posts if (p.comments_count or 0) >= min_comments]

    logger.info(f"Filtered by min_comments={min_comments}: {len(filtered_posts)}/{len(posts)} posts kept")

    return filtered_posts
