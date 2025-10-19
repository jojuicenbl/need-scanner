"""Twitter/X post fetcher.

NOTE: Twitter/X scraping has become more restricted. Options:
1. Official Twitter API v2 (requires API keys - recommended for production)
2. snscrape (has Python 3.13 compatibility issues)
3. Alternative: nitter instances or other tools

For now, this module provides a skeleton that can be implemented with:
- Twitter API v2 (tweepy library)
- Manual CSV import from Twitter Advanced Search
- Alternative scraping tools

TODO: Implement with Twitter API v2 once credentials are available.
"""

import time
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


def fetch_twitter_search(
    queries: Optional[List[str]] = None,
    days: int = 7,
    min_likes: int = 5,
    min_retweets: int = 2,
    limit_per_query: int = 100,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch tweets matching search queries.

    NOTE: This function is currently a stub. Twitter/X scraping requires:
    - Twitter API v2 credentials (recommended), OR
    - Alternative scraping solution compatible with Python 3.13

    Args:
        queries: List of search queries (Twitter search syntax)
        days: Look back N days
        min_likes: Minimum likes threshold
        min_retweets: Minimum retweets threshold
        limit_per_query: Maximum tweets per query
        output_dir: Directory to save raw JSON (optional)

    Returns:
        Empty list (stub implementation)

    Example queries:
        - "need help" OR "struggling with" lang:en
        - "looking for solution" OR "how do I" lang:en
        - "pain point" OR "frustrated" lang:en
        - "besoin d'aide" OR "cherche solution" lang:fr

    TODO: Implement with Twitter API v2 (tweepy) once credentials are available.
          See config/twitter_queries.txt for pre-configured queries.
    """
    logger.warning("=" * 70)
    logger.warning("Twitter/X collection is not yet implemented")
    logger.warning("Reasons:")
    logger.warning("  1. snscrape has Python 3.13 compatibility issues")
    logger.warning("  2. Twitter API v2 requires authentication (API keys)")
    logger.warning("=" * 70)
    logger.warning("Options to enable Twitter collection:")
    logger.warning("  1. Get Twitter API v2 credentials and implement with tweepy")
    logger.warning("  2. Use Twitter Advanced Search + manual CSV export")
    logger.warning("  3. Downgrade to Python 3.11 to use snscrape")
    logger.warning("=" * 70)
    logger.info("Queries that would have been used:")

    # Default queries focused on pain points
    if queries is None:
        queries = [
            '("need help" OR "struggling with" OR "how do I") lang:en',
            '("looking for" OR "does anyone know" OR "any recommendations") lang:en',
            '("frustrated" OR "annoying" OR "wish there was") lang:en',
            '("besoin d\'aide" OR "cherche solution" OR "comment faire") lang:fr'
        ]

    for i, query in enumerate(queries, 1):
        logger.info(f"  {i}. {query}")

    logger.info(f"\nWould have fetched up to {limit_per_query} tweets per query from last {days} days")
    logger.info("Returning empty result set for now.")

    return []


def load_queries_from_file(path: Path) -> List[str]:
    """Load Twitter search queries from a config file."""
    queries = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                queries.append(line)

    logger.info(f"Loaded {len(queries)} Twitter queries from {path}")
    return queries
