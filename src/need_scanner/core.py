"""Core module exposing the main Need Scanner pipeline as a reusable function."""

import glob
import json
from pathlib import Path
from typing import Optional, Dict, List
from loguru import logger

from .config import get_config
from .schemas import Post, EnrichedInsight
from .processing.embed import embed_posts
from .processing.cluster import cluster, get_cluster_data
from .jobs.enriched_pipeline import run_enriched_pipeline
from .export.csv_v2 import export_insights_to_csv
from .export.writer import write_enriched_cluster_results
from .db import (
    init_database,
    generate_run_id,
    save_run,
    save_insights,
    get_db_path
)


def run_scan(
    config_name: Optional[str] = None,
    mode: str = "deep",
    max_insights: Optional[int] = None,
    input_pattern: str = "data/raw/posts_*.json",
    output_dir: Optional[Path] = None,
    save_to_db: bool = True,
    db_path: Optional[Path] = None,
    use_mmr: bool = True,
    use_history_penalty: bool = True
) -> str:
    """
    Run complete Need Scanner pipeline and return run_id.

    This is the main entry point for programmatic usage of Need Scanner.
    It orchestrates the full pipeline:
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
    logger.info(f"🚀 Need Scanner - Run ID: {run_id}")
    logger.info(f"   Mode: {mode}")
    logger.info(f"   Config: {config_name or 'default'}")
    logger.info("=" * 60)

    # ========================================================================
    # STEP 1: Load posts
    # ========================================================================
    logger.info("\n[1/6] Loading posts...")

    posts_files = glob.glob(input_pattern)
    if not posts_files:
        raise FileNotFoundError(f"No files found matching pattern: {input_pattern}")

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
    logger.info("\n[2/6] Generating embeddings...")

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
    logger.info("\n[3/6] Clustering...")

    n_clusters = min(config.ns_num_clusters, len(all_posts))
    labels, _ = cluster(embeddings, n_clusters=n_clusters)

    cluster_data = get_cluster_data(labels, metadata, embeddings)

    logger.info(f"Created {len(cluster_data)} clusters")

    # ========================================================================
    # STEP 4: Run enriched pipeline
    # ========================================================================
    logger.info(f"\n[4/6] Running enriched pipeline ({mode} mode)...")
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
            use_history_penalty=use_history_penalty
        )
    finally:
        # Restore original config
        config.ns_top_k_enrichment = original_top_k
        config.ns_heavy_model = original_heavy_model

    insights: List[EnrichedInsight] = results['insights']
    total_cost = results['total_cost']
    summary_cost = results.get('summary_cost', 0.0)

    # Apply max_insights limit if specified
    if max_insights and len(insights) > max_insights:
        logger.info(f"Limiting insights to top {max_insights} (from {len(insights)})")
        insights = insights[:max_insights]

    logger.info(f"Generated {len(insights)} insights")

    # ========================================================================
    # STEP 5: Export results
    # ========================================================================
    logger.info("\n[5/6] Exporting results...")

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
        logger.info("\n[6/6] Saving to database...")

        save_run(
            run_id=run_id,
            config_name=config_name or "default",
            mode=mode,
            nb_insights=len(insights),
            nb_clusters=len(cluster_data),
            total_cost_usd=total_cost,
            embed_cost_usd=embed_cost,
            summary_cost_usd=summary_cost,
            csv_path=str(csv_path),
            json_path=str(json_path),
            notes=f"Input: {input_pattern}",
            db_path=db_path
        )

        save_insights(
            run_id=run_id,
            insights=insights,
            db_path=db_path
        )

        db_location = get_db_path(db_path)
        logger.info(f"   Database: {db_location}")
    else:
        logger.info("\n[6/6] Skipping database save (disabled)")

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
