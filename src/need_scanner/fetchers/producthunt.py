"""Product Hunt post/comment fetcher using GraphQL API."""

import time
import requests
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


def fetch_producthunt(
    api_token: Optional[str] = None,
    days: int = 7,
    categories: Optional[List[str]] = None,
    limit: int = 100,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch posts from Product Hunt using GraphQL API.

    NOTE: Product Hunt API requires authentication. This function provides
    a skeleton that can be implemented once API credentials are available.

    Args:
        api_token: Product Hunt API token (required for API access)
        days: Look back N days
        categories: List of categories to filter (optional)
        limit: Maximum posts to fetch
        output_dir: Directory to save raw JSON (optional)

    Returns:
        List of Post objects

    To get API access:
    1. Go to https://www.producthunt.com/v2/oauth/applications
    2. Create a new application
    3. Get your API token
    4. Set PRODUCTHUNT_API_TOKEN environment variable

    Categories examples: ['developer-tools', 'productivity', 'saas', 'artificial-intelligence']
    """
    if api_token is None:
        logger.warning("=" * 70)
        logger.warning("Product Hunt API token not provided")
        logger.warning("=" * 70)
        logger.warning("Product Hunt requires API authentication.")
        logger.warning("")
        logger.warning("To enable Product Hunt collection:")
        logger.warning("  1. Go to: https://www.producthunt.com/v2/oauth/applications")
        logger.warning("  2. Create a new application")
        logger.warning("  3. Get your API token")
        logger.warning("  4. Add to .env: PRODUCTHUNT_API_TOKEN=your_token")
        logger.warning("=" * 70)
        logger.info(f"Would fetch posts from last {days} days with limit {limit}")
        if categories:
            logger.info(f"Categories filter: {categories}")
        logger.info("Returning empty result set for now.")
        return []

    # GraphQL endpoint
    url = "https://api.producthunt.com/v2/api/graphql"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    # Calculate date range
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    logger.info(f"Fetching Product Hunt posts from last {days} days...")

    # GraphQL query for posts
    query = """
    query GetPosts($postedAfter: DateTime!, $first: Int!) {
      posts(postedAfter: $postedAfter, first: $first, order: VOTES) {
        edges {
          node {
            id
            name
            tagline
            description
            votesCount
            commentsCount
            url
            createdAt
            topics {
              edges {
                node {
                  name
                }
              }
            }
            comments(first: 5, order: VOTES) {
              edges {
                node {
                  id
                  body
                  votesCount
                  createdAt
                  user {
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    variables = {
        "postedAfter": since_date,
        "first": min(limit, 100)  # API limit per request
    }

    try:
        response = requests.post(
            url,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"Product Hunt API error: {response.status_code}")
            logger.error(f"Response: {response.text[:200]}")
            return []

        data = response.json()

        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return []

        posts_data = data.get("data", {}).get("posts", {}).get("edges", [])
        logger.info(f"Retrieved {len(posts_data)} posts from Product Hunt")

        posts = []
        for edge in posts_data:
            node = edge.get("node", {})

            # Get topics/categories
            topics = [
                t["node"]["name"]
                for t in node.get("topics", {}).get("edges", [])
            ]

            # Filter by category if specified
            if categories:
                if not any(cat.lower() in [t.lower() for t in topics] for cat in categories):
                    continue

            # Combine description and top comments for context
            description = node.get("description", "")
            comments = node.get("comments", {}).get("edges", [])
            top_comments = "\n".join([
                f"Comment: {c['node']['body'][:200]}"
                for c in comments[:3]
            ])

            body = f"{description}\n\nTop Comments:\n{top_comments}" if top_comments else description

            # Create Post object
            post = Post(
                id=f"ph_{node.get('id')}",
                source="ph",  # Product Hunt
                title=f"{node.get('name', '')} - {node.get('tagline', '')}",
                body=body,
                created_ts=int(datetime.fromisoformat(node.get("createdAt").replace("Z", "+00:00")).timestamp()),
                url=node.get("url"),
                score=node.get("votesCount", 0),
                comments_count=node.get("commentsCount", 0),
                raw={
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "tagline": node.get("tagline"),
                    "description": description,
                    "votes": node.get("votesCount"),
                    "comments": node.get("commentsCount"),
                    "url": node.get("url"),
                    "created_at": node.get("createdAt"),
                    "topics": topics,
                    "top_comments": [c["node"] for c in comments[:3]]
                }
            )

            posts.append(post)

        logger.info(f"Parsed {len(posts)} posts from Product Hunt")

        # Save raw data
        if output_dir and posts:
            output_dir = Path(output_dir)
            ensure_dir(output_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"posts_producthunt_{timestamp}.json"

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
                for p in posts
            ]

            write_json(output_path, posts_data)
            logger.info(f"Saved Product Hunt posts to {output_path}")

        return posts

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return []


def load_categories_from_file(path: Path) -> List[str]:
    """Load Product Hunt categories from a config file."""
    categories = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                categories.append(line)

    logger.info(f"Loaded {len(categories)} Product Hunt categories from {path}")
    return categories
