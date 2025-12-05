"""SQLite database management for Need Scanner runs and insights."""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from loguru import logger

from .schemas import EnrichedInsight


# Default database path
DEFAULT_DB_PATH = Path("data/needscanner.db")


def get_db_path(custom_path: Optional[Path] = None) -> Path:
    """Get database path from config or use default."""
    if custom_path:
        return custom_path

    # Try to get from environment or config
    import os
    env_path = os.getenv("NEEDSCANNER_DB_PATH")
    if env_path:
        return Path(env_path)

    return DEFAULT_DB_PATH


def init_database(db_path: Optional[Path] = None) -> None:
    """
    Initialize database with required tables.

    Creates tables if they don't exist:
    - runs: metadata about each scan run
    - insights: individual insights from each run

    Args:
        db_path: Path to SQLite database file (optional)
    """
    db_path = get_db_path(db_path)

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create runs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            config_name TEXT,
            mode TEXT,
            nb_insights INTEGER,
            nb_clusters INTEGER,
            total_cost_usd REAL,
            embed_cost_usd REAL,
            summary_cost_usd REAL,
            csv_path TEXT,
            json_path TEXT,
            notes TEXT,
            -- Step 5-bis: Run stats for instrumentation
            run_stats TEXT
        )
    """)

    # Create insights table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insights (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            rank INTEGER,
            mmr_rank INTEGER,
            cluster_id INTEGER,
            size INTEGER,
            sector TEXT,
            title TEXT NOT NULL,
            problem TEXT,
            persona TEXT,
            jtbd TEXT,
            context TEXT,
            mvp TEXT,
            alternatives TEXT,
            willingness_to_pay_signal TEXT,
            monetizable INTEGER,
            pain_score_llm REAL,
            pain_score_final REAL,
            heuristic_score REAL,
            traction_score REAL,
            novelty_score REAL,
            trend_score REAL,
            founder_fit_score REAL,
            priority_score REAL,
            priority_score_adjusted REAL,
            keywords_matched TEXT,
            source_mix TEXT,
            example_urls TEXT,
            created_at TIMESTAMP NOT NULL,
            -- Step 5.1 / 5-bis: Inter-day deduplication
            max_similarity_with_history REAL,
            duplicate_of_insight_id TEXT,
            is_historical_duplicate INTEGER DEFAULT 0,
            is_recurring_theme INTEGER DEFAULT 0,
            was_readded_by_fallback INTEGER DEFAULT 0,
            -- Step 5.2: SaaS-ability / Productizability
            solution_type TEXT,
            recurring_revenue_potential REAL,
            saas_viable INTEGER,
            -- Step 5.3: Product Ideation
            product_angle_title TEXT,
            product_angle_summary TEXT,
            product_angle_type TEXT,
            product_pricing_hint TEXT,
            product_complexity INTEGER,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        )
    """)

    # Create insight_explorations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insight_explorations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            insight_id TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            model_used TEXT,
            exploration_text TEXT NOT NULL,
            monetization_hypotheses TEXT,
            product_variants TEXT,
            validation_steps TEXT,
            FOREIGN KEY (insight_id) REFERENCES insights(id)
        )
    """)

    # Create indexes for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_insights_run_id
        ON insights(run_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_insights_rank
        ON insights(rank)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_insights_priority
        ON insights(priority_score DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_insights_sector
        ON insights(sector)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_runs_created
        ON runs(created_at DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_explorations_insight
        ON insight_explorations(insight_id)
    """)

    conn.commit()
    conn.close()

    # Run migrations for existing databases
    _migrate_database(db_path)

    logger.info(f"Database initialized at {db_path}")


def _migrate_database(db_path: Path) -> None:
    """
    Apply database migrations for new columns.

    This function adds new columns to existing tables if they don't exist.
    Safe to run multiple times.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get current columns in insights table
    cursor.execute("PRAGMA table_info(insights)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # New columns to add (Step 5 improvements)
    new_columns = [
        # Step 5.1 / 5-bis: Inter-day deduplication
        ("max_similarity_with_history", "REAL"),
        ("duplicate_of_insight_id", "TEXT"),
        ("is_historical_duplicate", "INTEGER DEFAULT 0"),
        ("is_recurring_theme", "INTEGER DEFAULT 0"),
        ("was_readded_by_fallback", "INTEGER DEFAULT 0"),
        # Step 5.2: SaaS-ability / Productizability
        ("solution_type", "TEXT"),
        ("recurring_revenue_potential", "REAL"),
        ("saas_viable", "INTEGER"),
        # Step 5.3: Product Ideation
        ("product_angle_title", "TEXT"),
        ("product_angle_summary", "TEXT"),
        ("product_angle_type", "TEXT"),
        ("product_pricing_hint", "TEXT"),
        ("product_complexity", "INTEGER"),
    ]

    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE insights ADD COLUMN {column_name} {column_type}")
                logger.info(f"Migration: Added column '{column_name}' to insights table")
            except sqlite3.OperationalError as e:
                # Column might already exist in some edge cases
                logger.debug(f"Could not add column {column_name}: {e}")

    # Migrate runs table for Step 5-bis stats
    cursor.execute("PRAGMA table_info(runs)")
    runs_columns = {row[1] for row in cursor.fetchall()}

    if "run_stats" not in runs_columns:
        try:
            cursor.execute("ALTER TABLE runs ADD COLUMN run_stats TEXT")
            logger.info("Migration: Added column 'run_stats' to runs table")
        except sqlite3.OperationalError as e:
            logger.debug(f"Could not add column run_stats: {e}")

    conn.commit()
    conn.close()


def generate_run_id() -> str:
    """Generate unique run ID based on timestamp."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_run(
    run_id: str,
    config_name: Optional[str],
    mode: str,
    nb_insights: int,
    nb_clusters: int,
    total_cost_usd: float = 0.0,
    embed_cost_usd: float = 0.0,
    summary_cost_usd: float = 0.0,
    csv_path: Optional[str] = None,
    json_path: Optional[str] = None,
    notes: Optional[str] = None,
    run_stats: Optional[Dict] = None,
    db_path: Optional[Path] = None
) -> None:
    """
    Save run metadata to database.

    Args:
        run_id: Unique run identifier
        config_name: Configuration name used
        mode: Run mode (light/deep)
        nb_insights: Number of insights generated
        nb_clusters: Number of clusters created
        total_cost_usd: Total API cost
        embed_cost_usd: Embedding cost
        summary_cost_usd: Summarization cost
        csv_path: Path to generated CSV
        json_path: Path to generated JSON
        notes: Optional notes
        run_stats: Step 5-bis instrumentation stats (optional)
        db_path: Database path (optional)
    """
    db_path = get_db_path(db_path)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Serialize run_stats to JSON if provided
    run_stats_json = json.dumps(run_stats) if run_stats else None

    cursor.execute("""
        INSERT INTO runs (
            id, created_at, config_name, mode, nb_insights, nb_clusters,
            total_cost_usd, embed_cost_usd, summary_cost_usd,
            csv_path, json_path, notes, run_stats
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id,
        datetime.now(),
        config_name,
        mode,
        nb_insights,
        nb_clusters,
        total_cost_usd,
        embed_cost_usd,
        summary_cost_usd,
        csv_path,
        json_path,
        notes,
        run_stats_json
    ))

    conn.commit()
    conn.close()

    logger.info(f"Saved run {run_id} to database")


def save_insights(
    run_id: str,
    insights: List[EnrichedInsight],
    db_path: Optional[Path] = None
) -> None:
    """
    Save insights to database.

    Args:
        run_id: Run identifier
        insights: List of EnrichedInsight objects
        db_path: Database path (optional)
    """
    db_path = get_db_path(db_path)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    created_at = datetime.now()

    for insight in insights:
        # Generate unique insight ID
        insight_id = f"{run_id}_cluster_{insight.cluster_id}"

        # Prepare data
        alternatives_str = json.dumps(insight.summary.alternatives) if insight.summary.alternatives else None
        keywords_str = json.dumps(insight.keywords_matched) if insight.keywords_matched else None
        source_mix_str = json.dumps(insight.source_mix) if insight.source_mix else None

        # Get example URLs
        example_urls = None
        if insight.examples:
            urls = [ex.get('url', '') for ex in insight.examples[:3] if ex.get('url')]
            example_urls = json.dumps(urls) if urls else None

        cursor.execute("""
            INSERT OR REPLACE INTO insights (
                id, run_id, rank, mmr_rank, cluster_id, size, sector,
                title, problem, persona, jtbd, context, mvp,
                alternatives, willingness_to_pay_signal, monetizable,
                pain_score_llm, pain_score_final, heuristic_score,
                traction_score, novelty_score, trend_score, founder_fit_score,
                priority_score, priority_score_adjusted,
                keywords_matched, source_mix, example_urls, created_at,
                max_similarity_with_history, duplicate_of_insight_id, is_historical_duplicate,
                is_recurring_theme, was_readded_by_fallback,
                solution_type, recurring_revenue_potential, saas_viable,
                product_angle_title, product_angle_summary, product_angle_type,
                product_pricing_hint, product_complexity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            insight_id,
            run_id,
            insight.rank,
            insight.mmr_rank,
            insight.cluster_id,
            insight.summary.size,
            insight.summary.sector,
            insight.summary.title,
            insight.summary.problem,
            insight.summary.persona,
            insight.summary.jtbd,
            insight.summary.context,
            insight.summary.mvp,
            alternatives_str,
            insight.summary.willingness_to_pay_signal,
            1 if insight.summary.monetizable else 0,
            insight.summary.pain_score_llm,
            insight.pain_score_final,
            insight.heuristic_score,
            insight.traction_score,
            insight.novelty_score,
            insight.trend_score,
            insight.founder_fit_score,
            insight.priority_score,
            insight.priority_score_adjusted,
            keywords_str,
            source_mix_str,
            example_urls,
            created_at,
            # Step 5.1 / 5-bis: Inter-day deduplication
            insight.max_similarity_with_history,
            insight.duplicate_of_insight_id,
            1 if insight.is_historical_duplicate else 0,
            1 if insight.is_recurring_theme else 0,
            1 if insight.was_readded_by_fallback else 0,
            # Step 5.2: SaaS-ability / Productizability
            insight.solution_type,
            insight.recurring_revenue_potential,
            1 if insight.saas_viable else (0 if insight.saas_viable is False else None),
            # Step 5.3: Product Ideation
            insight.product_angle_title,
            insight.product_angle_summary,
            insight.product_angle_type,
            insight.product_pricing_hint,
            insight.product_complexity
        ))

    conn.commit()
    conn.close()

    logger.info(f"Saved {len(insights)} insights to database for run {run_id}")


def get_latest_run(db_path: Optional[Path] = None) -> Optional[Dict]:
    """Get most recent run metadata."""
    db_path = get_db_path(db_path)

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM runs
        ORDER BY created_at DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_run_insights(
    run_id: str,
    limit: Optional[int] = None,
    db_path: Optional[Path] = None
) -> List[Dict]:
    """
    Get insights for a specific run.

    Args:
        run_id: Run identifier
        limit: Optional limit on number of insights
        db_path: Database path (optional)

    Returns:
        List of insight dictionaries
    """
    db_path = get_db_path(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT * FROM insights
        WHERE run_id = ?
        ORDER BY rank ASC
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query, (run_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def list_runs(
    limit: int = 10,
    db_path: Optional[Path] = None
) -> List[Dict]:
    """
    List recent runs.

    Args:
        limit: Maximum number of runs to return
        db_path: Database path (optional)

    Returns:
        List of run dictionaries
    """
    db_path = get_db_path(db_path)

    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM runs
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def query_insights(
    sector: Optional[str] = None,
    min_priority: Optional[float] = None,
    min_founder_fit: Optional[float] = None,
    monetizable_only: bool = False,
    limit: int = 50,
    db_path: Optional[Path] = None
) -> List[Dict]:
    """
    Query insights with filters.

    Args:
        sector: Filter by sector
        min_priority: Minimum priority score
        min_founder_fit: Minimum founder fit score
        monetizable_only: Only monetizable insights
        limit: Maximum results
        db_path: Database path (optional)

    Returns:
        List of matching insights
    """
    db_path = get_db_path(db_path)

    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM insights WHERE 1=1"
    params = []

    if sector:
        query += " AND sector = ?"
        params.append(sector)

    if min_priority is not None:
        query += " AND priority_score >= ?"
        params.append(min_priority)

    if min_founder_fit is not None:
        query += " AND founder_fit_score >= ?"
        params.append(min_founder_fit)

    if monetizable_only:
        query += " AND monetizable = 1"

    query += " ORDER BY priority_score DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_insight_by_id(
    insight_id: str,
    db_path: Optional[Path] = None
) -> Optional[Dict]:
    """
    Get a single insight by its ID.

    Args:
        insight_id: Insight identifier
        db_path: Database path (optional)

    Returns:
        Insight dictionary or None if not found
    """
    db_path = get_db_path(db_path)

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM insights
        WHERE id = ?
    """, (insight_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def save_exploration(
    insight_id: str,
    model_used: str,
    exploration_text: str,
    monetization_hypotheses: Optional[str] = None,
    product_variants: Optional[str] = None,
    validation_steps: Optional[str] = None,
    db_path: Optional[Path] = None
) -> int:
    """
    Save an insight exploration to the database.

    Args:
        insight_id: Insight identifier
        model_used: LLM model used for exploration
        exploration_text: Full exploration text
        monetization_hypotheses: JSON string of monetization ideas
        product_variants: JSON string of product variants
        validation_steps: JSON string of validation steps
        db_path: Database path (optional)

    Returns:
        exploration_id: ID of the created exploration
    """
    db_path = get_db_path(db_path)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO insight_explorations (
            insight_id, created_at, model_used, exploration_text,
            monetization_hypotheses, product_variants, validation_steps
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        insight_id,
        datetime.now(),
        model_used,
        exploration_text,
        monetization_hypotheses,
        product_variants,
        validation_steps
    ))

    exploration_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Saved exploration {exploration_id} for insight {insight_id}")
    return exploration_id


def get_explorations_for_insight(
    insight_id: str,
    db_path: Optional[Path] = None
) -> List[Dict]:
    """
    Get all explorations for a specific insight.

    Args:
        insight_id: Insight identifier
        db_path: Database path (optional)

    Returns:
        List of exploration dictionaries
    """
    db_path = get_db_path(db_path)

    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM insight_explorations
        WHERE insight_id = ?
        ORDER BY created_at DESC
    """, (insight_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]
