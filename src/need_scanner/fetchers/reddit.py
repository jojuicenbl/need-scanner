"""Reddit post fetcher using public JSON API."""

import time
import requests
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


USER_AGENT = "need_scanner/0.1.0 (research tool for pain point analysis)"


def fetch_subreddit_new(
    subreddit: str,
    limit: int = 200,
    sleep: float = 1.0,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch new posts from a subreddit using public JSON API.

    Args:
        subreddit: Subreddit name (without r/)
        limit: Maximum number of posts to fetch
        sleep: Sleep time between requests (seconds)
        output_dir: Directory to save raw JSON (optional)

    Returns:
        List of Post objects
    """
    posts = []
    after = None
    headers = {"User-Agent": USER_AGENT}

    logger.info(f"Fetching up to {limit} posts from r/{subreddit}/new...")

    while len(posts) < limit:
        # Build URL
        url = f"https://www.reddit.com/r/{subreddit}/new.json"
        params = {"limit": min(100, limit - len(posts))}
        if after:
            params["after"] = after

        try:
            # Make request
            response = requests.get(url, headers=headers, params=params, timeout=10)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            # Handle errors
            if response.status_code >= 400:
                logger.error(f"HTTP {response.status_code}: {response.text[:200]}")
                break

            # Parse response
            data = response.json()
            children = data.get("data", {}).get("children", [])

            if not children:
                logger.info("No more posts available")
                break

            # Convert to Post objects
            for child in children:
                post_data = child.get("data", {})
                try:
                    post = Post(
                        id=post_data.get("id", ""),
                        source="reddit",
                        title=post_data.get("title", ""),
                        selftext=post_data.get("selftext", ""),
                        created_utc=post_data.get("created_utc"),
                        permalink=f"https://reddit.com{post_data.get('permalink', '')}",
                        score=post_data.get("score", 0),
                        num_comments=post_data.get("num_comments", 0),
                        raw=post_data
                    )
                    posts.append(post)
                except Exception as e:
                    logger.warning(f"Failed to parse post {post_data.get('id')}: {e}")

            # Update pagination cursor
            after = data.get("data", {}).get("after")
            if not after:
                logger.info("Reached end of available posts")
                break

            logger.info(f"Fetched {len(posts)}/{limit} posts...")

            # Respect rate limits
            time.sleep(sleep)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break

    logger.info(f"Successfully fetched {len(posts)} posts from r/{subreddit}")

    # Save raw data
    if output_dir and posts:
        output_dir = Path(output_dir)
        ensure_dir(output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"posts_{subreddit}_{timestamp}.json"

        # Convert to serializable format
        posts_data = [
            {
                "id": p.id,
                "source": p.source,
                "title": p.title,
                "selftext": p.selftext,
                "created_utc": p.created_utc,
                "permalink": p.permalink,
                "score": p.score,
                "num_comments": p.num_comments,
                "raw": p.raw
            }
            for p in posts
        ]

        write_json(output_path, posts_data)
        logger.info(f"Saved raw posts to {output_path}")

    return posts


def load_posts_from_json(path: Path) -> List[Post]:
    """Load posts from a JSON file."""
    import json

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = []
    for item in data:
        try:
            posts.append(Post(**item))
        except Exception as e:
            logger.warning(f"Failed to parse post from JSON: {e}")

    logger.info(f"Loaded {len(posts)} posts from {path}")
    return posts
