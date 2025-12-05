#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL.

This script copies all data from an existing SQLite database to the new
PostgreSQL database configured via DATABASE_URL.

Usage:
    # Set DATABASE_URL in your environment
    export DATABASE_URL="postgresql+psycopg2://user:password@host:5432/needscanner"

    # Run migration
    python scripts/migrate_sqlite_to_postgres.py

    # Or specify a custom SQLite path
    python scripts/migrate_sqlite_to_postgres.py --sqlite-path data/needscanner.db

Requirements:
    - DATABASE_URL environment variable must be set
    - PostgreSQL database must exist and have schema (run Alembic migrations first)
    - SQLite database must exist

Note:
    This script is idempotent - it will skip rows that already exist in PostgreSQL.
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path

# Add the src directory to the path so we can import need_scanner modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<level>{level}</level> | {message}")


def get_sqlite_connection(sqlite_path: Path) -> sqlite3.Connection:
    """Get SQLite database connection."""
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found at: {sqlite_path}")

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    return conn


def migrate_runs(sqlite_conn: sqlite3.Connection, pg_session) -> int:
    """
    Migrate runs table from SQLite to PostgreSQL.

    Returns:
        Number of rows migrated
    """
    from need_scanner.database import Run

    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT * FROM runs")
    rows = cursor.fetchall()

    migrated = 0
    skipped = 0

    for row in rows:
        run_id = row["id"]

        # Check if already exists
        existing = pg_session.query(Run).filter(Run.id == run_id).first()
        if existing:
            skipped += 1
            continue

        # Parse created_at (might be string or datetime)
        created_at = row["created_at"]
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                created_at = datetime.now()

        run = Run(
            id=run_id,
            created_at=created_at,
            config_name=row["config_name"],
            mode=row["mode"],
            nb_insights=row["nb_insights"],
            nb_clusters=row["nb_clusters"],
            total_cost_usd=row["total_cost_usd"],
            embed_cost_usd=row["embed_cost_usd"],
            summary_cost_usd=row["summary_cost_usd"],
            csv_path=row["csv_path"],
            json_path=row["json_path"],
            notes=row["notes"],
            run_stats=row["run_stats"] if "run_stats" in row.keys() else None,
        )
        pg_session.add(run)
        migrated += 1

    pg_session.commit()
    logger.info(f"Runs: migrated {migrated}, skipped {skipped} (already exist)")
    return migrated


def migrate_insights(sqlite_conn: sqlite3.Connection, pg_session) -> int:
    """
    Migrate insights table from SQLite to PostgreSQL.

    Returns:
        Number of rows migrated
    """
    from need_scanner.database import Insight

    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT * FROM insights")
    rows = cursor.fetchall()

    migrated = 0
    skipped = 0
    errors = 0

    for row in rows:
        insight_id = row["id"]

        # Check if already exists
        existing = pg_session.query(Insight).filter(Insight.id == insight_id).first()
        if existing:
            skipped += 1
            continue

        try:
            # Parse created_at
            created_at = row["created_at"]
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    created_at = datetime.now()

            # Get column names from row
            columns = row.keys()

            insight = Insight(
                id=insight_id,
                run_id=row["run_id"],
                rank=row["rank"],
                mmr_rank=row["mmr_rank"] if "mmr_rank" in columns else None,
                cluster_id=row["cluster_id"],
                size=row["size"],
                sector=row["sector"],
                title=row["title"],
                problem=row["problem"],
                persona=row["persona"],
                jtbd=row["jtbd"],
                context=row["context"],
                mvp=row["mvp"],
                alternatives=row["alternatives"],
                willingness_to_pay_signal=row["willingness_to_pay_signal"],
                monetizable=row["monetizable"],
                pain_score_llm=row["pain_score_llm"],
                pain_score_final=row["pain_score_final"],
                heuristic_score=row["heuristic_score"],
                traction_score=row["traction_score"],
                novelty_score=row["novelty_score"],
                trend_score=row["trend_score"],
                founder_fit_score=row["founder_fit_score"],
                priority_score=row["priority_score"],
                priority_score_adjusted=row["priority_score_adjusted"] if "priority_score_adjusted" in columns else None,
                keywords_matched=row["keywords_matched"],
                source_mix=row["source_mix"],
                example_urls=row["example_urls"],
                created_at=created_at,
                # Step 5.1 / 5-bis columns (may not exist in older databases)
                max_similarity_with_history=row["max_similarity_with_history"] if "max_similarity_with_history" in columns else None,
                duplicate_of_insight_id=row["duplicate_of_insight_id"] if "duplicate_of_insight_id" in columns else None,
                is_historical_duplicate=row["is_historical_duplicate"] if "is_historical_duplicate" in columns else 0,
                is_recurring_theme=row["is_recurring_theme"] if "is_recurring_theme" in columns else 0,
                was_readded_by_fallback=row["was_readded_by_fallback"] if "was_readded_by_fallback" in columns else 0,
                # Step 5.2 columns
                solution_type=row["solution_type"] if "solution_type" in columns else None,
                recurring_revenue_potential=row["recurring_revenue_potential"] if "recurring_revenue_potential" in columns else None,
                saas_viable=row["saas_viable"] if "saas_viable" in columns else None,
                # Step 5.3 columns
                product_angle_title=row["product_angle_title"] if "product_angle_title" in columns else None,
                product_angle_summary=row["product_angle_summary"] if "product_angle_summary" in columns else None,
                product_angle_type=row["product_angle_type"] if "product_angle_type" in columns else None,
                product_pricing_hint=row["product_pricing_hint"] if "product_pricing_hint" in columns else None,
                product_complexity=row["product_complexity"] if "product_complexity" in columns else None,
            )
            pg_session.add(insight)
            migrated += 1

        except Exception as e:
            logger.warning(f"Failed to migrate insight {insight_id}: {e}")
            errors += 1
            continue

    pg_session.commit()
    logger.info(f"Insights: migrated {migrated}, skipped {skipped}, errors {errors}")
    return migrated


def migrate_explorations(sqlite_conn: sqlite3.Connection, pg_session) -> int:
    """
    Migrate insight_explorations table from SQLite to PostgreSQL.

    Returns:
        Number of rows migrated
    """
    from need_scanner.database import InsightExploration

    cursor = sqlite_conn.cursor()

    # Check if table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='insight_explorations'"
    )
    if not cursor.fetchone():
        logger.info("Explorations: table does not exist in SQLite, skipping")
        return 0

    cursor.execute("SELECT * FROM insight_explorations")
    rows = cursor.fetchall()

    migrated = 0
    skipped = 0
    errors = 0

    for row in rows:
        exploration_id = row["id"]

        # Check if already exists (by insight_id + created_at to handle auto-increment IDs)
        try:
            created_at = row["created_at"]
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    created_at = datetime.now()

            existing = (
                pg_session.query(InsightExploration)
                .filter(
                    InsightExploration.insight_id == row["insight_id"],
                    InsightExploration.created_at == created_at,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            exploration = InsightExploration(
                # Note: Don't set id - let PostgreSQL auto-generate
                insight_id=row["insight_id"],
                created_at=created_at,
                model_used=row["model_used"],
                exploration_text=row["exploration_text"],
                monetization_hypotheses=row["monetization_hypotheses"],
                product_variants=row["product_variants"],
                validation_steps=row["validation_steps"],
            )
            pg_session.add(exploration)
            migrated += 1

        except Exception as e:
            logger.warning(f"Failed to migrate exploration {exploration_id}: {e}")
            errors += 1
            continue

    pg_session.commit()
    logger.info(f"Explorations: migrated {migrated}, skipped {skipped}, errors {errors}")
    return migrated


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Need Scanner data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path("data/needscanner.db"),
        help="Path to SQLite database (default: data/needscanner.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually migrate, just show what would be done",
    )

    args = parser.parse_args()

    # Check DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error(
            "DATABASE_URL environment variable is not set.\n"
            "Please set it to your PostgreSQL connection string.\n"
            "Example: export DATABASE_URL='postgresql+psycopg2://user:password@localhost:5432/needscanner'"
        )
        sys.exit(1)

    # Check SQLite file exists
    if not args.sqlite_path.exists():
        logger.error(f"SQLite database not found at: {args.sqlite_path}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Need Scanner - SQLite to PostgreSQL Migration")
    logger.info("=" * 60)
    logger.info(f"SQLite source: {args.sqlite_path}")
    logger.info(f"PostgreSQL target: {database_url[:50]}...")

    if args.dry_run:
        logger.info("DRY RUN MODE - No data will be migrated")

    # Connect to SQLite
    logger.info("\nConnecting to SQLite...")
    sqlite_conn = get_sqlite_connection(args.sqlite_path)

    # Count source data
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM runs")
    runs_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM insights")
    insights_count = cursor.fetchone()[0]

    # Check for explorations table
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='insight_explorations'"
    )
    if cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM insight_explorations")
        explorations_count = cursor.fetchone()[0]
    else:
        explorations_count = 0

    logger.info(f"\nSource data:")
    logger.info(f"  Runs: {runs_count}")
    logger.info(f"  Insights: {insights_count}")
    logger.info(f"  Explorations: {explorations_count}")

    if args.dry_run:
        logger.info("\nDry run complete. No data migrated.")
        sqlite_conn.close()
        return

    # Connect to PostgreSQL
    logger.info("\nConnecting to PostgreSQL...")
    from need_scanner.database import get_db_session

    with get_db_session() as pg_session:
        # Migrate data
        logger.info("\nMigrating data...")

        total_runs = migrate_runs(sqlite_conn, pg_session)
        total_insights = migrate_insights(sqlite_conn, pg_session)
        total_explorations = migrate_explorations(sqlite_conn, pg_session)

        logger.info("\n" + "=" * 60)
        logger.info("Migration Complete!")
        logger.info("=" * 60)
        logger.info(f"  Runs migrated: {total_runs}")
        logger.info(f"  Insights migrated: {total_insights}")
        logger.info(f"  Explorations migrated: {total_explorations}")

    sqlite_conn.close()
    logger.info("\nDone!")


if __name__ == "__main__":
    main()
