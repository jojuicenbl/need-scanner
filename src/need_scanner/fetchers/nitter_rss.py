"""Nitter RSS feed fetcher - Twitter/X scraping via Nitter instances."""

import time
import urllib.parse
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import feedparser
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


# List of public Nitter instances (some may be down, we'll try multiple)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
]


def fetch_nitter_search(
    query: str,
    days: int = 7,
    nitter_instance: Optional[str] = None,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch tweets via Nitter RSS search.

    Note: Nitter is subject to rate limiting and instance availability.
    This is a best-effort scraper without official API access.

    Args:
        query: Search query (e.g., 'alternative to', 'pricing too high')
        days: Look back N days
        nitter_instance: Specific Nitter instance to use (optional)
        output_dir: Directory to save raw JSON (optional)

    Returns:
        List of Post objects
    """
    # Use provided instance or try defaults
    instances_to_try = [nitter_instance] if nitter_instance else NITTER_INSTANCES

    logger.info(f"Searching Nitter for: '{query}' (last {days} days)")

    for instance in instances_to_try:
        if not instance:
            continue

        try:
            # Build search URL
            encoded_query = urllib.parse.quote(query)
            url = f"{instance}/search/rss?f=tweets&q={encoded_query}"

            logger.debug(f"Trying Nitter instance: {instance}")

            # Parse feed
            feed = feedparser.parse(url)

            if not feed.entries:
                logger.debug(f"No entries from {instance}, trying next...")
                continue

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
                    id=f"ntr_{hash(link)}",
                    source="x",  # Use existing "x" source for Twitter/X
                    title=title,
                    body=body,
                    created_ts=ts,
                    url=link,
                    score=None,  # Nitter RSS doesn't provide engagement metrics
                    comments_count=None,
                    lang=None,
                    raw={'query': query, 'nitter_instance': instance}
                )
                posts.append(post)

            logger.info(f"✓ Fetched {len(posts)} tweets from Nitter ({instance})")

            # Save raw data
            if output_dir and posts:
                output_dir = Path(output_dir)
                ensure_dir(output_dir)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_query = query.replace(' ', '_')[:30]
                output_path = output_dir / f"posts_nitter_{safe_query}_{timestamp}.json"

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
            logger.warning(f"Failed to fetch from {instance}: {e}")
            continue

    logger.error("All Nitter instances failed or returned no results")
    return []


def fetch_nitter_multiple_queries(
    queries: List[str],
    days: int = 7,
    sleep_between: float = 2.0,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch tweets for multiple search queries.

    Args:
        queries: List of search queries
        days: Look back N days
        sleep_between: Sleep between queries (seconds)
        output_dir: Directory to save raw JSON (optional)

    Returns:
        Combined list of Post objects
    """
    all_posts = []

    for i, query in enumerate(queries, 1):
        logger.info(f"[{i}/{len(queries)}] Fetching Nitter query: '{query}'")

        posts = fetch_nitter_search(
            query=query,
            days=days,
            output_dir=output_dir
        )

        all_posts.extend(posts)

        # Sleep between queries to avoid rate limiting
        if i < len(queries):
            logger.debug(f"Sleeping {sleep_between}s before next query...")
            time.sleep(sleep_between)

    logger.info(f"✓ Total: {len(all_posts)} tweets from {len(queries)} queries")

    return all_posts
