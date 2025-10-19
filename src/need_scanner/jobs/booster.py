"""Daily trend booster - fetch hot trending content from multiple sources."""

import time
from typing import List, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger

from ..schemas import Post
from ..fetchers.reddit import fetch_multiple_subreddits
from ..fetchers.indiehackers import fetch_indiehackers
from ..fetchers.nitter_rss import fetch_nitter_multiple_queries
from ..utils import write_json, ensure_dir


# Default hot subreddits for trend detection
DEFAULT_HOT_SUBREDDITS = [
    "Entrepreneur",
    "smallbusiness",
    "SaaS",
    "startups",
    "webdev",
    "freelance",
    "productivity",
    "marketing"
]

# Default Nitter queries for trending pain points
DEFAULT_NITTER_QUERIES = [
    "alternative to",
    "pricing too high",
    "can't find software"
]


def run_daily_booster(
    output_dir: Path = Path("data/incoming"),
    hot_subreddits: Optional[List[str]] = None,
    nitter_queries: Optional[List[str]] = None,
    min_score: int = 5,
    limit_per_sub: int = 10
) -> List[Post]:
    """
    Morning booster: fetch hot trending content from multiple sources.

    This function is designed to run daily (e.g., via cron or GitHub Actions)
    to capture trending topics and fresh pain points.

    Sources:
    - Reddit hot posts (5-8 dynamic subreddits)
    - IndieHackers RSS
    - Nitter RSS (2-3 trending queries)

    Args:
        output_dir: Directory to save booster results
        hot_subreddits: List of subreddits to fetch from (hot mode)
        nitter_queries: List of Nitter search queries
        min_score: Minimum score threshold for posts
        limit_per_sub: Posts per subreddit

    Returns:
        List of Post objects from all sources
    """
    logger.info("=" * 60)
    logger.info("DAILY TREND BOOSTER")
    logger.info("=" * 60)

    all_posts = []

    # Use defaults if not provided
    subreddits = hot_subreddits or DEFAULT_HOT_SUBREDDITS
    queries = nitter_queries or DEFAULT_NITTER_QUERIES

    # 1. Reddit hot posts
    logger.info(f"\n[1/3] Fetching Reddit hot posts from {len(subreddits)} subreddits...")
    try:
        reddit_posts = fetch_multiple_subreddits(
            subreddits=subreddits,
            limit_per_sub=limit_per_sub,
            mode="hot",
            sleep_between_subs=1.5
        )

        # Filter by min score
        reddit_filtered = [p for p in reddit_posts if (p.score or 0) >= min_score]
        all_posts.extend(reddit_filtered)
        logger.info(f"✓ Collected {len(reddit_filtered)} hot posts from Reddit (min_score={min_score})")

    except Exception as e:
        logger.error(f"Failed to fetch Reddit hot posts: {e}")

    # 2. IndieHackers RSS
    logger.info(f"\n[2/3] Fetching IndieHackers RSS...")
    try:
        ih_posts = fetch_indiehackers(days=7)
        all_posts.extend(ih_posts)
        logger.info(f"✓ Collected {len(ih_posts)} posts from IndieHackers")

    except Exception as e:
        logger.error(f"Failed to fetch IndieHackers: {e}")

    # 3. Nitter trending queries
    logger.info(f"\n[3/3] Fetching Nitter RSS for {len(queries)} trending queries...")
    try:
        nitter_posts = fetch_nitter_multiple_queries(
            queries=queries,
            days=3,
            sleep_between=2.0
        )
        all_posts.extend(nitter_posts)
        logger.info(f"✓ Collected {len(nitter_posts)} tweets from Nitter")

    except Exception as e:
        logger.error(f"Failed to fetch Nitter: {e}")

    logger.info(f"\n✓ Total booster posts: {len(all_posts)}")

    # Save to output
    if all_posts:
        ensure_dir(output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"booster_{timestamp}.json"

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
            for p in all_posts
        ]

        write_json(output_path, posts_data)
        logger.info(f"\n✓ Saved booster posts to: {output_path}")

    logger.info("\n" + "=" * 60)
    logger.info("BOOSTER COMPLETE")
    logger.info("=" * 60)

    return all_posts


def main():
    """CLI entry point for booster job."""
    import sys
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

    posts = run_daily_booster()

    if posts:
        logger.info(f"\nBooster successful: {len(posts)} posts collected")
        return 0
    else:
        logger.warning("\nBooster returned no posts")
        return 1


if __name__ == "__main__":
    exit(main())
