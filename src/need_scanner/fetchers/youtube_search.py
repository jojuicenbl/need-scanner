"""YouTube search fetcher - extracts video metadata without API."""

import time
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


def fetch_youtube(
    query: str,
    max_results: int = 30,
    min_views: int = 10000,
    days: int = 30,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch YouTube video metadata via youtube-search-python.

    Note: This does not use the official YouTube API, so it has limitations:
    - No authentication required
    - Subject to rate limiting
    - Limited metadata (no exact publish dates in some cases)

    Args:
        query: Search query (e.g., "alternative to Notion", "pricing problem SaaS")
        max_results: Maximum number of videos to fetch
        min_views: Minimum view count threshold
        days: Look back N days (limited support - best effort)
        output_dir: Directory to save raw JSON (optional)

    Returns:
        List of Post objects
    """
    try:
        from youtube_search import YoutubeSearch
    except ImportError:
        logger.error(
            "youtube-search-python not installed. "
            "Install with: pip install youtube-search-python"
        )
        return []

    logger.info(f"Searching YouTube for: '{query}' (max {max_results} results)")

    try:
        # Perform search
        search = YoutubeSearch(query, max_results=max_results)
        results = search.to_dict()

        if not results:
            logger.warning(f"No YouTube results found for '{query}'")
            return []

        posts = []
        cutoff = time.time() - (days * 86400)

        for video in results:
            # Extract metadata
            title = video.get('title', '')[:300]
            video_id = video.get('id', '')
            channel = video.get('channel', '')
            duration = video.get('duration', '')
            views_str = video.get('views', '0')

            # Parse view count (format: "1,234,567 views" or "1.2M views")
            views = 0
            try:
                views_clean = views_str.replace(',', '').replace('.', '').split()[0]
                if 'K' in views_str:
                    views = int(float(views_clean) * 1000)
                elif 'M' in views_str:
                    views = int(float(views_clean) * 1000000)
                else:
                    views = int(views_clean) if views_clean.isdigit() else 0
            except (ValueError, IndexError):
                views = 0

            # Skip videos with too few views
            if views < min_views:
                continue

            # Build description from available metadata
            description = f"Channel: {channel} | Duration: {duration} | Views: {views_str}"

            # YouTube URL
            url = f"https://www.youtube.com/watch?v={video_id}"

            # Note: youtube-search-python doesn't provide exact timestamps
            # We can't accurately filter by date, so we include all results
            # and rely on view count as a proxy for relevance

            # Create Post
            post = Post(
                id=f"yt_{video_id}",
                source="rss",  # Or create new source "youtube"
                title=title,
                body=description,
                created_ts=None,  # Not available from this library
                url=url,
                score=views,  # Use view count as score
                comments_count=None,
                lang=None,
                raw={'query': query, 'video': video}
            )
            posts.append(post)

        logger.info(f"✓ Fetched {len(posts)} YouTube videos (with >= {min_views} views)")

        # Save raw data
        if output_dir and posts:
            output_dir = Path(output_dir)
            ensure_dir(output_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = query.replace(' ', '_')[:30]
            output_path = output_dir / f"posts_youtube_{safe_query}_{timestamp}.json"

            posts_data = [
                {
                    "id": p.id,
                    "source": p.source,
                    "title": p.title,
                    "body": p.body,
                    "created_ts": p.created_ts,
                    "url": p.url,
                    "score": p.score,
                    "comments_count": p.comments_count,
                    "lang": p.lang,
                    "raw": {}
                }
                for p in posts
            ]

            write_json(output_path, posts_data)
            logger.info(f"Saved raw posts to {output_path}")

        return posts

    except Exception as e:
        logger.error(f"Failed to search YouTube: {e}")
        return []


def fetch_youtube_multiple_queries(
    queries: List[str],
    max_results_per_query: int = 20,
    min_views: int = 10000,
    days: int = 30,
    sleep_between: float = 2.0,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch YouTube videos for multiple search queries.

    Args:
        queries: List of search queries
        max_results_per_query: Max results per query
        min_views: Minimum view count threshold
        days: Look back N days
        sleep_between: Sleep between queries (seconds)
        output_dir: Directory to save raw JSON (optional)

    Returns:
        Combined list of Post objects
    """
    all_posts = []

    for i, query in enumerate(queries, 1):
        logger.info(f"[{i}/{len(queries)}] YouTube query: '{query}'")

        posts = fetch_youtube(
            query=query,
            max_results=max_results_per_query,
            min_views=min_views,
            days=days,
            output_dir=output_dir
        )

        all_posts.extend(posts)

        # Sleep between queries to avoid rate limiting
        if i < len(queries):
            logger.debug(f"Sleeping {sleep_between}s before next query...")
            time.sleep(sleep_between)

    logger.info(f"✓ Total: {len(all_posts)} videos from {len(queries)} queries")

    return all_posts
