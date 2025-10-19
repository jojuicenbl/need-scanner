"""Stack Exchange question fetcher using public API."""

import time
import requests
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


def fetch_stackexchange(
    sites: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    days: int = 7,
    min_score: int = 5,
    limit_per_site: int = 100,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch questions from Stack Exchange sites using public API.

    Args:
        sites: List of site names (e.g., ['stackoverflow', 'softwareengineering'])
        tags: List of tags to filter (optional)
        days: Look back N days
        min_score: Minimum question score
        limit_per_site: Maximum questions per site
        output_dir: Directory to save raw JSON (optional)

    Returns:
        List of Post objects

    Example sites:
    - stackoverflow: General programming
    - softwareengineering: Software design/architecture
    - startups: Startup questions
    - workplace: Professional workplace questions
    - freelancing: Freelancing questions
    """
    # Default sites
    if sites is None:
        sites = [
            "stackoverflow",
            "softwareengineering",
            "startups",
            "workplace",
            "freelancing"
        ]

    # API endpoint
    base_url = "https://api.stackexchange.com/2.3/questions"

    # Calculate timestamp
    from_date = int((datetime.now() - timedelta(days=days)).timestamp())

    logger.info(f"Fetching from {len(sites)} Stack Exchange sites (last {days} days)...")

    all_posts = []

    for site in sites:
        logger.info(f"Fetching from {site}...")

        # Build parameters
        params = {
            "site": site,
            "fromdate": from_date,
            "sort": "votes",
            "order": "desc",
            "pagesize": min(limit_per_site, 100),  # API max
            "filter": "withbody",  # Include question body
            "min": min_score
        }

        if tags:
            params["tagged"] = ";".join(tags)

        try:
            response = requests.get(base_url, params=params, timeout=30)

            # Handle rate limiting
            if response.status_code == 429:
                logger.warning(f"Rate limited on {site}, skipping...")
                continue

            if response.status_code != 200:
                logger.error(f"HTTP {response.status_code} for {site}")
                continue

            data = response.json()

            # Check for API errors
            if "error_id" in data:
                logger.error(f"API error for {site}: {data.get('error_message')}")
                continue

            questions = data.get("items", [])
            logger.info(f"  Retrieved {len(questions)} questions from {site}")

            # Convert to Post objects
            for q in questions:
                # Truncate body if too long
                body = q.get("body_markdown", q.get("body", ""))
                if len(body) > 1000:
                    body = body[:1000] + "..."

                post = Post(
                    id=f"se_{site}_{q.get('question_id')}",
                    source="se",  # Stack Exchange
                    title=q.get("title", ""),
                    body=body,
                    created_ts=q.get("creation_date"),
                    url=q.get("link"),
                    score=q.get("score", 0),
                    comments_count=q.get("answer_count", 0),  # Use answer count
                    raw={
                        "question_id": q.get("question_id"),
                        "site": site,
                        "title": q.get("title"),
                        "score": q.get("score"),
                        "answer_count": q.get("answer_count"),
                        "view_count": q.get("view_count"),
                        "tags": q.get("tags", []),
                        "owner": q.get("owner", {}),
                        "is_answered": q.get("is_answered", False),
                        "accepted_answer_id": q.get("accepted_answer_id")
                    }
                )

                all_posts.append(post)

            # Respect rate limits (30 requests/sec)
            time.sleep(0.1)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {site}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error for {site}: {e}")
            continue

    logger.info(f"Successfully fetched {len(all_posts)} total questions")

    # Save raw data
    if output_dir and all_posts:
        output_dir = Path(output_dir)
        ensure_dir(output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"posts_stackexchange_{timestamp}.json"

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
        logger.info(f"Saved Stack Exchange questions to {output_path}")

    return all_posts


def load_sites_from_file(path: Path) -> List[str]:
    """Load Stack Exchange site names from a config file."""
    sites = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                sites.append(line)

    logger.info(f"Loaded {len(sites)} Stack Exchange sites from {path}")
    return sites
