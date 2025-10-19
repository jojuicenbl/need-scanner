#!/usr/bin/env python
"""Test complet du Sprint 1 - Pipeline enrichi avec 50 posts."""

import json
import sys
from pathlib import Path

sys.path.insert(0, 'src')

from need_scanner.config import get_config
from need_scanner.schemas import Post, EnrichedInsight
from need_scanner.utils import setup_logger, write_json, ensure_dir
from need_scanner.analysis.intent import filter_by_intent
from need_scanner.analysis.wtp import enrich_posts_with_wtp
from need_scanner.processing.filters import filter_by_language
from need_scanner.processing.clean import normalize
from need_scanner.processing.dedupe import dedupe
from need_scanner.processing.embed import embed_posts
from need_scanner.processing.cluster import cluster, get_cluster_data
from need_scanner.analysis.summarize import summarize_all_clusters_enriched
from need_scanner.analysis.scoring import compute_pain_score
from need_scanner.analysis.priority import (
    calculate_traction_score,
    calculate_novelty_score,
    calculate_priority_score,
    calculate_avg_wtp_score,
    rank_insights
)
from need_scanner.export.writer import write_cluster_results
from loguru import logger


def main():
    setup_logger()

    logger.info("=" * 70)
    logger.info("TEST SPRINT 1 - PIPELINE ENRICHI")
    logger.info("=" * 70)

    config = get_config()

    # 1. Load 50 posts from multi-sector collection
    logger.info("\n[1/9] Loading posts from multi-sector Reddit collection...")
    posts_file = Path("data/raw/posts_reddit_multi_20251016_160711.json")

    if not posts_file.exists():
        logger.error(f"File not found: {posts_file}")
        logger.info("Run 'python -m need_scanner collect-reddit-multi' first")
        return

    with open(posts_file) as f:
        posts_data = json.load(f)

    # Convert to Post objects (take first 200 for better filtering results)
    all_posts = []
    for p in posts_data[:200]:
        try:
            post = Post(**p)
            all_posts.append(post)
        except Exception as e:
            logger.warning(f"Failed to parse post: {e}")
            continue

    logger.info(f"Loaded {len(all_posts)} posts")

    # 2. Language filter (keep English only for now)
    logger.info("\n[2/9] Filtering by language...")
    filtered_posts = filter_by_language(all_posts, allowed_languages=["en"])

    # 3. Enrich with WTP signals
    logger.info("\n[3/9] Detecting WTP signals...")
    filtered_posts = enrich_posts_with_wtp(filtered_posts)

    # 4. Intent classification and filtering (include howto which can signal needs)
    logger.info("\n[4/9] Classifying intent and filtering...")
    filtered_posts = filter_by_intent(filtered_posts, allowed_intents=["pain", "request", "howto"])

    if len(filtered_posts) < 10:
        logger.error(f"Not enough posts after filtering ({len(filtered_posts)}). Need at least 10.")
        return

    logger.info(f"After filtering: {len(filtered_posts)} posts")

    # Take exactly 50 for the test (or less if we don't have enough)
    test_posts = filtered_posts[:min(50, len(filtered_posts))]
    logger.info(f"Using {len(test_posts)} posts for test")

    # 5. Clean and dedupe
    logger.info("\n[5/9] Cleaning and deduplicating...")
    clean_posts = normalize(test_posts)
    deduped_posts = dedupe(clean_posts)

    if len(deduped_posts) < 5:
        logger.error(f"Not enough posts after dedup ({len(deduped_posts)}). Need at least 5.")
        return

    # 6. Embed
    logger.info("\n[6/9] Generating embeddings...")
    output_dir = Path("data/sprint1_test")
    ensure_dir(output_dir)

    embeddings, metadata, embed_cost = embed_posts(
        posts=deduped_posts,
        model=config.ns_embed_model,
        api_key=config.openai_api_key,
        output_dir=output_dir
    )

    # 7. Cluster
    logger.info("\n[7/9] Clustering...")
    n_clusters = min(5, len(deduped_posts) // 2)  # At least 2 posts per cluster
    labels, kmeans_model = cluster(embeddings, n_clusters)
    cluster_data = get_cluster_data(labels, metadata, embeddings)

    # 8. Summarize with ENRICHED prompt
    logger.info("\n[8/9] Summarizing clusters with ENRICHED analysis...")
    summaries, summary_cost = summarize_all_clusters_enriched(
        cluster_data=cluster_data,
        model=config.ns_summary_model,
        api_key=config.openai_api_key,
        max_examples=5,
        max_input_tokens=config.ns_max_input_tokens_per_prompt,
        max_output_tokens=800,  # Increased for enriched output
        cost_warn_threshold=config.ns_cost_warn_prompt_usd
    )

    if not summaries:
        logger.error("No summaries generated")
        return

    # 9. Create insights with PRIORITY SCORING
    logger.info("\n[9/9] Computing priority scores and ranking...")
    insights = []

    for summary in summaries:
        cluster_items = cluster_data[summary.cluster_id]
        meta_items = [item["meta"] for item in cluster_items]

        # Get original Post objects for this cluster
        cluster_posts = [p for p in deduped_posts if p.id in [m["id"] for m in meta_items]]

        # Heuristic score
        heuristic_score = compute_pain_score(meta_items)

        # Traction score
        traction_score = calculate_traction_score(meta_items)

        # Novelty score
        novelty_score = calculate_novelty_score(summary, meta_items)

        # WTP score (average for cluster)
        wtp_score = calculate_avg_wtp_score(cluster_posts)

        # Priority score
        pain_llm = summary.pain_score_llm or 5.0
        priority_score = calculate_priority_score(
            pain_score_llm=pain_llm,
            heuristic_score=heuristic_score,
            traction_score=traction_score,
            novelty_score=novelty_score,
            wtp_score=wtp_score
        )

        # Combined pain score
        pain_final = int((pain_llm * 0.7 + heuristic_score * 0.3))

        # Get source mix
        source_mix = list(set(m.get("source", "unknown") for m in meta_items))

        # Create enriched insight
        insight = EnrichedInsight(
            cluster_id=summary.cluster_id,
            rank=0,  # Will be set by ranking
            priority_score=priority_score,
            examples=meta_items[:5],
            summary=summary,
            pain_score_final=pain_final,
            heuristic_score=heuristic_score,
            traction_score=traction_score,
            novelty_score=novelty_score,
            source_mix=source_mix
        )
        insights.append(insight)

    # Rank insights by priority
    ranked_insights = rank_insights(insights)

    # Export results
    logger.info("\nExporting results...")
    stats = {
        "total_posts": len(all_posts),
        "after_language_filter": len(filtered_posts) + len(all_posts) - len(filtered_posts),
        "after_wtp_enrichment": len(filtered_posts),
        "after_intent_filter": len(test_posts),
        "after_cleaning": len(clean_posts),
        "after_dedup": len(deduped_posts),
        "num_clusters": len(cluster_data),
        "embeddings_cost_usd": round(embed_cost, 4),
        "summary_cost_usd": round(summary_cost, 4),
        "total_cost_usd": round(embed_cost + summary_cost, 4)
    }

    # Convert to serializable format for JSON export
    insights_data = []
    for ins in ranked_insights:
        insights_data.append({
            "cluster_id": ins.cluster_id,
            "rank": ins.rank,
            "priority_score": ins.priority_score,
            "examples": ins.examples[:3],
            "summary": {
                "cluster_id": ins.summary.cluster_id,
                "size": ins.summary.size,
                "title": ins.summary.title,
                "problem": ins.summary.problem,
                "persona": ins.summary.persona,
                "jtbd": ins.summary.jtbd,
                "context": ins.summary.context,
                "monetizable": ins.summary.monetizable,
                "mvp": ins.summary.mvp,
                "alternatives": ins.summary.alternatives,
                "willingness_to_pay_signal": ins.summary.willingness_to_pay_signal,
                "pain_score_llm": ins.summary.pain_score_llm
            },
            "pain_score_final": ins.pain_score_final,
            "heuristic_score": ins.heuristic_score,
            "traction_score": ins.traction_score,
            "novelty_score": ins.novelty_score,
            "source_mix": ins.source_mix
        })

    output_data = {
        "insights": insights_data,
        "statistics": stats
    }

    write_json(output_dir / "enriched_results.json", output_data)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SPRINT 1 COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total posts: {stats['total_posts']}")
    logger.info(f"After filtering: {stats['after_intent_filter']}")
    logger.info(f"After dedup: {stats['after_dedup']}")
    logger.info(f"Clusters: {stats['num_clusters']}")
    logger.info(f"Insights generated: {len(ranked_insights)}")
    logger.info(f"\nCost breakdown:")
    logger.info(f"  Embeddings: ${embed_cost:.4f}")
    logger.info(f"  Summaries:  ${summary_cost:.4f}")
    logger.info(f"  Total:      ${embed_cost + summary_cost:.4f}")
    logger.info(f"\nOutputs:")
    logger.info(f"  {output_dir / 'enriched_results.json'}")
    logger.info(f"  {output_dir / 'embeddings.npy'}")
    logger.info(f"  {output_dir / 'meta.json'}")

    logger.info("\n" + "=" * 70)
    logger.info("TOP 3 INSIGHTS BY PRIORITY:")
    logger.info("=" * 70)
    for ins in ranked_insights[:3]:
        logger.info(f"\n#{ins.rank}: {ins.summary.title}")
        logger.info(f"  Priority Score: {ins.priority_score:.2f}/10.0")
        logger.info(f"  Persona: {ins.summary.persona}")
        logger.info(f"  JTBD: {ins.summary.jtbd[:80]}...")
        logger.info(f"  Pain (LLM): {ins.summary.pain_score_llm}/10")
        logger.info(f"  Traction: {ins.traction_score:.1f}/10")
        logger.info(f"  Novelty: {ins.novelty_score:.1f}/10")
        logger.info(f"  Alternatives: {ins.summary.alternatives}")
        logger.info(f"  WTP Signal: {ins.summary.willingness_to_pay_signal[:80]}...")
        logger.info(f"  MVP: {ins.summary.mvp[:100]}...")


if __name__ == "__main__":
    main()
