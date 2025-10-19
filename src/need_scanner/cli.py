"""CLI for need_scanner using Typer."""

import typer
from pathlib import Path
from typing import Optional
from loguru import logger
import glob

from .config import get_config
from .utils import setup_logger, ensure_dir, format_cost, read_json
from .schemas import Insight, ProcessingStats
from .fetchers.reddit import fetch_subreddit_new, fetch_multiple_subreddits, load_posts_from_json
from .fetchers.hn import fetch_ask_hn, load_posts_from_json as hn_load_posts
from .fetchers.rss import fetch_rss, load_feed_urls_from_file
from .fetchers.twitter import fetch_twitter_search, load_queries_from_file
from .fetchers.producthunt import fetch_producthunt, load_categories_from_file
from .fetchers.stackexchange import fetch_stackexchange, load_sites_from_file
from .analysis.intent import filter_by_intent
from .processing.filters import filter_by_language, filter_by_score, filter_by_comments
from .processing.clean import normalize
from .processing.dedupe import dedupe
from .processing.embed import embed_posts
from .processing.cluster import cluster, get_cluster_data
from .analysis.summarize import summarize_all_clusters
from .analysis.scoring import compute_pain_score, combine_scores
from .export.writer import write_insights_csv, write_cluster_results

app = typer.Typer(
    name="need_scanner",
    help="Pipeline for collecting and analyzing user pain points"
)


@app.command()
def collect(
    subreddit: Optional[str] = None,
    limit: int = typer.Option(None, help="Number of posts to fetch"),
    sleep: float = typer.Option(None, help="Sleep between requests (seconds)"),
    output: Path = typer.Option(Path("data/raw"), help="Output directory")
):
    """
    Collect posts from Reddit.

    Example: python -m need_scanner collect --subreddit freelance --limit 200
    """
    setup_logger()

    # Load config
    config = get_config()

    # Use config defaults if not specified
    subreddit = subreddit or config.ns_default_subreddit
    limit = limit or config.ns_fetch_limit
    sleep = sleep or config.ns_sleep_between

    logger.info(f"Collecting posts from r/{subreddit}...")

    # Fetch posts
    posts = fetch_subreddit_new(
        subreddit=subreddit,
        limit=limit,
        sleep=sleep,
        output_dir=output
    )

    logger.info(f"✓ Collected {len(posts)} posts")


@app.command()
def collect_reddit_multi(
    config_file: Path = typer.Option(Path("config/reddit_subs.txt"), help="Subreddit list config file"),
    limit_per_sub: int = typer.Option(30, help="Max posts per subreddit"),
    sleep_between: float = typer.Option(2.0, help="Sleep between subreddits (seconds)"),
    output: Path = typer.Option(Path("data/raw"), help="Output directory")
):
    """
    Collect posts from multiple subreddits defined in config file.

    Example: python -m need_scanner collect-reddit-multi --limit-per-sub 30
    """
    setup_logger()

    if not config_file.exists():
        logger.error(f"Config file not found: {config_file}")
        raise typer.Exit(1)

    logger.info(f"Collecting from multiple subreddits (config: {config_file})...")

    # Fetch posts from all subreddits
    posts = fetch_multiple_subreddits(
        config_file=config_file,
        limit_per_sub=limit_per_sub,
        sleep_between_subs=sleep_between,
        output_dir=output
    )

    logger.info(f"✓ Collected {len(posts)} total posts from multiple subreddits")


@app.command()
def collect_hn(
    queries: Optional[str] = typer.Option(None, help="Comma-separated query strings"),
    min_points: int = typer.Option(20, help="Minimum points threshold"),
    days: int = typer.Option(30, help="Look back N days"),
    limit: int = typer.Option(100, help="Max posts per query"),
    output: Path = typer.Option(Path("data/raw"), help="Output directory")
):
    """
    Collect posts from Hacker News (Ask HN).

    Example: python -m need_scanner collect-hn --days 30 --min-points 20
    """
    setup_logger()

    logger.info("Collecting posts from Hacker News...")

    # Parse queries
    query_list = None
    if queries:
        query_list = [q.strip() for q in queries.split(",")]

    # Fetch posts
    posts = fetch_ask_hn(
        queries=query_list,
        min_points=min_points,
        days=days,
        limit=limit,
        output_dir=output
    )

    logger.info(f"✓ Collected {len(posts)} posts from Hacker News")


@app.command()
def collect_rss(
    feeds_file: Optional[Path] = typer.Option(None, help="Path to RSS feeds file"),
    feeds: Optional[str] = typer.Option(None, help="Comma-separated RSS feed URLs"),
    days: int = typer.Option(30, help="Look back N days"),
    output: Path = typer.Option(Path("data/raw"), help="Output directory")
):
    """
    Collect posts from RSS feeds.

    Example: python -m need_scanner collect-rss --feeds-file config/rss_feeds.txt
    """
    setup_logger()

    logger.info("Collecting posts from RSS feeds...")

    # Load feed URLs
    feed_urls = []
    if feeds_file and feeds_file.exists():
        feed_urls = load_feed_urls_from_file(feeds_file)
    elif feeds:
        feed_urls = [f.strip() for f in feeds.split(",")]
    else:
        logger.error("Please provide either --feeds-file or --feeds")
        raise typer.Exit(1)

    # Fetch posts
    posts = fetch_rss(
        feed_urls=feed_urls,
        days=days,
        output_dir=output
    )

    logger.info(f"✓ Collected {len(posts)} posts from RSS feeds")


@app.command()
def collect_twitter(
    queries_file: Optional[Path] = typer.Option(None, help="Path to Twitter queries file"),
    queries: Optional[str] = typer.Option(None, help="Comma-separated query strings"),
    days: int = typer.Option(7, help="Look back N days"),
    min_likes: int = typer.Option(5, help="Minimum likes threshold"),
    min_retweets: int = typer.Option(2, help="Minimum retweets threshold"),
    limit: int = typer.Option(100, help="Max tweets per query"),
    output: Path = typer.Option(Path("data/raw"), help="Output directory")
):
    """
    Collect tweets from Twitter/X using snscrape.

    Example: python -m need_scanner collect-twitter --queries-file config/twitter_queries.txt --days 7
    """
    setup_logger()

    logger.info("Collecting tweets from Twitter/X...")

    # Load queries
    query_list = None
    if queries_file and queries_file.exists():
        query_list = load_queries_from_file(queries_file)
    elif queries:
        query_list = [q.strip() for q in queries.split(",")]

    # Fetch tweets
    posts = fetch_twitter_search(
        queries=query_list,
        days=days,
        min_likes=min_likes,
        min_retweets=min_retweets,
        limit_per_query=limit,
        output_dir=output
    )

    logger.info(f"✓ Collected {len(posts)} tweets from Twitter/X")


@app.command()
def collect_producthunt(
    api_token: Optional[str] = typer.Option(None, "--api-token", envvar="PRODUCTHUNT_API_TOKEN", help="Product Hunt API token"),
    categories_file: Optional[Path] = typer.Option(None, help="Path to categories file"),
    categories: Optional[str] = typer.Option(None, help="Comma-separated category slugs"),
    days: int = typer.Option(7, help="Look back N days"),
    limit: int = typer.Option(100, help="Max posts to fetch"),
    output: Path = typer.Option(Path("data/raw"), help="Output directory")
):
    """
    Collect posts from Product Hunt using GraphQL API.

    Requires PRODUCTHUNT_API_TOKEN environment variable or --api-token option.
    Get your token at: https://www.producthunt.com/v2/oauth/applications

    Example: python -m need_scanner collect-producthunt --days 7 --limit 50
    """
    setup_logger()

    logger.info("Collecting posts from Product Hunt...")

    # Load categories
    category_list = None
    if categories_file and categories_file.exists():
        category_list = load_categories_from_file(categories_file)
    elif categories:
        category_list = [c.strip() for c in categories.split(",")]

    # Fetch posts
    posts = fetch_producthunt(
        api_token=api_token,
        days=days,
        categories=category_list,
        limit=limit,
        output_dir=output
    )

    logger.info(f"✓ Collected {len(posts)} posts from Product Hunt")


@app.command()
def collect_stackexchange(
    sites_file: Optional[Path] = typer.Option(None, help="Path to sites file"),
    sites: Optional[str] = typer.Option(None, help="Comma-separated site names"),
    tags: Optional[str] = typer.Option(None, help="Comma-separated tags to filter"),
    days: int = typer.Option(7, help="Look back N days"),
    min_score: int = typer.Option(5, help="Minimum question score"),
    limit: int = typer.Option(50, help="Max questions per site"),
    output: Path = typer.Option(Path("data/raw"), help="Output directory")
):
    """
    Collect questions from Stack Exchange sites using public API.

    Example: python -m need_scanner collect-stackexchange --sites stackoverflow,workplace --days 7
    """
    setup_logger()

    logger.info("Collecting questions from Stack Exchange...")

    # Load sites
    site_list = None
    if sites_file and sites_file.exists():
        site_list = load_sites_from_file(sites_file)
    elif sites:
        site_list = [s.strip() for s in sites.split(",")]

    # Parse tags
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]

    # Fetch questions
    posts = fetch_stackexchange(
        sites=site_list,
        tags=tag_list,
        days=days,
        min_score=min_score,
        limit_per_site=limit,
        output_dir=output
    )

    logger.info(f"✓ Collected {len(posts)} questions from Stack Exchange")


@app.command()
def collect_all(
    # Reddit options
    reddit_subreddit: Optional[str] = typer.Option(None, help="Reddit subreddit (single)"),
    pack: Optional[str] = typer.Option(None, help="Subreddit pack name (from config/packs/)"),
    reddit_limit: int = typer.Option(200, help="Reddit post limit"),
    reddit_mode: str = typer.Option("new", help="Reddit mode: 'new' or 'hot'"),

    # Keyword filtering
    include_keywords_file: Optional[Path] = typer.Option(None, help="Keywords file for filtering (e.g., config/intent_patterns.txt)"),

    # History & deduplication
    history_days: int = typer.Option(0, help="Days of history for deduplication (0 = disabled)"),

    # Other sources
    hn_days: int = typer.Option(30, help="HN lookback days"),
    hn_min_points: int = typer.Option(20, help="HN minimum points"),
    rss_feeds_file: Optional[Path] = typer.Option(None, help="RSS feeds file"),
    rss_days: int = typer.Option(30, help="RSS lookback days"),

    # Output & filters
    output: Path = typer.Option(Path("data/raw"), help="Output directory"),
    filter_lang: Optional[str] = typer.Option(None, help="Filter by language (e.g., 'en,fr')"),
    filter_intent: bool = typer.Option(True, help="Filter by intent (pain/request only)"),
    min_score: int = typer.Option(0, help="Minimum score filter"),
    min_comments: int = typer.Option(0, help="Minimum comments filter")
):
    """
    Collect posts from all configured sources (Reddit + HN + RSS).

    V2 Features:
    - Subreddit packs (--pack smallbiz_fr)
    - Hot/new modes (--reddit-mode hot)
    - Keyword filtering (--include-keywords-file config/intent_patterns.txt)
    - Multi-week deduplication (--history-days 45)

    Example: python -m need_scanner collect-all --pack smallbiz_fr --reddit-mode hot --include-keywords-file config/intent_patterns.txt
    """
    setup_logger()
    from .config import load_subreddit_pack, load_intent_keywords

    config = get_config()

    logger.info("=" * 60)
    logger.info("MULTI-SOURCE COLLECTION (V2)")
    logger.info("=" * 60)

    # Load keywords if specified
    include_keywords = None
    if include_keywords_file:
        try:
            include_keywords = load_intent_keywords(include_keywords_file)
            logger.info(f"Loaded {len(include_keywords)} intent keywords from {include_keywords_file}")
        except FileNotFoundError as e:
            logger.error(str(e))
            raise typer.Exit(1)

    all_posts = []

    # 1. Collect from Reddit
    if pack or reddit_subreddit or config.ns_default_subreddit:
        if pack:
            # Load pack
            try:
                subreddits = load_subreddit_pack(pack)
                logger.info(f"\n[1/3] Collecting from Reddit pack '{pack}' ({len(subreddits)} subreddits)...")

                reddit_posts = fetch_multiple_subreddits(
                    subreddits=subreddits,
                    limit_per_sub=reddit_limit,
                    mode=reddit_mode,
                    include_keywords=include_keywords,
                    sleep_between_subs=2.0,
                    output_dir=output
                )
                all_posts.extend(reddit_posts)
                logger.info(f"✓ Collected {len(reddit_posts)} posts from Reddit pack")
            except FileNotFoundError as e:
                logger.error(str(e))
                raise typer.Exit(1)
        else:
            # Single subreddit
            subreddit = reddit_subreddit or config.ns_default_subreddit
            logger.info(f"\n[1/3] Collecting from Reddit (r/{subreddit}, mode={reddit_mode})...")
            try:
                reddit_posts = fetch_subreddit_new(
                    subreddit=subreddit,
                    limit=reddit_limit,
                    mode=reddit_mode,
                    include_keywords=include_keywords,
                    output_dir=output
                )
                all_posts.extend(reddit_posts)
                logger.info(f"✓ Collected {len(reddit_posts)} posts from Reddit")
            except Exception as e:
                logger.error(f"Failed to collect from Reddit: {e}")

    # 2. Collect from Hacker News
    logger.info(f"\n[2/3] Collecting from Hacker News...")
    try:
        hn_posts = fetch_ask_hn(
            min_points=hn_min_points,
            days=hn_days,
            output_dir=output
        )
        all_posts.extend(hn_posts)
        logger.info(f"✓ Collected {len(hn_posts)} posts from Hacker News")
    except Exception as e:
        logger.error(f"Failed to collect from Hacker News: {e}")

    # 3. Collect from RSS
    if rss_feeds_file and rss_feeds_file.exists():
        logger.info(f"\n[3/3] Collecting from RSS feeds...")
        try:
            feed_urls = load_feed_urls_from_file(rss_feeds_file)
            rss_posts = fetch_rss(
                feed_urls=feed_urls,
                days=rss_days,
                output_dir=output
            )
            all_posts.extend(rss_posts)
            logger.info(f"✓ Collected {len(rss_posts)} posts from RSS")
        except Exception as e:
            logger.error(f"Failed to collect from RSS: {e}")
    else:
        logger.info(f"\n[3/3] Skipping RSS (no feeds file specified)")

    logger.info(f"\n✓ Total collected: {len(all_posts)} posts from all sources")

    # Apply filters
    filtered_posts = all_posts

    # Language filter
    if filter_lang:
        allowed_langs = [lang.strip() for lang in filter_lang.split(",")]
        logger.info(f"\nApplying language filter: {allowed_langs}")
        filtered_posts = filter_by_language(filtered_posts, allowed_languages=allowed_langs)

    # Intent filter
    if filter_intent:
        logger.info("\nApplying intent filter (pain/request only)...")
        filtered_posts = filter_by_intent(filtered_posts, allowed_intents=["pain", "request"])

    # Score filter
    if min_score > 0:
        logger.info(f"\nApplying score filter (min_score={min_score})...")
        filtered_posts = filter_by_score(filtered_posts, min_score=min_score)

    # Comments filter
    if min_comments > 0:
        logger.info(f"\nApplying comments filter (min_comments={min_comments})...")
        filtered_posts = filter_by_comments(filtered_posts, min_comments=min_comments)

    # Multi-week deduplication (V2)
    if history_days > 0:
        logger.info(f"\nApplying multi-week deduplication (history_days={history_days})...")
        from .processing.dedupe import dedupe
        history_path = Path("data/history/dedupe_history.json")
        filtered_posts = dedupe(
            filtered_posts,
            history_path=history_path,
            history_days=history_days
        )

    logger.info(f"\n✓ After filtering: {len(filtered_posts)} posts")

    # Save filtered posts to unified file
    from .utils import write_json
    ensure_dir(output)
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output / f"posts_multi_{timestamp}.json"

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
            "intent": p.intent,
            "raw": {}
        }
        for p in filtered_posts
    ]

    write_json(output_path, posts_data)
    logger.info(f"\n✓ Saved filtered posts to: {output_path}")

    logger.info("\n" + "=" * 60)
    logger.info("COLLECTION COMPLETE")
    logger.info("=" * 60)


@app.command()
def run(
    input_pattern: str = typer.Option("data/raw/posts_*.json", help="Input file pattern"),
    clusters: int = typer.Option(None, help="Number of clusters"),
    model_sum: str = typer.Option(None, help="Summary model"),
    max_examples: int = typer.Option(None, help="Max examples per cluster"),
    output_dir: Path = typer.Option(Path("data"), help="Output directory"),

    # V2: Priority scoring weights
    novelty_weight: float = typer.Option(0.15, help="Weight for novelty score (default: 0.15)"),
    trend_weight: float = typer.Option(0.10, help="Weight for trend score (default: 0.10)"),
    pain_weight: float = typer.Option(0.30, help="Weight for pain score (default: 0.30)"),
    traction_weight: float = typer.Option(0.25, help="Weight for traction score (default: 0.25)"),
    wtp_weight: float = typer.Option(0.20, help="Weight for WTP score (default: 0.20)"),

    # V2: History paths for trend/novelty
    history_path: Optional[Path] = typer.Option(None, help="Path to history directory (for trends/novelty)")
):
    """
    Run complete pipeline: clean, dedupe, embed, cluster, summarize, export.

    V2 Features:
    - Trend analysis (--trend-weight 0.15)
    - Novelty detection (--novelty-weight 0.15)
    - Configurable priority weights

    Example: python -m need_scanner run --novelty-weight 0.20 --trend-weight 0.15
    """
    setup_logger()

    # Load config
    config = get_config()

    # Use config defaults if not specified
    n_clusters = clusters or config.ns_num_clusters
    summary_model = model_sum or config.ns_summary_model
    max_docs = max_examples or config.ns_max_docs_per_cluster

    # Default history path
    if history_path is None:
        history_path = Path("data/history")

    logger.info("=" * 60)
    logger.info("NEED SCANNER PIPELINE (V2)")
    logger.info("=" * 60)
    logger.info(f"Priority weights: pain={pain_weight}, traction={traction_weight}, novelty={novelty_weight}, wtp={wtp_weight}, trend={trend_weight}")

    # Ensure output directory exists
    ensure_dir(output_dir)

    # 1. Load posts
    logger.info("\n[1/7] Loading posts...")
    input_files = glob.glob(input_pattern)
    if not input_files:
        logger.error(f"No files found matching pattern: {input_pattern}")
        raise typer.Exit(1)

    logger.info(f"Found {len(input_files)} input files")
    all_posts = []
    for file_path in input_files:
        posts = load_posts_from_json(Path(file_path))
        all_posts.extend(posts)

    logger.info(f"Loaded {len(all_posts)} total posts")

    if len(all_posts) < 5:
        logger.error("Not enough posts to process (minimum 5 required)")
        raise typer.Exit(1)

    # 2. Clean
    logger.info("\n[2/7] Cleaning and normalizing...")
    clean_posts = normalize(all_posts)

    # 3. Dedupe
    logger.info("\n[3/7] Deduplicating...")
    deduped_posts = dedupe(clean_posts)

    if len(deduped_posts) < 5:
        logger.error("Not enough posts after deduplication (minimum 5 required)")
        raise typer.Exit(1)

    # 4. Embed
    logger.info("\n[4/7] Generating embeddings...")
    embeddings, metadata, embed_cost = embed_posts(
        posts=deduped_posts,
        model=config.ns_embed_model,
        api_key=config.openai_api_key,
        output_dir=output_dir
    )

    # 5. Cluster
    logger.info("\n[5/7] Clustering...")
    labels, kmeans_model = cluster(embeddings, n_clusters)
    cluster_data = get_cluster_data(labels, metadata, embeddings)

    # 5.5. Calculate trends & novelty (V2)
    logger.info("\n[5.5/7] Calculating trend & novelty scores...")

    from .analysis.trends import calculate_cluster_trends
    from .analysis.novelty import calculate_cluster_novelty
    import numpy as np

    # Prepare embeddings by cluster for novelty
    embeddings_by_cluster = {}
    for cluster_id, items in cluster_data.items():
        cluster_embeddings = np.array([item["embedding"] for item in items])
        embeddings_by_cluster[cluster_id] = cluster_embeddings

    # Calculate trends
    trend_path = history_path / "trends.json" if history_path else None
    trend_scores = calculate_cluster_trends(
        cluster_data=cluster_data,
        history_path=trend_path,
        weeks_lookback=4
    )

    # Calculate novelty
    novelty_path = history_path / "novelty.json" if history_path else None
    novelty_scores = calculate_cluster_novelty(
        cluster_data=cluster_data,
        embeddings_by_cluster=embeddings_by_cluster,
        history_path=novelty_path
    )

    logger.info(f"Calculated trends & novelty for {len(trend_scores)} clusters")

    # 6. Summarize
    logger.info("\n[6/7] Summarizing clusters with LLM...")
    summaries, summary_cost = summarize_all_clusters(
        cluster_data=cluster_data,
        model=summary_model,
        api_key=config.openai_api_key,
        max_examples=max_docs,
        max_input_tokens=config.ns_max_input_tokens_per_prompt,
        max_output_tokens=config.ns_max_output_tokens,
        cost_warn_threshold=config.ns_cost_warn_prompt_usd
    )

    if not summaries:
        logger.error("No cluster summaries generated")
        raise typer.Exit(1)

    # 7. Score and create insights (V2: with trend & novelty)
    logger.info("\n[7/7] Computing priority scores and creating insights...")

    from .analysis.priority import calculate_traction_score, calculate_priority_score
    from .schemas import EnrichedInsight, EnrichedClusterSummary

    insights = []

    for summary in summaries:
        cluster_items = cluster_data[summary.cluster_id]
        meta_items = [item["meta"] for item in cluster_items]

        # Heuristic score
        heuristic_score = compute_pain_score(meta_items)

        # Combined pain score
        pain_llm = summary.pain_score_llm or 5.0
        final_pain_score = combine_scores(pain_llm, heuristic_score)

        # Traction score
        traction_score = calculate_traction_score(meta_items)

        # Get trend & novelty scores
        cluster_id = summary.cluster_id
        trend_score = trend_scores.get(cluster_id, 5.0)
        novelty_score = novelty_scores.get(cluster_id, 5.0)

        # WTP score (if available)
        wtp_score = 5.0  # Default, could be enhanced with WTP analysis

        # Calculate priority with custom weights
        priority_score = calculate_priority_score(
            pain_score_llm=pain_llm,
            heuristic_score=heuristic_score,
            traction_score=traction_score,
            novelty_score=novelty_score,
            wtp_score=wtp_score,
            trend_score=trend_score,
            pain_weight=pain_weight,
            traction_weight=traction_weight,
            novelty_weight=novelty_weight,
            wtp_weight=wtp_weight,
            trend_weight=trend_weight
        )

        # Convert to EnrichedClusterSummary if needed
        if hasattr(summary, 'problem'):
            # Already enriched
            enriched_summary = summary
        else:
            # Convert legacy to enriched
            enriched_summary = EnrichedClusterSummary(
                cluster_id=summary.cluster_id,
                size=summary.size,
                title=summary.title,
                problem=summary.description,
                persona="Unknown",  # Would need LLM extraction
                jtbd="",
                context="",
                monetizable=summary.monetizable,
                mvp=summary.mvp,
                alternatives=[],
                willingness_to_pay_signal="",
                pain_score_llm=summary.pain_score_llm
            )

        # Create EnrichedInsight
        insight = EnrichedInsight(
            cluster_id=cluster_id,
            rank=0,  # Will be set after sorting
            priority_score=priority_score,
            examples=meta_items[:5],
            summary=enriched_summary,
            pain_score_final=final_pain_score,
            heuristic_score=heuristic_score,
            traction_score=traction_score,
            novelty_score=novelty_score,
            trend_score=trend_score,
            keywords_matched=[],
            source_mix=list(set(item.get("source", "unknown") for item in meta_items))
        )
        insights.append(insight)

    # Sort by priority score
    insights.sort(key=lambda x: x.priority_score, reverse=True)

    # Assign ranks
    for rank, insight in enumerate(insights, 1):
        insight.rank = rank

    # Export
    logger.info("\nExporting results...")

    # Statistics
    stats = {
        "total_posts": len(all_posts),
        "after_cleaning": len(clean_posts),
        "after_dedup": len(deduped_posts),
        "num_clusters": len(cluster_data),
        "embeddings_cost_usd": round(embed_cost, 4),
        "summary_cost_usd": round(summary_cost, 4),
        "total_cost_usd": round(embed_cost + summary_cost, 4),
        "priority_weights": {
            "pain": pain_weight,
            "traction": traction_weight,
            "novelty": novelty_weight,
            "wtp": wtp_weight,
            "trend": trend_weight
        }
    }

    # Write outputs (V2: enriched format)
    from .export.writer import write_enriched_cluster_results, write_enriched_insights_csv

    write_enriched_cluster_results(
        output_dir / "cluster_results.json",
        insights,
        stats
    )

    write_enriched_insights_csv(
        output_dir / "insights_enriched.csv",
        insights
    )

    # Legacy format for compatibility
    write_insights_csv(
        output_dir / "insights.csv",
        insights
    )

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE (V2)")
    logger.info("=" * 60)
    logger.info(f"Total posts: {stats['total_posts']}")
    logger.info(f"After cleaning: {stats['after_cleaning']}")
    logger.info(f"After dedup: {stats['after_dedup']}")
    logger.info(f"Clusters: {stats['num_clusters']}")
    logger.info(f"Insights generated: {len(insights)}")
    logger.info(f"\nTop 3 priorities:")
    for insight in insights[:3]:
        logger.info(f"  #{insight.rank}: {insight.summary.title}")
        logger.info(f"    Priority: {insight.priority_score:.2f} | Pain: {insight.pain_score_final} | Traction: {insight.traction_score:.1f} | Novelty: {insight.novelty_score:.1f} | Trend: {insight.trend_score:.1f}")
    logger.info(f"\nCost breakdown:")
    logger.info(f"  Embeddings: {format_cost(embed_cost)}")
    logger.info(f"  Summaries:  {format_cost(summary_cost)}")
    logger.info(f"  Total:      {format_cost(embed_cost + summary_cost)}")
    logger.info(f"\nOutputs:")
    logger.info(f"  {output_dir / 'cluster_results.json'}")
    logger.info(f"  {output_dir / 'insights.csv'} (legacy)")
    logger.info(f"  {output_dir / 'insights_enriched.csv'} (V2 with all scores)")
    logger.info(f"  {output_dir / 'embeddings.npy'}")
    logger.info(f"  {output_dir / 'meta.json'}")


@app.command()
def estimate(
    input_pattern: str = typer.Option("data/raw/posts_*.json", help="Input file pattern"),
    clusters: int = typer.Option(None, help="Number of clusters")
):
    """
    Estimate cost without making API calls.

    Example: python -m need_scanner estimate --input "data/raw/posts_*.json"
    """
    setup_logger()

    # Load config
    config = get_config()
    n_clusters = clusters or config.ns_num_clusters

    logger.info("Estimating costs...")

    # Load posts
    input_files = glob.glob(input_pattern)
    if not input_files:
        logger.error(f"No files found matching pattern: {input_pattern}")
        raise typer.Exit(1)

    all_posts = []
    for file_path in input_files:
        posts = load_posts_from_json(Path(file_path))
        all_posts.extend(posts)

    logger.info(f"Posts to process: {len(all_posts)}")

    # Estimate embedding cost
    from .utils import estimate_tokens_batch, calculate_cost
    from .processing.embed import create_text_for_embedding

    texts = [create_text_for_embedding(p) for p in all_posts]
    embed_tokens = estimate_tokens_batch(texts)
    embed_cost = calculate_cost(embed_tokens, 0, config.ns_embed_model)

    # Estimate summary cost
    summary_cost_per_cluster = calculate_cost(
        config.ns_max_input_tokens_per_prompt,
        config.ns_max_output_tokens,
        config.ns_summary_model
    )
    total_summary_cost = summary_cost_per_cluster * n_clusters

    total_cost = embed_cost + total_summary_cost

    logger.info(f"\nEstimated costs:")
    logger.info(f"  Embeddings ({embed_tokens} tokens): {format_cost(embed_cost)}")
    logger.info(f"  Summaries ({n_clusters} clusters): {format_cost(total_summary_cost)}")
    logger.info(f"  Total: {format_cost(total_cost)}")


@app.command()
def prefilter(
    input_pattern: str = typer.Option("data/raw/posts_*.json", help="Input file pattern"),
    filter_lang: Optional[str] = typer.Option(None, help="Filter by language (e.g., 'en,fr')"),
    filter_intent: bool = typer.Option(False, help="Apply intent filter (pain/request/howto)"),
    keep_intents: Optional[str] = typer.Option(None, help='Comma-separated list of intents to keep, e.g. "pain,request"'),
    detect_wtp: bool = typer.Option(False, help="Detect WTP signals"),
    show_sample: int = typer.Option(5, help="Number of sample posts to show")
):
    """
    Preview and filter collected posts before running full pipeline.

    Shows statistics about posts: language distribution, intent distribution,
    WTP signals, etc. Useful for understanding your data before clustering.

    Example: python -m need_scanner prefilter --filter-lang en --keep-intents "pain,request" --detect-wtp --show-sample 10
    """
    setup_logger()

    logger.info("=" * 60)
    logger.info("PREFILTER - Data Preview")
    logger.info("=" * 60)

    # 1. Load posts
    logger.info("\n[1/4] Loading posts...")
    input_files = glob.glob(input_pattern)
    if not input_files:
        logger.error(f"No files found matching pattern: {input_pattern}")
        raise typer.Exit(1)

    logger.info(f"Found {len(input_files)} input files")
    all_posts = []
    for file_path in input_files:
        posts = load_posts_from_json(Path(file_path))
        all_posts.extend(posts)

    logger.info(f"Loaded {len(all_posts)} total posts")

    # Count by source
    from collections import Counter
    sources = Counter(p.source for p in all_posts)
    logger.info(f"Sources: {dict(sources)}")

    # 2. Language detection
    logger.info("\n[2/4] Detecting languages...")
    from .processing.filters import filter_by_language

    # Detect for all
    all_with_lang = filter_by_language(all_posts, allowed_languages=None)  # Detect but don't filter

    langs = Counter(p.lang for p in all_with_lang if p.lang)
    logger.info(f"Language distribution: {dict(langs.most_common(10))}")

    # Apply language filter if specified
    filtered_posts = all_with_lang
    if filter_lang:
        allowed_langs = [lang.strip() for lang in filter_lang.split(",")]
        filtered_posts = filter_by_language(all_with_lang, allowed_languages=allowed_langs)
        logger.info(f"After language filter ({allowed_langs}): {len(filtered_posts)} posts")

    # 3. Intent classification
    logger.info("\n[3/4] Classifying intent...")
    from .analysis.intent import tag_intent

    for post in filtered_posts:
        if not post.intent:
            post.intent = tag_intent(post, use_llm_fallback=False)

    intents = Counter(p.intent for p in filtered_posts)
    logger.info(f"Intent distribution: {dict(intents.most_common())}")

    # Apply intent filter if specified
    if keep_intents:
        from .analysis.intent import filter_by_intent
        allowed_intents = [intent.strip() for intent in keep_intents.split(",")]
        filtered_posts = filter_by_intent(filtered_posts, allowed_intents=allowed_intents)
        logger.info(f"After intent filter ({allowed_intents}): {len(filtered_posts)} posts")
    elif filter_intent:
        from .analysis.intent import filter_by_intent
        filtered_posts = filter_by_intent(filtered_posts, allowed_intents=["pain", "request", "howto"])
        logger.info(f"After intent filter: {len(filtered_posts)} posts")

    # 4. WTP Detection
    if detect_wtp:
        logger.info("\n[4/4] Detecting WTP signals...")
        from .analysis.wtp import enrich_posts_with_wtp
        filtered_posts = enrich_posts_with_wtp(filtered_posts)

        posts_with_wtp = [p for p in filtered_posts if p.wtp_signals and p.wtp_signals.get('has_wtp')]
        logger.info(f"Posts with WTP signals: {len(posts_with_wtp)} ({100*len(posts_with_wtp)/len(filtered_posts):.1f}%)")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total posts loaded: {len(all_posts)}")
    logger.info(f"After filters: {len(filtered_posts)}")
    logger.info(f"Ready for pipeline: {'✅ Yes' if len(filtered_posts) >= 10 else '❌ No (need at least 10)'}")

    # Show sample posts
    if show_sample > 0 and filtered_posts:
        logger.info(f"\n📝 Sample of {min(show_sample, len(filtered_posts))} posts:")
        for i, post in enumerate(filtered_posts[:show_sample], 1):
            logger.info(f"\n{i}. {post.title[:70]}")
            logger.info(f"   Source: {post.source} | Lang: {post.lang} | Intent: {post.intent}")
            logger.info(f"   Score: {post.score} | Comments: {post.comments_count}")
            if detect_wtp and post.wtp_signals and post.wtp_signals.get('has_wtp'):
                logger.info(f"   💰 WTP Signals: {post.wtp_signals.get('signal_types')}")

    logger.info("\n" + "=" * 60)


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
