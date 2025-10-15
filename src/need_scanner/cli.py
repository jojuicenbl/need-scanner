"""CLI for need_scanner using Typer."""

import typer
from pathlib import Path
from typing import Optional
from loguru import logger
import glob

from .config import get_config
from .utils import setup_logger, ensure_dir, format_cost, read_json
from .schemas import Insight, ProcessingStats
from .fetchers.reddit import fetch_subreddit_new, load_posts_from_json
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
def run(
    input_pattern: str = typer.Option("data/raw/posts_*.json", help="Input file pattern"),
    clusters: int = typer.Option(None, help="Number of clusters"),
    model_sum: str = typer.Option(None, help="Summary model"),
    max_examples: int = typer.Option(None, help="Max examples per cluster"),
    output_dir: Path = typer.Option(Path("data"), help="Output directory")
):
    """
    Run complete pipeline: clean, dedupe, embed, cluster, summarize, export.

    Example: python -m need_scanner run --input "data/raw/posts_*.json" --clusters 10
    """
    setup_logger()

    # Load config
    config = get_config()

    # Use config defaults if not specified
    n_clusters = clusters or config.ns_num_clusters
    summary_model = model_sum or config.ns_summary_model
    max_docs = max_examples or config.ns_max_docs_per_cluster

    logger.info("=" * 60)
    logger.info("NEED SCANNER PIPELINE")
    logger.info("=" * 60)

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

    # 7. Score and create insights
    logger.info("\n[7/7] Computing pain scores and creating insights...")
    insights = []

    for summary in summaries:
        cluster_items = cluster_data[summary.cluster_id]
        meta_items = [item["meta"] for item in cluster_items]

        # Heuristic score
        heuristic_score = compute_pain_score(meta_items)

        # Combined score
        final_score = combine_scores(summary.pain_score_llm, heuristic_score)

        # Create insight
        insight = Insight(
            cluster_id=summary.cluster_id,
            examples=meta_items[:5],  # Top 5 examples
            summary=summary,
            pain_score_final=final_score
        )
        insights.append(insight)

    # Sort by pain score
    insights.sort(key=lambda x: x.pain_score_final or 0, reverse=True)

    # Export
    logger.info("\nExporting results...")
    ensure_dir(output_dir)

    # Statistics
    stats = {
        "total_posts": len(all_posts),
        "after_cleaning": len(clean_posts),
        "after_dedup": len(deduped_posts),
        "num_clusters": len(cluster_data),
        "embeddings_cost_usd": round(embed_cost, 4),
        "summary_cost_usd": round(summary_cost, 4),
        "total_cost_usd": round(embed_cost + summary_cost, 4)
    }

    # Write outputs
    write_cluster_results(
        output_dir / "cluster_results.json",
        insights,
        stats
    )

    write_insights_csv(
        output_dir / "insights.csv",
        insights
    )

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total posts: {stats['total_posts']}")
    logger.info(f"After cleaning: {stats['after_cleaning']}")
    logger.info(f"After dedup: {stats['after_dedup']}")
    logger.info(f"Clusters: {stats['num_clusters']}")
    logger.info(f"Insights generated: {len(insights)}")
    logger.info(f"\nCost breakdown:")
    logger.info(f"  Embeddings: {format_cost(embed_cost)}")
    logger.info(f"  Summaries:  {format_cost(summary_cost)}")
    logger.info(f"  Total:      {format_cost(embed_cost + summary_cost)}")
    logger.info(f"\nOutputs:")
    logger.info(f"  {output_dir / 'cluster_results.json'}")
    logger.info(f"  {output_dir / 'insights.csv'}")
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


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
