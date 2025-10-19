"""RSS feed fetcher for blogs and Indie Hackers."""

import time
import requests
import feedparser
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


USER_AGENT = "need_scanner/0.2.0 (market discovery tool)"


def fetch_rss(
    feed_urls: List[str],
    days: int = 30,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch posts from RSS feeds.

    Args:
        feed_urls: List of RSS feed URLs
        days: Look back N days
        output_dir: Directory to save raw JSON

    Returns:
        List of Post objects
    """
    since_dt = datetime.now() - timedelta(days=days)
    all_posts = []

    logger.info(f"Fetching from {len(feed_urls)} RSS feeds (last {days} days)...")

    for feed_url in feed_urls:
        try:
            logger.info(f"Fetching: {feed_url}")

            # Parse feed
            feed = feedparser.parse(feed_url, agent=USER_AGENT)

            if feed.bozo and feed.bozo_exception:
                logger.warning(f"Feed parsing warning: {feed.bozo_exception}")

            entries = feed.entries
            logger.info(f"  Found {len(entries)} entries")

            for entry in entries:
                try:
                    # Parse date
                    published_dt = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_dt = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        published_dt = datetime(*entry.updated_parsed[:6])

                    # Filter by date
                    if published_dt and published_dt < since_dt:
                        continue

                    # Extract data
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    description = entry.get('description', '') or entry.get('summary', '')

                    # Create unique ID from link
                    rss_id = f"rss_{hash(link) & 0xffffffff}"

                    post = Post(
                        id=rss_id,
                        source="rss",
                        title=title,
                        body=description,
                        created_ts=published_dt.timestamp() if published_dt else None,
                        url=link,
                        score=0,  # RSS doesn't have scores
                        comments_count=0,
                        raw=dict(entry)
                    )
                    all_posts.append(post)

                except Exception as e:
                    logger.warning(f"Failed to parse RSS entry: {e}")

            # Respect rate limits
            time.sleep(1.0)

        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {feed_url}: {e}")
            continue

    logger.info(f"Successfully fetched {len(all_posts)} posts from RSS feeds")

    # Save raw data
    if output_dir and all_posts:
        output_dir = Path(output_dir)
        ensure_dir(output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"posts_rss_{timestamp}.json"

        # Convert to serializable format
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
                "raw": {}  # Don't save full raw to reduce size
            }
            for p in all_posts
        ]

        write_json(output_path, posts_data)

    return all_posts


def load_feed_urls_from_file(path: Path) -> List[str]:
    """Load RSS feed URLs from a text file (one per line)."""
    feeds = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                feeds.append(line)
    logger.info(f"Loaded {len(feeds)} RSS feed URLs from {path}")
    return feeds
