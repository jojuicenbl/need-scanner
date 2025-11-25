"""Balanced sampling by source category for multi-sector coverage."""

import yaml
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
from loguru import logger


def load_sources_config(config_path: Path = Path("config/sources_config.yaml")) -> Dict:
    """
    Load sources configuration from YAML.

    Args:
        config_path: Path to YAML config file

    Returns:
        Dict with sources configuration
    """
    if not config_path.exists():
        logger.warning(f"Sources config not found at {config_path}, using defaults")
        return {
            'reddit_sources': [],
            'stackexchange_sources': [],
            'category_quotas': {}
        }

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded sources config from {config_path}")
    return config


def get_sources_by_category(config: Dict, source_type: str = 'reddit') -> Dict[str, List[Dict]]:
    """
    Group sources by category.

    Args:
        config: Sources configuration dict
        source_type: 'reddit' or 'stackexchange'

    Returns:
        Dict mapping category to list of sources
    """
    key = f"{source_type}_sources"
    sources = config.get(key, [])

    by_category = defaultdict(list)
    for source in sources:
        category = source.get('category', 'other')
        by_category[category].append(source)

    return dict(by_category)


def balance_posts_by_category(
    posts: List[Dict],
    category_quotas: Dict[str, int] = None
) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Balance posts across categories to ensure diversity.

    Args:
        posts: List of post dicts with 'source_category' field
        category_quotas: Dict mapping category to max posts (optional)

    Returns:
        Tuple of (balanced posts list, category counts dict)
    """
    if not posts:
        return [], {}

    # Group posts by category
    by_category = defaultdict(list)
    for post in posts:
        category = post.get('source_category', 'other')
        by_category[category].append(post)

    # Log initial distribution
    logger.info("Initial category distribution:")
    for category, cat_posts in sorted(by_category.items()):
        logger.info(f"  {category}: {len(cat_posts)} posts")

    # Apply quotas if provided
    balanced_posts = []
    category_counts = {}

    for category, cat_posts in by_category.items():
        quota = category_quotas.get(category) if category_quotas else None

        if quota and len(cat_posts) > quota:
            # Sample to quota
            selected = cat_posts[:quota]
            logger.info(f"  {category}: sampled {quota} from {len(cat_posts)}")
        else:
            selected = cat_posts

        balanced_posts.extend(selected)
        category_counts[category] = len(selected)

    # Log final distribution
    logger.info(f"Balanced to {len(balanced_posts)} posts across {len(category_counts)} categories")
    for category, count in sorted(category_counts.items()):
        logger.info(f"  {category}: {count} posts")

    return balanced_posts, category_counts


def annotate_posts_with_source_category(
    posts: List[Dict],
    sources_config: Dict,
    source_type: str = 'reddit'
) -> List[Dict]:
    """
    Annotate posts with their source category.

    Args:
        posts: List of post dicts
        sources_config: Sources configuration
        source_type: 'reddit' or 'stackexchange'

    Returns:
        Posts with 'source_category' field added
    """
    # Build source -> category mapping
    key = f"{source_type}_sources"
    sources = sources_config.get(key, [])

    source_to_category = {}
    for source in sources:
        if source_type == 'reddit':
            source_name = source.get('name')
        else:  # stackexchange
            source_name = source.get('site')

        category = source.get('category', 'other')
        source_to_category[source_name] = category

    # Annotate posts
    for post in posts:
        # Extract source name from post
        if source_type == 'reddit':
            # Assume post has 'subreddit' field or we can extract from raw
            source_name = post.get('raw', {}).get('subreddit', 'unknown')
        else:
            # StackExchange: extract from post metadata
            source_name = post.get('raw', {}).get('site', 'unknown')

        category = source_to_category.get(source_name, 'other')
        post['source_category'] = category

    logger.info(f"Annotated {len(posts)} posts with source categories")
    return posts


def get_sampling_plan(
    sources_config: Dict,
    total_budget: int = 800
) -> Dict[str, Dict[str, int]]:
    """
    Create a sampling plan for balanced multi-sector collection.

    Args:
        sources_config: Sources configuration
        total_budget: Total number of posts to collect

    Returns:
        Dict with sampling plan per source type and category
    """
    category_quotas = sources_config.get('category_quotas', {})

    # Calculate proportions
    total_quota = sum(category_quotas.values()) or 1
    plan = {}

    # Reddit sampling
    reddit_by_category = get_sources_by_category(sources_config, 'reddit')
    reddit_plan = {}

    for category, sources in reddit_by_category.items():
        quota = category_quotas.get(category, 50)
        proportion = quota / total_quota
        category_budget = int(total_budget * proportion * 0.6)  # 60% from Reddit

        # Distribute across sources in category
        posts_per_source = category_budget // len(sources) if sources else 0
        reddit_plan[category] = {
            'total': category_budget,
            'per_source': posts_per_source,
            'sources': [s.get('name') for s in sources]
        }

    plan['reddit'] = reddit_plan

    # StackExchange sampling
    se_by_category = get_sources_by_category(sources_config, 'stackexchange')
    se_plan = {}

    for category, sources in se_by_category.items():
        quota = category_quotas.get(category, 50)
        proportion = quota / total_quota
        category_budget = int(total_budget * proportion * 0.4)  # 40% from StackExchange

        posts_per_source = category_budget // len(sources) if sources else 0
        se_plan[category] = {
            'total': category_budget,
            'per_source': posts_per_source,
            'sources': [s.get('site') for s in sources]
        }

    plan['stackexchange'] = se_plan

    # Log plan
    logger.info("Sampling plan:")
    logger.info(f"  Total budget: {total_budget} posts")
    for source_type, type_plan in plan.items():
        logger.info(f"  {source_type}:")
        for category, cat_plan in type_plan.items():
            logger.info(
                f"    {category}: {cat_plan['total']} posts "
                f"({cat_plan['per_source']} per source, {len(cat_plan['sources'])} sources)"
            )

    return plan
