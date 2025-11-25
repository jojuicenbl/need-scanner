"""Enhanced pipeline with sector tagging, MMR, and history-based deduplication."""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

from ..config import get_config
from ..schemas import EnrichedClusterSummary, EnrichedInsight
from ..processing.cluster import get_cluster_data
from ..processing.history import load_or_create_history
from ..processing.mmr import mmr_rerank, mmr_rerank_by_sector
from ..analysis.sector import classify_all_clusters_sectors
from ..analysis.summarize import summarize_enriched_cluster
from ..analysis.priority import (
    calculate_traction_score,
    calculate_novelty_score,
    calculate_priority_score,
    enrich_insight_with_priority
)
from ..analysis.scoring import compute_pain_score
from ..analysis.wtp import detect_wtp_signals, get_wtp_score
from ..utils import format_cost


def run_enriched_pipeline(
    cluster_data: Dict[int, List[dict]],
    embeddings: np.ndarray,
    labels: np.ndarray,
    output_dir: Path,
    history_path: Optional[Path] = None,
    use_mmr: bool = True,
    use_history_penalty: bool = True
) -> Dict:
    """
    Run the enhanced pipeline with all improvements.

    Pipeline steps:
    1. Compute initial priority scores (heuristic)
    2. Enrich TOP K clusters with heavy model (persona, JTBD, etc.)
    3. Enrich remaining clusters with light model (or skip)
    4. Classify sectors for all clusters
    5. Apply history-based similarity penalty
    6. MMR reranking for diversity
    7. Save results and update history

    Args:
        cluster_data: Dict mapping cluster_id to list of items
        embeddings: Array of all embeddings (N, D)
        labels: Array of cluster labels (N,)
        output_dir: Output directory
        history_path: Path to history file (defaults to data/history/clusters.jsonl)
        use_mmr: Whether to use MMR reranking
        use_history_penalty: Whether to apply history penalty

    Returns:
        Dict with pipeline results and stats
    """
    config = get_config()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if history_path is None:
        history_path = Path("data/history/clusters.jsonl")

    logger.info("=" * 60)
    logger.info("ENHANCED PIPELINE - Multi-sector market discovery")
    logger.info("=" * 60)

    # ========================================================================
    # STEP 1: Initial scoring (heuristic)
    # ========================================================================
    logger.info("\n[STEP 1] Computing initial heuristic scores...")

    initial_scores = {}
    for cluster_id, items in cluster_data.items():
        meta_items = [item['meta'] for item in items]
        heuristic_score = compute_pain_score(meta_items)
        initial_scores[cluster_id] = heuristic_score

    # Sort clusters by initial score
    sorted_cluster_ids = sorted(
        initial_scores.keys(),
        key=lambda cid: initial_scores[cid],
        reverse=True
    )

    logger.info(f"Computed heuristic scores for {len(sorted_cluster_ids)} clusters")

    # ========================================================================
    # STEP 2: Enrichment with LLM (TOP K with heavy model)
    # ========================================================================
    logger.info(f"\n[STEP 2] Enriching TOP {config.ns_top_k_enrichment} clusters with heavy model ({config.ns_heavy_model})...")

    enriched_summaries = []
    total_cost = 0.0

    # Enrich TOP K with heavy model
    top_k_ids = sorted_cluster_ids[:config.ns_top_k_enrichment]

    for cluster_id in top_k_ids:
        items = cluster_data[cluster_id]
        texts = [item['meta']['title'] for item in items]

        summary, cost = summarize_enriched_cluster(
            texts=texts,
            cluster_id=cluster_id,
            cluster_size=len(items),
            model=config.ns_heavy_model,
            api_key=config.openai_api_key,
            max_examples=config.ns_max_docs_per_cluster,
            max_input_tokens=config.ns_max_input_tokens_per_prompt,
            max_output_tokens=config.ns_max_output_tokens,
            cost_warn_threshold=config.ns_cost_warn_prompt_usd
        )

        if summary:
            enriched_summaries.append(summary)
            total_cost += cost

    logger.info(f"Enriched {len(enriched_summaries)} top clusters. Cost: {format_cost(total_cost)}")

    # Enrich remaining clusters with light model (optional, or skip for cost control)
    remaining_ids = sorted_cluster_ids[config.ns_top_k_enrichment:]
    logger.info(f"\n[STEP 2b] Enriching {len(remaining_ids)} remaining clusters with light model ({config.ns_light_model})...")

    for cluster_id in remaining_ids:
        items = cluster_data[cluster_id]
        texts = [item['meta']['title'] for item in items]

        summary, cost = summarize_enriched_cluster(
            texts=texts,
            cluster_id=cluster_id,
            cluster_size=len(items),
            model=config.ns_light_model,
            api_key=config.openai_api_key,
            max_examples=min(config.ns_max_docs_per_cluster, 3),  # Fewer examples for light
            max_input_tokens=config.ns_max_input_tokens_per_prompt // 2,
            max_output_tokens=config.ns_max_output_tokens,
            cost_warn_threshold=config.ns_cost_warn_prompt_usd
        )

        if summary:
            enriched_summaries.append(summary)
            total_cost += cost

    logger.info(f"Total enriched clusters: {len(enriched_summaries)}. Total cost: {format_cost(total_cost)}")

    # ========================================================================
    # STEP 3: Sector classification
    # ========================================================================
    logger.info(f"\n[STEP 3] Classifying clusters into sectors with light model...")

    sectors_map = classify_all_clusters_sectors(
        clusters_summaries=enriched_summaries,
        model=config.ns_light_model,
        api_key=config.openai_api_key
    )

    # Add sector to summaries
    for summary in enriched_summaries:
        summary.sector = sectors_map.get(summary.cluster_id, 'other')

    # ========================================================================
    # STEP 4: Compute cluster embeddings (centroids)
    # ========================================================================
    logger.info("\n[STEP 4] Computing cluster embeddings...")

    cluster_embeddings = []
    cluster_ids_ordered = []

    for summary in enriched_summaries:
        cluster_id = summary.cluster_id
        items = cluster_data[cluster_id]

        # Get embeddings for this cluster
        item_embeddings = [item['embedding'] for item in items]
        centroid = np.mean(item_embeddings, axis=0)

        cluster_embeddings.append(centroid)
        cluster_ids_ordered.append(cluster_id)

    cluster_embeddings = np.array(cluster_embeddings)

    # ========================================================================
    # STEP 5: Priority scoring
    # ========================================================================
    logger.info("\n[STEP 5] Computing priority scores...")

    insights = []

    for i, summary in enumerate(enriched_summaries):
        cluster_id = summary.cluster_id
        items = cluster_data[cluster_id]
        meta_items = [item['meta'] for item in items]

        # Traction score
        traction_score = calculate_traction_score(meta_items)

        # Novelty score
        novelty_score = calculate_novelty_score(summary, meta_items)

        # WTP score
        wtp_scores = [get_wtp_score(item['meta']) for item in items]
        avg_wtp_score = np.mean(wtp_scores) if wtp_scores else 0.0

        # Priority score
        pain_llm = summary.pain_score_llm or 5.0
        heuristic = initial_scores.get(cluster_id, 5.0)

        priority_score = calculate_priority_score(
            pain_score_llm=pain_llm,
            heuristic_score=heuristic,
            traction_score=traction_score,
            novelty_score=novelty_score,
            wtp_score=avg_wtp_score
        )

        # Create insight
        insight = EnrichedInsight(
            cluster_id=cluster_id,
            rank=0,  # Will be set later
            priority_score=priority_score,
            examples=[item['meta'] for item in items[:5]],
            summary=summary,
            pain_score_final=int((pain_llm * 0.7 + heuristic * 0.3)),
            heuristic_score=heuristic,
            traction_score=traction_score,
            novelty_score=novelty_score,
            source_mix=list(set(item['meta'].get('source', 'unknown') for item in items))
        )

        insights.append(insight)

    # ========================================================================
    # STEP 6: History-based similarity penalty
    # ========================================================================
    if use_history_penalty:
        logger.info(f"\n[STEP 6] Applying history-based similarity penalty (factor={config.ns_history_penalty_factor})...")

        history = load_or_create_history(
            history_path=history_path,
            retention_days=config.ns_history_retention_days
        )

        # Extract priority scores
        priority_scores = np.array([ins.priority_score for ins in insights])

        # Apply penalty
        adjusted_scores = history.apply_penalty_to_scores(
            priority_scores=priority_scores,
            new_embeddings=cluster_embeddings,
            penalty_factor=config.ns_history_penalty_factor
        )

        # Update insights
        for i, insight in enumerate(insights):
            insight.priority_score_adjusted = float(adjusted_scores[i])

        logger.info("Applied history penalty to priority scores")
    else:
        logger.info("\n[STEP 6] Skipping history penalty (disabled)")
        for insight in insights:
            insight.priority_score_adjusted = insight.priority_score

    # ========================================================================
    # STEP 7: MMR reranking
    # ========================================================================
    if use_mmr:
        logger.info(f"\n[STEP 7] MMR reranking (λ={config.ns_mmr_lambda}, top_k={config.ns_mmr_top_k})...")

        # Use adjusted scores for MMR
        scores_for_mmr = np.array([
            ins.priority_score_adjusted or ins.priority_score
            for ins in insights
        ])

        # Extract sectors
        sectors = [ins.summary.sector for ins in insights]

        # MMR rerank by sector for diversity
        reranked_insights, selected_indices = mmr_rerank_by_sector(
            items=insights,
            embeddings=cluster_embeddings,
            priority_scores=scores_for_mmr,
            sectors=sectors,
            top_k_per_sector=2,  # Max 2 per sector
            lambda_param=config.ns_mmr_lambda
        )

        logger.info(f"MMR reranking complete. Selected {len(reranked_insights)} diverse insights.")
    else:
        logger.info("\n[STEP 7] Skipping MMR reranking (disabled)")
        # Just sort by adjusted score
        reranked_insights = sorted(
            insights,
            key=lambda x: x.priority_score_adjusted or x.priority_score,
            reverse=True
        )
        # Add MMR rank
        for i, insight in enumerate(reranked_insights, 1):
            insight.mmr_rank = i

    # Assign final ranks
    for i, insight in enumerate(reranked_insights, 1):
        insight.rank = i

    # ========================================================================
    # STEP 8: Save results
    # ========================================================================
    logger.info("\n[STEP 8] Saving results...")

    # Save JSON
    results_path = output_dir / "enriched_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(
            [insight.dict() for insight in reranked_insights],
            f,
            indent=2,
            ensure_ascii=False
        )

    logger.info(f"Saved enriched results to {results_path}")

    # Save CSV (optional - can be done with export module)

    # ========================================================================
    # STEP 9: Update history
    # ========================================================================
    if use_history_penalty:
        logger.info("\n[STEP 9] Updating history...")

        history.add_clusters(
            cluster_summaries=enriched_summaries,
            embeddings=cluster_embeddings,
            priority_scores=[ins.priority_score for ins in insights]
        )
        history.save()

        logger.info("History updated")
    else:
        logger.info("\n[STEP 9] Skipping history update (disabled)")

    # ========================================================================
    # Summary stats
    # ========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total clusters: {len(insights)}")
    logger.info(f"Top insights: {len(reranked_insights)}")
    logger.info(f"Total LLM cost: {format_cost(total_cost)}")

    # Show top 5
    logger.info("\nTOP 5 INSIGHTS:")
    for insight in reranked_insights[:5]:
        logger.info(
            f"  #{insight.rank} [{insight.summary.sector}] {insight.summary.title} "
            f"(priority: {insight.priority_score:.2f}, adjusted: {insight.priority_score_adjusted:.2f})"
        )

    return {
        'insights': reranked_insights,
        'total_cost': total_cost,
        'num_clusters': len(insights),
        'num_top_insights': len(reranked_insights)
    }
