"""Core module exposing the main Need Scanner pipeline as a reusable function."""

import glob
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from loguru import logger

from .config import get_config, load_subreddit_pack
from .schemas import Post, EnrichedInsight
from .processing.embed import embed_posts
from .processing.cluster import cluster, get_cluster_data
from .jobs.enriched_pipeline import run_enriched_pipeline
from .export.csv_v2 import export_insights_to_csv
from .export.writer import write_enriched_cluster_results
from .fetchers.reddit import fetch_multiple_subreddits
from .db import (
    init_database,
    generate_run_id,
    save_run,
    save_insights,
    get_db_path
)


# Default max age for posts data (in days)
DEFAULT_MAX_DATA_AGE_DAYS = 1


def _check_data_freshness(input_pattern: str, max_age_days: int = 1) -> tuple[bool, Optional[datetime]]:
    """
    Check if existing data files are fresh enough.

    Args:
        input_pattern: Glob pattern for input files
        max_age_days: Maximum acceptable age in days

    Returns:
        Tuple of (is_fresh, oldest_file_date)
    """
    files = glob.glob(input_pattern)
    if not files:
        return False, None

    oldest_mtime = None
    for f in files:
        mtime = datetime.fromtimestamp(os.path.getmtime(f))
        if oldest_mtime is None or mtime < oldest_mtime:
            oldest_mtime = mtime

    if oldest_mtime is None:
        return False, None

    age = datetime.now() - oldest_mtime
    is_fresh = age < timedelta(days=max_age_days)

    return is_fresh, oldest_mtime


def _fetch_fresh_data(
    pack_name: str = "multi_sector",
    output_dir: Path = Path("data/raw"),
    limit_per_sub: int = 30,
    clear_old: bool = True
) -> int:
    """
    Fetch fresh posts from Reddit using specified pack.

    Args:
        pack_name: Name of subreddit pack to use
        output_dir: Directory to save posts
        limit_per_sub: Posts per subreddit
        clear_old: Whether to delete old files first

    Returns:
        Number of posts fetched
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clear old files if requested
    if clear_old:
        old_files = list(output_dir.glob("posts_*.json"))
        if old_files:
            logger.info(f"Clearing {len(old_files)} old data files...")
            for f in old_files:
                f.unlink()

    # Load subreddit pack
    try:
        subreddits = load_subreddit_pack(pack_name)
        logger.info(f"Loaded pack '{pack_name}' with {len(subreddits)} subreddits")
    except FileNotFoundError:
        # Fallback to a minimal set
        logger.warning(f"Pack '{pack_name}' not found, using fallback subreddits")
        subreddits = ["freelance", "Entrepreneur", "smallbusiness", "SaaS", "webdev"]

    # Fetch posts
    posts = fetch_multiple_subreddits(
        subreddits=subreddits,
        limit_per_sub=limit_per_sub,
        mode="new",
        output_dir=output_dir
    )

    logger.info(f"Fetched {len(posts)} fresh posts")
    return len(posts)


def run_scan(
    config_name: Optional[str] = None,
    mode: str = "deep",
    max_insights: Optional[int] = None,
    input_pattern: str = "data/raw/posts_*.json",
    output_dir: Optional[Path] = None,
    save_to_db: bool = True,
    db_path: Optional[Path] = None,
    use_mmr: bool = True,
    use_history_penalty: bool = True,
    run_mode: str = "discover",  # "discover" (filter duplicates/non-SaaS) or "track"
    # Auto-fetch options
    auto_fetch: bool = True,  # Automatically fetch fresh data if stale
    max_data_age_days: int = 1,  # Max age of data before refetch
    fetch_pack: str = "multi_sector",  # Subreddit pack to use for fetch
    fetch_limit_per_sub: int = 30  # Posts per subreddit when fetching
) -> str:
    """
    Run complete Need Scanner pipeline and return run_id.

    This is the main entry point for programmatic usage of Need Scanner.
    It orchestrates the full pipeline:
    0. [NEW] Auto-fetch fresh data if existing data is stale
    1. Load collected posts from JSON files
    2. Generate embeddings
    3. Cluster posts
    4. Run enriched analysis (LLM scoring, sector classification, etc.)
    5. Export to CSV/JSON
    6. Save to SQLite database (optional)

    Args:
        config_name: Optional configuration name (for future multi-config support)
        mode: "light" or "deep" - controls LLM enrichment level
            - "light": Use light model for all enrichment (cheaper, faster)
            - "deep": Use heavy model for TOP K insights (better quality)
        max_insights: Optional limit on number of insights to keep (post-MMR)
        input_pattern: Glob pattern for input JSON files
        output_dir: Output directory (default: data/results_v2)
        save_to_db: Whether to save results to database (default: True)
        db_path: Custom database path (default: from config/env)
        use_mmr: Use MMR reranking for diversity (default: True)
        use_history_penalty: Apply history-based similarity penalty (default: True)
        run_mode: "discover" (filter duplicates & non-SaaS) or "track" (show all)
        auto_fetch: Automatically fetch fresh data if stale (default: True)
        max_data_age_days: Max age of data before refetch (default: 1 day)
        fetch_pack: Subreddit pack to use for fetch (default: "multi_sector")
        fetch_limit_per_sub: Posts per subreddit when fetching (default: 30)

    Returns:
        run_id: Unique identifier for this scan run

    Example:
        >>> from need_scanner.core import run_scan
        >>> run_id = run_scan(mode="deep", max_insights=20)
        >>> print(f"Scan complete! Run ID: {run_id}")

    Raises:
        FileNotFoundError: If no input files match the pattern
        ValueError: If invalid mode specified
    """
    # Validate mode
    if mode not in ["light", "deep"]:
        raise ValueError(f"Invalid mode '{mode}'. Must be 'light' or 'deep'.")

    # Load configuration
    config = get_config()

    # Generate unique run ID
    run_id = generate_run_id()

    # Setup output directory
    if output_dir is None:
        output_dir = Path("data/results_v2")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database if saving
    if save_to_db:
        init_database(db_path)

    logger.info("=" * 60)
    logger.info(f"Need Scanner - Run ID: {run_id}")
    logger.info(f"   Mode: {mode}")
    logger.info(f"   Config: {config_name or 'default'}")
    logger.info(f"   Auto-fetch: {auto_fetch} (max age: {max_data_age_days} days)")
    logger.info("=" * 60)

    # ========================================================================
    # STEP 0: Check data freshness and auto-fetch if needed
    # ========================================================================
    if auto_fetch:
        is_fresh, oldest_date = _check_data_freshness(input_pattern, max_data_age_days)

        if not is_fresh:
            if oldest_date:
                age_days = (datetime.now() - oldest_date).days
                logger.warning(f"\n[0/7] Data is stale! Oldest file: {oldest_date.strftime('%Y-%m-%d')} ({age_days} days old)")
            else:
                logger.warning(f"\n[0/7] No existing data found")

            logger.info(f"       Fetching fresh data from pack '{fetch_pack}'...")

            # Determine raw data directory from input pattern
            raw_dir = Path(input_pattern).parent
            if "*" in str(raw_dir):
                raw_dir = Path("data/raw")

            num_fetched = _fetch_fresh_data(
                pack_name=fetch_pack,
                output_dir=raw_dir,
                limit_per_sub=fetch_limit_per_sub,
                clear_old=True
            )

            if num_fetched == 0:
                raise ValueError("Failed to fetch any posts. Check network connection and subreddit pack.")

            logger.info(f"       Fetched {num_fetched} fresh posts")
        else:
            logger.info(f"\n[0/7] Data is fresh (oldest: {oldest_date.strftime('%Y-%m-%d %H:%M')})")

    # ========================================================================
    # STEP 1: Load posts
    # ========================================================================
    logger.info("\n[1/7] Loading posts...")

    posts_files = glob.glob(input_pattern)
    if not posts_files:
        if auto_fetch:
            raise FileNotFoundError(f"No files found after fetch. Pattern: {input_pattern}")
        else:
            raise FileNotFoundError(f"No files found matching pattern: {input_pattern}. Consider enabling auto_fetch=True.")

    all_posts = []
    for file_path in posts_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            posts_data = json.load(f)
            all_posts.extend([Post(**p) for p in posts_data])

    logger.info(f"Loaded {len(all_posts)} posts from {len(posts_files)} files")

    if len(all_posts) == 0:
        raise ValueError("No posts loaded. Cannot proceed with empty dataset.")

    # ========================================================================
    # STEP 2: Generate embeddings
    # ========================================================================
    logger.info("\n[2/7] Generating embeddings...")

    embeddings, metadata, embed_cost = embed_posts(
        posts=all_posts,
        model=config.ns_embed_model,
        api_key=config.openai_api_key,
        output_dir=output_dir
    )

    logger.info(f"Generated embeddings. Cost: ${embed_cost:.4f}")

    # ========================================================================
    # STEP 3: Clustering
    # ========================================================================
    logger.info("\n[3/7] Clustering...")

    n_clusters = min(config.ns_num_clusters, len(all_posts))
    labels, _ = cluster(embeddings, n_clusters=n_clusters)

    cluster_data = get_cluster_data(labels, metadata, embeddings)

    logger.info(f"Created {len(cluster_data)} clusters")

    # ========================================================================
    # STEP 4: Run enriched pipeline
    # ========================================================================
    logger.info(f"\n[4/7] Running enriched pipeline ({mode} mode)...")
    logger.info("   - Multi-model enrichment")
    logger.info("   - Trend scoring (LLM + historical)")
    logger.info("   - Founder fit scoring")
    logger.info("   - Sector classification")
    logger.info(f"   - History penalty: {use_history_penalty}")
    logger.info(f"   - MMR reranking: {use_mmr}")

    # Adjust config based on mode
    original_top_k = config.ns_top_k_enrichment
    original_heavy_model = config.ns_heavy_model

    if mode == "light":
        # Use light model for everything
        config.ns_top_k_enrichment = 0  # No heavy model enrichment
        logger.info("   Using light model (gpt-4o-mini) for all insights")
    else:  # deep
        logger.info(f"   Using heavy model ({config.ns_heavy_model}) for TOP {config.ns_top_k_enrichment} insights")

    try:
        results = run_enriched_pipeline(
            cluster_data=cluster_data,
            embeddings=embeddings,
            labels=labels,
            output_dir=output_dir,
            use_mmr=use_mmr,
            use_history_penalty=use_history_penalty,
            run_mode=run_mode
        )
    finally:
        # Restore original config
        config.ns_top_k_enrichment = original_top_k
        config.ns_heavy_model = original_heavy_model

    # Get filtered insights (for display/export) and all insights (for DB)
    insights: List[EnrichedInsight] = results['insights']
    all_insights: List[EnrichedInsight] = results.get('all_insights', insights)
    total_cost = results['total_cost']
    summary_cost = results.get('summary_cost', 0.0)
    run_stats = results.get('run_stats')  # Step 5-bis instrumentation

    # Apply max_insights limit if specified (to filtered insights)
    if max_insights and len(insights) > max_insights:
        logger.info(f"Limiting insights to top {max_insights} (from {len(insights)})")
        insights = insights[:max_insights]

    logger.info(f"Generated {len(insights)} filtered insights ({len(all_insights)} total)")

    # ========================================================================
    # STEP 5: Export results
    # ========================================================================
    logger.info("\n[5/7] Exporting results...")

    # CSV export
    csv_path = output_dir / f"insights_{run_id}.csv"
    export_insights_to_csv(insights, csv_path)
    logger.info(f"   CSV: {csv_path}")

    # JSON export
    json_path = output_dir / f"results_{run_id}.json"
    stats_dict = {
        'run_id': run_id,
        'mode': mode,
        'config_name': config_name,
        'num_posts': len(all_posts),
        'num_clusters': len(cluster_data),
        'num_insights': len(insights),
        'embed_cost_usd': embed_cost,
        'summary_cost_usd': summary_cost,
        'total_cost_usd': total_cost
    }
    write_enriched_cluster_results(json_path, insights, stats_dict)
    logger.info(f"   JSON: {json_path}")

    # ========================================================================
    # STEP 6: Save to database
    # ========================================================================
    if save_to_db:
        logger.info("\n[6/7] Saving to database...")

        save_run(
            run_id=run_id,
            config_name=config_name or "default",
            mode=mode,
            nb_insights=len(all_insights),  # Save total count
            nb_clusters=len(cluster_data),
            total_cost_usd=total_cost,
            embed_cost_usd=embed_cost,
            summary_cost_usd=summary_cost,
            csv_path=str(csv_path),
            json_path=str(json_path),
            notes=f"Input: {input_pattern} | Mode: {run_mode} | Filtered: {len(insights)}",
            run_stats=run_stats,  # Step 5-bis instrumentation
            db_path=db_path
        )

        # Save ALL insights to DB (including non-SaaS and duplicates)
        # This allows querying them later with filters
        save_insights(
            run_id=run_id,
            insights=all_insights,
            db_path=db_path
        )

        db_location = get_db_path(db_path)
        logger.info(f"   Database: {db_location}")
        logger.info(f"   Saved {len(all_insights)} insights (filtered: {len(insights)})")
    else:
        logger.info("\n[6/7] Skipping database save (disabled)")

    # ========================================================================
    # Summary
    # ========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("✅ Scan complete!")
    logger.info("=" * 60)
    logger.info(f"   Run ID: {run_id}")
    logger.info(f"   Insights: {len(insights)}")
    logger.info(f"   Clusters: {len(cluster_data)}")
    logger.info(f"   Total cost: ${total_cost:.4f}")
    logger.info(f"   CSV: {csv_path}")
    logger.info(f"   JSON: {json_path}")
    if save_to_db:
        logger.info(f"   Database: {get_db_path(db_path)}")
    logger.info("=" * 60)

    # Show top 3 insights
    if insights:
        logger.info("\n🏆 Top 3 insights:")
        for i, insight in enumerate(insights[:3], 1):
            logger.info(f"   #{i}: {insight.summary.title}")
            logger.info(f"        Priority: {insight.priority_score:.2f} | "
                       f"Pain: {insight.summary.pain_score_llm} | "
                       f"Trend: {insight.trend_score:.1f} | "
                       f"Fit: {insight.founder_fit_score:.1f}")

    return run_id


def run_scan_for_worker(
    run_id: str,
    mode: str = "deep",
    run_mode: str = "discover",
    max_insights: Optional[int] = None,
    input_pattern: str = "data/raw/posts_*.json",
    config_name: Optional[str] = None,
    progress_callback: Optional[callable] = None,
    auto_fetch: bool = True,
    max_data_age_days: int = 1,
    fetch_pack: str = "multi_sector",
    fetch_limit_per_sub: int = 30,
) -> Dict:
    """
    Run the scan pipeline for a worker process.

    This is similar to run_scan() but designed for the job queue worker:
    - Uses a pre-assigned run_id (from the job queue)
    - Returns results as a dictionary (caller saves to DB)
    - Accepts a progress_callback for real-time progress updates
    - Does NOT save run metadata to DB (worker handles that)

    Args:
        run_id: Pre-assigned run identifier from job queue
        mode: "light" or "deep" - controls LLM enrichment level
        run_mode: "discover" (filter duplicates/non-SaaS) or "track" (show all)
        max_insights: Optional limit on number of insights
        input_pattern: Glob pattern for input JSON files
        config_name: Optional configuration name
        progress_callback: Optional callback(progress: int, message: str)
        auto_fetch: Automatically fetch fresh data if stale
        max_data_age_days: Max age of data before refetch
        fetch_pack: Subreddit pack to use for fetch
        fetch_limit_per_sub: Posts per subreddit when fetching

    Returns:
        Dictionary with results:
        - nb_insights: int
        - nb_clusters: int
        - total_cost_usd: float
        - embed_cost_usd: float
        - summary_cost_usd: float
        - csv_path: str
        - json_path: str
        - notes: str
        - run_stats: dict (optional)
        - insights: List[EnrichedInsight]

    Raises:
        FileNotFoundError: If no input files match the pattern
        ValueError: If invalid mode specified
    """
    # Validate mode
    if mode not in ["light", "deep"]:
        raise ValueError(f"Invalid mode '{mode}'. Must be 'light' or 'deep'.")

    # Load configuration
    config = get_config()

    # Setup output directory
    output_dir = Path("data/results_v2")
    output_dir.mkdir(parents=True, exist_ok=True)

    def update_progress(pct: int, msg: str = ""):
        if progress_callback:
            progress_callback(pct, msg)

    logger.info("=" * 60)
    logger.info(f"Need Scanner Worker - Run ID: {run_id}")
    logger.info(f"   Mode: {mode}")
    logger.info(f"   Run Mode: {run_mode}")
    logger.info(f"   Config: {config_name or 'default'}")
    logger.info("=" * 60)

    update_progress(0, "Starting scan")

    # ========================================================================
    # STEP 0: Check data freshness and auto-fetch if needed (0-10%)
    # ========================================================================
    if auto_fetch:
        is_fresh, oldest_date = _check_data_freshness(input_pattern, max_data_age_days)

        if not is_fresh:
            update_progress(2, "Fetching fresh data")
            logger.info("[0/7] Fetching fresh data...")

            raw_dir = Path(input_pattern).parent
            if "*" in str(raw_dir):
                raw_dir = Path("data/raw")

            num_fetched = _fetch_fresh_data(
                pack_name=fetch_pack,
                output_dir=raw_dir,
                limit_per_sub=fetch_limit_per_sub,
                clear_old=True
            )

            if num_fetched == 0:
                raise ValueError("Failed to fetch any posts. Check network connection.")

            logger.info(f"       Fetched {num_fetched} fresh posts")
        else:
            logger.info(f"[0/7] Data is fresh (oldest: {oldest_date.strftime('%Y-%m-%d %H:%M')})")

    update_progress(10, "Loading posts")

    # ========================================================================
    # STEP 1: Load posts (10-15%)
    # ========================================================================
    logger.info("[1/7] Loading posts...")

    posts_files = glob.glob(input_pattern)
    if not posts_files:
        if auto_fetch:
            raise FileNotFoundError(f"No files found after fetch. Pattern: {input_pattern}")
        else:
            raise FileNotFoundError(f"No files found matching pattern: {input_pattern}")

    all_posts = []
    for file_path in posts_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            posts_data = json.load(f)
            all_posts.extend([Post(**p) for p in posts_data])

    logger.info(f"Loaded {len(all_posts)} posts from {len(posts_files)} files")

    if len(all_posts) == 0:
        raise ValueError("No posts loaded. Cannot proceed with empty dataset.")

    update_progress(15, "Generating embeddings")

    # ========================================================================
    # STEP 2: Generate embeddings (15-30%)
    # ========================================================================
    logger.info("[2/7] Generating embeddings...")

    embeddings, metadata, embed_cost = embed_posts(
        posts=all_posts,
        model=config.ns_embed_model,
        api_key=config.openai_api_key,
        output_dir=output_dir
    )

    logger.info(f"Generated embeddings. Cost: ${embed_cost:.4f}")

    update_progress(30, "Clustering")

    # ========================================================================
    # STEP 3: Clustering (30-40%)
    # ========================================================================
    logger.info("[3/7] Clustering...")

    n_clusters = min(config.ns_num_clusters, len(all_posts))
    labels, _ = cluster(embeddings, n_clusters=n_clusters)

    cluster_data = get_cluster_data(labels, metadata, embeddings)

    logger.info(f"Created {len(cluster_data)} clusters")

    update_progress(40, "Running enriched pipeline")

    # ========================================================================
    # STEP 4: Run enriched pipeline (40-80%)
    # ========================================================================
    logger.info(f"[4/7] Running enriched pipeline ({mode} mode)...")

    original_top_k = config.ns_top_k_enrichment
    original_heavy_model = config.ns_heavy_model

    if mode == "light":
        config.ns_top_k_enrichment = 0
        logger.info("   Using light model (gpt-4o-mini) for all insights")
    else:
        logger.info(f"   Using heavy model ({config.ns_heavy_model}) for TOP {config.ns_top_k_enrichment} insights")

    try:
        results = run_enriched_pipeline(
            cluster_data=cluster_data,
            embeddings=embeddings,
            labels=labels,
            output_dir=output_dir,
            use_mmr=True,
            use_history_penalty=True,
            run_mode=run_mode
        )
    finally:
        config.ns_top_k_enrichment = original_top_k
        config.ns_heavy_model = original_heavy_model

    insights: List[EnrichedInsight] = results['insights']
    all_insights: List[EnrichedInsight] = results.get('all_insights', insights)
    total_cost = results['total_cost']
    summary_cost = results.get('summary_cost', 0.0)
    run_stats = results.get('run_stats')

    if max_insights and len(insights) > max_insights:
        logger.info(f"Limiting insights to top {max_insights} (from {len(insights)})")
        insights = insights[:max_insights]

    logger.info(f"Generated {len(insights)} filtered insights ({len(all_insights)} total)")

    update_progress(80, "Exporting results")

    # ========================================================================
    # STEP 5: Export results (80-95%)
    # ========================================================================
    logger.info("[5/7] Exporting results...")

    csv_path = output_dir / f"insights_{run_id}.csv"
    export_insights_to_csv(insights, csv_path)
    logger.info(f"   CSV: {csv_path}")

    json_path = output_dir / f"results_{run_id}.json"
    stats_dict = {
        'run_id': run_id,
        'mode': mode,
        'config_name': config_name,
        'num_posts': len(all_posts),
        'num_clusters': len(cluster_data),
        'num_insights': len(insights),
        'embed_cost_usd': embed_cost,
        'summary_cost_usd': summary_cost,
        'total_cost_usd': total_cost
    }
    write_enriched_cluster_results(json_path, insights, stats_dict)
    logger.info(f"   JSON: {json_path}")

    update_progress(95, "Finalizing")

    # ========================================================================
    # Summary
    # ========================================================================
    logger.info("=" * 60)
    logger.info("Scan complete!")
    logger.info("=" * 60)
    logger.info(f"   Run ID: {run_id}")
    logger.info(f"   Insights: {len(all_insights)}")
    logger.info(f"   Clusters: {len(cluster_data)}")
    logger.info(f"   Total cost: ${total_cost:.4f}")
    logger.info("=" * 60)

    update_progress(100, "Complete")

    # Return results for the worker to save
    return {
        "nb_insights": len(all_insights),
        "nb_clusters": len(cluster_data),
        "total_cost_usd": total_cost,
        "embed_cost_usd": embed_cost,
        "summary_cost_usd": summary_cost,
        "csv_path": str(csv_path),
        "json_path": str(json_path),
        "notes": f"Input: {input_pattern} | Mode: {run_mode} | Filtered: {len(insights)}",
        "run_stats": run_stats,
        "insights": all_insights,  # All insights (including filtered)
    }


def list_recent_runs(limit: int = 10, db_path: Optional[Path] = None) -> List[Dict]:
    """
    List recent scan runs from database.

    Args:
        limit: Maximum number of runs to return
        db_path: Custom database path (optional)

    Returns:
        List of run dictionaries with metadata

    Example:
        >>> from need_scanner.core import list_recent_runs
        >>> runs = list_recent_runs(limit=5)
        >>> for run in runs:
        ...     print(f"{run['id']}: {run['nb_insights']} insights")
    """
    from .db import list_runs

    return list_runs(limit=limit, db_path=db_path)


def get_insights_for_run(
    run_id: str,
    limit: Optional[int] = None,
    db_path: Optional[Path] = None
) -> List[Dict]:
    """
    Get insights for a specific run from database.

    Args:
        run_id: Run identifier
        limit: Optional limit on results
        db_path: Custom database path (optional)

    Returns:
        List of insight dictionaries

    Example:
        >>> from need_scanner.core import get_insights_for_run
        >>> insights = get_insights_for_run("20251125_143022", limit=10)
        >>> print(f"Found {len(insights)} insights")
    """
    from .db import get_run_insights

    return get_run_insights(run_id=run_id, limit=limit, db_path=db_path)
