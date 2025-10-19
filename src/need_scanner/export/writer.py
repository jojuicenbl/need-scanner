"""Export functions for results (JSON and CSV)."""

import csv
from pathlib import Path
from typing import List
from loguru import logger

from ..schemas import Insight, ClusterSummary, EnrichedInsight, EnrichedClusterSummary
from ..utils import write_json, ensure_dir


def write_insights_json(path: Path, insights: List[Insight]) -> None:
    """
    Write insights to JSON file.

    Args:
        path: Output path
        insights: List of Insight objects
    """
    data = []
    for insight in insights:
        item = {
            "cluster_id": insight.cluster_id,
            "summary": {
                "title": insight.summary.title,
                "description": insight.summary.description,
                "monetizable": insight.summary.monetizable,
                "justification": insight.summary.justification,
                "mvp": insight.summary.mvp,
                "pain_score_llm": insight.summary.pain_score_llm,
                "size": insight.summary.size
            },
            "pain_score_final": insight.pain_score_final,
            "examples": insight.examples
        }
        data.append(item)

    write_json(path, data)


def write_enriched_insights_csv(path: Path, insights: List[EnrichedInsight]) -> None:
    """
    Write enriched insights to CSV file with all enhanced fields.

    Args:
        path: Output path
        insights: List of EnrichedInsight objects
    """
    ensure_dir(path.parent)

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header with enriched fields
        writer.writerow([
            "rank",
            "cluster_id",
            "size",
            "priority_score",
            "title",
            "problem",
            "persona",
            "jtbd",
            "context",
            "monetizable",
            "mvp",
            "alternatives",
            "willingness_to_pay_signal",
            "pain_score_llm",
            "pain_score_final",
            "heuristic_score",
            "traction_score",
            "novelty_score",
            "trend_score",
            "keywords_matched",
            "source_mix",
            "example_urls"
        ])

        # Data
        for insight in insights:
            example_urls = " | ".join(str(ex.get("url") or "") for ex in insight.examples[:3])
            alternatives_str = ", ".join(insight.summary.alternatives) if insight.summary.alternatives else ""
            source_mix_str = ", ".join(insight.source_mix) if insight.source_mix else ""
            keywords_str = ", ".join(insight.keywords_matched) if insight.keywords_matched else ""

            writer.writerow([
                insight.rank,
                insight.cluster_id,
                insight.summary.size,
                insight.priority_score,
                insight.summary.title,
                insight.summary.problem,
                insight.summary.persona,
                insight.summary.jtbd,
                insight.summary.context,
                insight.summary.monetizable,
                insight.summary.mvp,
                alternatives_str,
                insight.summary.willingness_to_pay_signal,
                insight.summary.pain_score_llm or "",
                insight.pain_score_final or "",
                insight.heuristic_score or "",
                insight.traction_score or "",
                insight.novelty_score or "",
                insight.trend_score or "",
                keywords_str,
                source_mix_str,
                example_urls
            ])

    logger.info(f"Written enriched CSV to {path}")


def write_enriched_cluster_results(
    path: Path,
    insights: List[EnrichedInsight],
    stats: dict
) -> None:
    """
    Write complete enriched cluster results to JSON.

    Args:
        path: Output path
        insights: List of enriched insights
        stats: Processing statistics
    """
    data = {
        "statistics": stats,
        "insights": []
    }

    for insight in insights:
        item = {
            "cluster_id": insight.cluster_id,
            "rank": insight.rank,
            "priority_score": insight.priority_score,
            "summary": {
                "title": insight.summary.title,
                "problem": insight.summary.problem,
                "persona": insight.summary.persona,
                "jtbd": insight.summary.jtbd,
                "context": insight.summary.context,
                "monetizable": insight.summary.monetizable,
                "mvp": insight.summary.mvp,
                "alternatives": insight.summary.alternatives,
                "willingness_to_pay_signal": insight.summary.willingness_to_pay_signal,
                "pain_score_llm": insight.summary.pain_score_llm,
                "size": insight.summary.size
            },
            "pain_score_final": insight.pain_score_final,
            "heuristic_score": insight.heuristic_score,
            "traction_score": insight.traction_score,
            "novelty_score": insight.novelty_score,
            "trend_score": insight.trend_score,
            "keywords_matched": insight.keywords_matched,
            "source_mix": insight.source_mix,
            "examples": insight.examples
        }
        data["insights"].append(item)

    write_json(path, data)
    logger.info(f"Written enriched results to {path}")


def write_insights_csv(path: Path, insights: List[Insight]) -> None:
    """
    Write insights to CSV file.

    Args:
        path: Output path
        insights: List of Insight objects
    """
    ensure_dir(path.parent)

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            "cluster_id",
            "size",
            "title",
            "description",
            "monetizable",
            "justification",
            "mvp",
            "pain_score_llm",
            "pain_score_final",
            "example_urls",
            "source"
        ])

        # Data
        for insight in insights:
            example_urls = " | ".join(str(ex.get("url") or "") for ex in insight.examples[:3])

            writer.writerow([
                insight.cluster_id,
                insight.summary.size,
                insight.summary.title,
                insight.summary.description,
                insight.summary.monetizable,
                insight.summary.justification,
                insight.summary.mvp,
                insight.summary.pain_score_llm or "",
                insight.pain_score_final or "",
                example_urls,
                "reddit"
            ])

    logger.info(f"Written CSV to {path}")


def write_cluster_results(
    path: Path,
    insights: List[Insight],
    stats: dict
) -> None:
    """
    Write complete cluster results to JSON.

    Args:
        path: Output path
        insights: List of insights
        stats: Processing statistics
    """
    data = {
        "statistics": stats,
        "insights": []
    }

    for insight in insights:
        item = {
            "cluster_id": insight.cluster_id,
            "summary": {
                "title": insight.summary.title,
                "description": insight.summary.description,
                "monetizable": insight.summary.monetizable,
                "justification": insight.summary.justification,
                "mvp": insight.summary.mvp,
                "pain_score_llm": insight.summary.pain_score_llm,
                "size": insight.summary.size
            },
            "pain_score_final": insight.pain_score_final,
            "examples": insight.examples
        }
        data["insights"].append(item)

    write_json(path, data)
