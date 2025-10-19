"""IndieHackers RSS feed fetcher."""

import time
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import feedparser
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


def fetch_indiehackers(
    days: int = 14,
    sleep: float = 0.5,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch posts from IndieHackers RSS feed.

    Args:
        days: Look back N days
        sleep: Sleep between requests (not used for single feed, but kept for consistency)
        output_dir: Directory to save raw JSON (optional)

    Returns:
        List of Post objects
    """
    url = "https://www.indiehackers.com/feed.xml"

    logger.info(f"Fetching IndieHackers feed (last {days} days)...")

    try:
        # Parse feed
        feed = feedparser.parse(url)

        if not feed.entries:
            logger.warning("No entries found in IndieHackers feed")
            return []

        posts = []
        cutoff = time.time() - (days * 86400)

        for entry in feed.entries:
            # Parse timestamp
            ts = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                ts = time.mktime(entry.published_parsed)

            # Filter by date
            if ts and ts < cutoff:
                continue

            # Extract content
            title = entry.get('title', '')[:300]
            body = (entry.get('summary', '') or entry.get('description', ''))[:5000]
            link = entry.get('link', '')

            # Create Post
            post = Post(
                id=f"ih_{hash(link)}",
                source="rss",  # Or create new source "indiehackers"
                title=title,
                body=body,
                created_ts=ts,
                url=link,
                score=None,
                comments_count=None,
                lang=None,
                raw={'feed': 'indiehackers', 'entry': entry}
            )
            posts.append(post)

        logger.info(f"✓ Fetched {len(posts)} posts from IndieHackers")

        # Save raw data
        if output_dir and posts:
            output_dir = Path(output_dir)
            ensure_dir(output_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"posts_indiehackers_{timestamp}.json"

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
                    "raw": {}  # Don't save full raw data
                }
                for p in posts
            ]

            write_json(output_path, posts_data)
            logger.info(f"Saved raw posts to {output_path}")

        return posts

    except Exception as e:
        logger.error(f"Failed to fetch IndieHackers feed: {e}")
        return []
