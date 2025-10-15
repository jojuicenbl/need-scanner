"""Hacker News fetcher using Algolia API."""

import time
import requests
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


USER_AGENT = "need_scanner/0.2.0 (market discovery tool)"

# HN Algolia API
HN_API_BASE = "https://hn.algolia.com/api/v1"


def fetch_ask_hn(
    queries: List[str] = None,
    min_points: int = 20,
    days: int = 30,
    limit: int = 100,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch Ask HN posts using Algolia API.

    Args:
        queries: List of query strings (default: need/tool-related queries)
        min_points: Minimum points threshold
        days: Look back N days
        limit: Maximum posts per query
        output_dir: Directory to save raw JSON

    Returns:
        List of Post objects
    """
    if queries is None:
        queries = [
            "Ask HN",
            "How do you",
            "What do you use",
            "Anyone using",
            "I built"
        ]

    # Calculate timestamp filter
    since_ts = int((datetime.now() - timedelta(days=days)).timestamp())

    all_posts = []
    headers = {"User-Agent": USER_AGENT}

    logger.info(f"Fetching Ask HN posts from last {days} days (min {min_points} points)...")

    for query in queries:
        logger.info(f"Query: '{query}'")

        try:
            # Build API request
            params = {
                "query": query,
                "tags": "story",
                "numericFilters": f"points>{min_points},created_at_i>{since_ts}",
                "hitsPerPage": min(limit, 100)
            }

            response = requests.get(
                f"{HN_API_BASE}/search_by_date",
                params=params,
                headers=headers,
                timeout=10
            )

            if response.status_code >= 400:
                logger.error(f"HTTP {response.status_code}: {response.text[:200]}")
                continue

            data = response.json()
            hits = data.get("hits", [])

            logger.info(f"  Found {len(hits)} posts")

            # Convert to Post objects
            for hit in hits:
                try:
                    # Build post text
                    title = hit.get("title", "")
                    story_text = hit.get("story_text") or ""

                    # HN IDs are integers
                    hn_id = str(hit.get("objectID", ""))

                    post = Post(
                        id=f"hn_{hn_id}",
                        source="hn",
                        title=title,
                        body=story_text,
                        created_ts=float(hit.get("created_at_i", 0)),
                        url=f"https://news.ycombinator.com/item?id={hn_id}",
                        score=hit.get("points", 0),
                        comments_count=hit.get("num_comments", 0),
                        raw=hit
                    )
                    all_posts.append(post)

                except Exception as e:
                    logger.warning(f"Failed to parse HN post {hit.get('objectID')}: {e}")

            # Respect rate limits
            time.sleep(1.0)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for query '{query}': {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error for query '{query}': {e}")
            continue

    logger.info(f"Successfully fetched {len(all_posts)} posts from Hacker News")

    # Save raw data
    if output_dir and all_posts:
        output_dir = Path(output_dir)
        ensure_dir(output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"posts_hn_{timestamp}.json"

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
                "raw": p.raw
            }
            for p in all_posts
        ]

        write_json(output_path, posts_data)

    return all_posts


def load_posts_from_json(path: Path) -> List[Post]:
    """Load HN posts from a JSON file."""
    import json

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = []
    for item in data:
        try:
            posts.append(Post(**item))
        except Exception as e:
            logger.warning(f"Failed to parse post from JSON: {e}")

    logger.info(f"Loaded {len(posts)} HN posts from {path}")
    return posts
