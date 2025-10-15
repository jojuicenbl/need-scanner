"""Export functions for results (JSON and CSV)."""

import csv
from pathlib import Path
from typing import List
from loguru import logger

from ..schemas import Insight, ClusterSummary
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
            example_urls = " | ".join(ex.get("url", "") for ex in insight.examples[:3])

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
