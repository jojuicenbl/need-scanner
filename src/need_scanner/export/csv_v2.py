"""CSV export for v2.0 enriched insights."""

import csv
from pathlib import Path
from typing import List
from loguru import logger

from ..schemas import EnrichedInsight


def export_insights_to_csv(
    insights: List[EnrichedInsight],
    output_path: Path
) -> None:
    """
    Export enriched insights to CSV file (v2.0 format).

    Args:
        insights: List of EnrichedInsight objects
        output_path: Path to output CSV file
    """
    if not insights:
        logger.warning("No insights to export")
        return

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Define CSV columns
    fieldnames = [
        # Ranking & Scores
        'rank',
        'mmr_rank',
        'priority_score',
        'priority_score_adjusted',

        # Cluster info
        'cluster_id',
        'size',
        'sector',

        # Content
        'title',
        'problem',
        'persona',
        'jtbd',
        'context',

        # Business
        'monetizable',
        'mvp',
        'alternatives',
        'willingness_to_pay_signal',

        # Scores
        'pain_score_llm',
        'pain_score_final',
        'heuristic_score',
        'traction_score',
        'novelty_score',
        'trend_score',
        'founder_fit_score',

        # Examples
        'example_urls',
        'source_mix',
        'keywords_matched'
    ]

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for insight in insights:
            # Prepare alternatives as string (filter out None values)
            alternatives = insight.summary.alternatives or []
            alternatives_str = ', '.join([alt for alt in alternatives if alt]) if alternatives else ''

            # Prepare example URLs (filter out None values)
            example_urls = ', '.join([
                ex.get('url', '') or '' for ex in insight.examples[:3] if ex.get('url')
            ])

            # Prepare source mix (filter out None values)
            source_mix = insight.source_mix or []
            source_mix_str = ', '.join([src for src in source_mix if src]) if source_mix else ''

            # Prepare keywords (filter out None values)
            keywords = insight.keywords_matched or []
            keywords_str = ', '.join([kw for kw in keywords if kw]) if keywords else ''

            row = {
                # Ranking & Scores
                'rank': insight.rank,
                'mmr_rank': insight.mmr_rank or '',
                'priority_score': f"{insight.priority_score:.2f}",
                'priority_score_adjusted': f"{insight.priority_score_adjusted:.2f}" if insight.priority_score_adjusted else '',

                # Cluster info
                'cluster_id': insight.cluster_id,
                'size': insight.summary.size,
                'sector': insight.summary.sector or '',

                # Content
                'title': insight.summary.title,
                'problem': insight.summary.problem,
                'persona': insight.summary.persona,
                'jtbd': insight.summary.jtbd,
                'context': insight.summary.context,

                # Business
                'monetizable': 'Yes' if insight.summary.monetizable else 'No',
                'mvp': insight.summary.mvp,
                'alternatives': alternatives_str,
                'willingness_to_pay_signal': insight.summary.willingness_to_pay_signal,

                # Scores
                'pain_score_llm': insight.summary.pain_score_llm or '',
                'pain_score_final': insight.pain_score_final or '',
                'heuristic_score': f"{insight.heuristic_score:.1f}" if insight.heuristic_score else '',
                'traction_score': f"{insight.traction_score:.1f}" if insight.traction_score else '',
                'novelty_score': f"{insight.novelty_score:.1f}" if insight.novelty_score else '',
                'trend_score': f"{insight.trend_score:.1f}" if insight.trend_score else '',
                'founder_fit_score': f"{insight.founder_fit_score:.1f}" if insight.founder_fit_score else '',

                # Examples
                'example_urls': example_urls,
                'source_mix': source_mix_str,
                'keywords_matched': keywords_str
            }

            writer.writerow(row)

    logger.info(f"Exported {len(insights)} insights to {output_path}")
