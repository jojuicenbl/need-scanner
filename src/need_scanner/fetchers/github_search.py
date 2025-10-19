"""GitHub repository search fetcher - finds alternative/open-source projects."""

import time
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import requests
from loguru import logger

from ..schemas import Post
from ..utils import write_json, ensure_dir


def fetch_github_alternatives(
    query: str = "alternative",
    topics: Optional[List[str]] = None,
    max_results: int = 30,
    min_stars: int = 10,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch GitHub repositories using search API.

    Useful for finding open-source alternatives and trending projects.

    Args:
        query: Search query (e.g., "alternative", "saas", "open source")
        topics: GitHub topics to filter by (e.g., ["saas", "productivity"])
        max_results: Maximum number of repositories to fetch
        min_stars: Minimum star count threshold
        output_dir: Directory to save raw JSON (optional)

    Returns:
        List of Post objects

    Note: GitHub API has rate limits:
    - Authenticated: 5,000 requests/hour
    - Unauthenticated: 60 requests/hour
    """
    logger.info(f"Searching GitHub for: '{query}' (max {max_results} results)")

    # Build search query
    search_query = query
    if topics:
        topic_str = '+'.join([f"topic:{t}" for t in topics])
        search_query = f"{query}+{topic_str}"

    # API endpoint
    url = "https://api.github.com/search/repositories"
    params = {
        "q": search_query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(max_results, 100)  # GitHub max is 100 per page
    }

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "need-scanner/0.1.0"
    }

    try:
        # Make request
        response = requests.get(url, params=params, headers=headers, timeout=10)

        # Check rate limit
        rate_remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
        logger.debug(f"GitHub API rate limit remaining: {rate_remaining}")

        response.raise_for_status()

        data = response.json()
        items = data.get("items", [])

        if not items:
            logger.warning(f"No GitHub repositories found for '{query}'")
            return []

        posts = []

        for repo in items[:max_results]:
            # Extract metadata
            stars = repo.get("stargazers_count", 0)

            # Skip repos with too few stars
            if stars < min_stars:
                continue

            # Build description
            repo_name = repo.get("full_name", "")
            description = repo.get("description", "") or ""
            language = repo.get("language", "")
            topics_list = repo.get("topics", [])

            body = f"{description}\n\nLanguage: {language}"
            if topics_list:
                body += f"\nTopics: {', '.join(topics_list[:5])}"

            body = body[:5000]

            # Parse creation date
            created_at = repo.get("created_at")
            ts = None
            if created_at:
                try:
                    dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    ts = dt.timestamp()
                except ValueError:
                    pass

            # Create Post
            post = Post(
                id=f"gh_{repo.get('id', hash(repo_name))}",
                source="rss",  # Or create new source "github"
                title=repo_name[:300],
                body=body,
                created_ts=ts,
                url=repo.get("html_url", ""),
                score=stars,
                comments_count=repo.get("open_issues_count", 0),
                lang=language if language else None,
                raw={'query': query, 'repo': repo}
            )
            posts.append(post)

        logger.info(f"✓ Fetched {len(posts)} GitHub repositories (with >= {min_stars} stars)")

        # Save raw data
        if output_dir and posts:
            output_dir = Path(output_dir)
            ensure_dir(output_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = query.replace(' ', '_')[:30]
            output_path = output_dir / f"posts_github_{safe_query}_{timestamp}.json"

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

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            logger.error(
                "GitHub API rate limit exceeded. "
                "Consider setting GITHUB_TOKEN environment variable for higher limits."
            )
        else:
            logger.error(f"GitHub API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to search GitHub: {e}")
        return []


def fetch_github_multiple_queries(
    queries: List[str],
    topics: Optional[List[str]] = None,
    max_results_per_query: int = 20,
    min_stars: int = 10,
    sleep_between: float = 2.0,
    output_dir: Optional[Path] = None
) -> List[Post]:
    """
    Fetch GitHub repositories for multiple search queries.

    Args:
        queries: List of search queries
        topics: GitHub topics to filter by (applies to all queries)
        max_results_per_query: Max results per query
        min_stars: Minimum star count threshold
        sleep_between: Sleep between queries (seconds)
        output_dir: Directory to save raw JSON (optional)

    Returns:
        Combined list of Post objects
    """
    all_posts = []

    for i, query in enumerate(queries, 1):
        logger.info(f"[{i}/{len(queries)}] GitHub query: '{query}'")

        posts = fetch_github_alternatives(
            query=query,
            topics=topics,
            max_results=max_results_per_query,
            min_stars=min_stars,
            output_dir=output_dir
        )

        all_posts.extend(posts)

        # Sleep between queries to avoid rate limiting
        if i < len(queries):
            logger.debug(f"Sleeping {sleep_between}s before next query...")
            time.sleep(sleep_between)

    logger.info(f"✓ Total: {len(all_posts)} repositories from {len(queries)} queries")

    return all_posts
