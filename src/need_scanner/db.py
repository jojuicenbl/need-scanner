"""Database operations for Need Scanner - PostgreSQL with SQLAlchemy.

This module provides the public API for database operations.
It uses SQLAlchemy ORM with PostgreSQL (via Supabase or local).

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (required)
        Example: postgresql+psycopg2://user:password@localhost:5432/needscanner

Migration from SQLite:
    This module replaces the old SQLite-based implementation.
    See docs/DB_MIGRATION.md for migration instructions.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from loguru import logger
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .database import (
    get_session,
    get_db_session,
    init_db,
    check_db_connection,
    User,
    Run,
    Insight,
    InsightExploration,
)
from .database.config import DatabaseConfigError
from .database.models import (
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    VALID_JOB_STATUSES,
)
from .schemas import EnrichedInsight


def init_database(db_path: Optional[Path] = None) -> None:
    """
    Initialize database connection and verify schema.

    Note: db_path parameter is kept for backwards compatibility but is ignored.
    The database URL is read from DATABASE_URL environment variable.

    Args:
        db_path: Ignored (kept for backwards compatibility)

    Raises:
        DatabaseConfigError: If DATABASE_URL is not set
    """
    if db_path is not None:
        logger.warning(
            "db_path parameter is deprecated and ignored. "
            "Use DATABASE_URL environment variable instead."
        )

    try:
        # Verify connection works
        check_db_connection()
        logger.info("Database connection verified (PostgreSQL)")
    except DatabaseConfigError as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def get_db_path(custom_path: Optional[Path] = None) -> str:
    """
    Get database connection info (for logging purposes).

    Note: This function is kept for backwards compatibility.
    Returns a descriptive string instead of a path.

    Args:
        custom_path: Ignored (kept for backwards compatibility)

    Returns:
        String describing the database connection
    """
    if custom_path is not None:
        logger.warning(
            "custom_path parameter is deprecated and ignored. "
            "Use DATABASE_URL environment variable instead."
        )

    return "PostgreSQL (via DATABASE_URL)"


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
        db_path: Ignored (kept for backwards compatibility)
    """
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    # Serialize run_stats to JSON if provided
    run_stats_json = json.dumps(run_stats) if run_stats else None

    with get_db_session() as db:
        run = Run(
            id=run_id,
            created_at=datetime.now(),
            config_name=config_name,
            mode=mode,
            nb_insights=nb_insights,
            nb_clusters=nb_clusters,
            total_cost_usd=total_cost_usd,
            embed_cost_usd=embed_cost_usd,
            summary_cost_usd=summary_cost_usd,
            csv_path=csv_path,
            json_path=json_path,
            notes=notes,
            run_stats=run_stats_json,
        )
        db.add(run)
        # Commit happens automatically in context manager

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
        db_path: Ignored (kept for backwards compatibility)
    """
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    created_at = datetime.now()

    with get_db_session() as db:
        for insight in insights:
            # Generate unique insight ID
            insight_id = f"{run_id}_cluster_{insight.cluster_id}"

            # Prepare JSON data
            alternatives_str = json.dumps(insight.summary.alternatives) if insight.summary.alternatives else None
            keywords_str = json.dumps(insight.keywords_matched) if insight.keywords_matched else None
            source_mix_str = json.dumps(insight.source_mix) if insight.source_mix else None

            # Get example URLs
            example_urls = None
            if insight.examples:
                urls = [ex.get('url', '') for ex in insight.examples[:3] if ex.get('url')]
                example_urls = json.dumps(urls) if urls else None

            # Create insight record
            insight_record = Insight(
                id=insight_id,
                run_id=run_id,
                rank=insight.rank,
                mmr_rank=insight.mmr_rank,
                cluster_id=insight.cluster_id,
                size=insight.summary.size,
                sector=insight.summary.sector,
                title=insight.summary.title,
                problem=insight.summary.problem,
                persona=insight.summary.persona,
                jtbd=insight.summary.jtbd,
                context=insight.summary.context,
                mvp=insight.summary.mvp,
                alternatives=alternatives_str,
                willingness_to_pay_signal=insight.summary.willingness_to_pay_signal,
                monetizable=1 if insight.summary.monetizable else 0,
                pain_score_llm=insight.summary.pain_score_llm,
                pain_score_final=insight.pain_score_final,
                heuristic_score=insight.heuristic_score,
                traction_score=insight.traction_score,
                novelty_score=insight.novelty_score,
                trend_score=insight.trend_score,
                founder_fit_score=insight.founder_fit_score,
                priority_score=insight.priority_score,
                priority_score_adjusted=insight.priority_score_adjusted,
                keywords_matched=keywords_str,
                source_mix=source_mix_str,
                example_urls=example_urls,
                created_at=created_at,
                # Step 5.1 / 5-bis: Inter-day deduplication
                max_similarity_with_history=insight.max_similarity_with_history,
                duplicate_of_insight_id=insight.duplicate_of_insight_id,
                is_historical_duplicate=1 if insight.is_historical_duplicate else 0,
                is_recurring_theme=1 if insight.is_recurring_theme else 0,
                was_readded_by_fallback=1 if insight.was_readded_by_fallback else 0,
                # Step 5.2: SaaS-ability / Productizability
                solution_type=insight.solution_type,
                recurring_revenue_potential=insight.recurring_revenue_potential,
                saas_viable=1 if insight.saas_viable else (0 if insight.saas_viable is False else None),
                # Step 5.3: Product Ideation
                product_angle_title=insight.product_angle_title,
                product_angle_summary=insight.product_angle_summary,
                product_angle_type=insight.product_angle_type,
                product_pricing_hint=insight.product_pricing_hint,
                product_complexity=insight.product_complexity,
            )

            # Use merge to handle INSERT OR REPLACE behavior
            db.merge(insight_record)

    logger.info(f"Saved {len(insights)} insights to database for run {run_id}")


def get_latest_run(db_path: Optional[Path] = None) -> Optional[Dict]:
    """Get most recent run metadata."""
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    with get_db_session() as db:
        run = db.query(Run).order_by(desc(Run.created_at)).first()

        if run:
            return _run_to_dict(run)
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
        db_path: Ignored (kept for backwards compatibility)

    Returns:
        List of insight dictionaries
    """
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    with get_db_session() as db:
        query = db.query(Insight).filter(Insight.run_id == run_id).order_by(Insight.rank)

        if limit:
            query = query.limit(limit)

        insights = query.all()
        return [_insight_to_dict(i) for i in insights]


def list_runs(
    limit: int = 10,
    db_path: Optional[Path] = None
) -> List[Dict]:
    """
    List recent runs.

    Args:
        limit: Maximum number of runs to return
        db_path: Ignored (kept for backwards compatibility)

    Returns:
        List of run dictionaries
    """
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    with get_db_session() as db:
        runs = db.query(Run).order_by(desc(Run.created_at)).limit(limit).all()
        return [_run_to_dict(r) for r in runs]


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
        db_path: Ignored (kept for backwards compatibility)

    Returns:
        List of matching insights
    """
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    with get_db_session() as db:
        query = db.query(Insight)

        if sector:
            query = query.filter(Insight.sector == sector)

        if min_priority is not None:
            query = query.filter(Insight.priority_score >= min_priority)

        if min_founder_fit is not None:
            query = query.filter(Insight.founder_fit_score >= min_founder_fit)

        if monetizable_only:
            query = query.filter(Insight.monetizable == 1)

        query = query.order_by(desc(Insight.priority_score)).limit(limit)

        insights = query.all()
        return [_insight_to_dict(i) for i in insights]


def get_insight_by_id(
    insight_id: str,
    db_path: Optional[Path] = None
) -> Optional[Dict]:
    """
    Get a single insight by its ID.

    Args:
        insight_id: Insight identifier
        db_path: Ignored (kept for backwards compatibility)

    Returns:
        Insight dictionary or None if not found
    """
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    with get_db_session() as db:
        insight = db.query(Insight).filter(Insight.id == insight_id).first()

        if insight:
            return _insight_to_dict(insight)
        return None


def save_exploration(
    insight_id: str,
    model_used: str,
    exploration_text: str,
    monetization_hypotheses: Optional[str] = None,
    product_variants: Optional[str] = None,
    validation_steps: Optional[str] = None,
    user_id: Optional[str] = None,
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
        user_id: ID of user creating this exploration (Step 3: freemium)
        db_path: Ignored (kept for backwards compatibility)

    Returns:
        exploration_id: ID of the created exploration
    """
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    with get_db_session() as db:
        exploration = InsightExploration(
            insight_id=insight_id,
            created_at=datetime.now(),
            model_used=model_used,
            exploration_text=exploration_text,
            monetization_hypotheses=monetization_hypotheses,
            product_variants=product_variants,
            validation_steps=validation_steps,
            user_id=user_id,
        )
        db.add(exploration)
        db.flush()  # Get the auto-generated ID
        exploration_id = exploration.id

    logger.info(f"Saved exploration {exploration_id} for insight {insight_id} by user {user_id}")
    return exploration_id


def get_explorations_for_insight(
    insight_id: str,
    db_path: Optional[Path] = None
) -> List[Dict]:
    """
    Get all explorations for a specific insight.

    Args:
        insight_id: Insight identifier
        db_path: Ignored (kept for backwards compatibility)

    Returns:
        List of exploration dictionaries
    """
    if db_path is not None:
        logger.warning("db_path parameter is deprecated and ignored.")

    with get_db_session() as db:
        explorations = (
            db.query(InsightExploration)
            .filter(InsightExploration.insight_id == insight_id)
            .order_by(desc(InsightExploration.created_at))
            .all()
        )
        return [_exploration_to_dict(e) for e in explorations]


# ============================================================================
# Job Queue Operations (Step 2)
# ============================================================================

def enqueue_run(
    run_id: str,
    mode: str = "deep",
    run_mode: str = "discover",
    max_insights: Optional[int] = None,
    input_pattern: str = "data/raw/posts_*.json",
    config_name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict:
    """
    Create a new run in 'queued' status.

    This is the entry point for the job queue. The HTTP API calls this
    to enqueue a scan job, which will be picked up by a worker process.

    Args:
        run_id: Unique run identifier
        mode: Scan mode ('light' or 'deep')
        run_mode: Run mode ('discover' or 'track')
        max_insights: Maximum number of insights to generate
        input_pattern: Glob pattern for input files
        config_name: Optional configuration name
        user_id: ID of user creating this run (Step 3: freemium)

    Returns:
        Dictionary with the created run details
    """
    with get_db_session() as db:
        run = Run(
            id=run_id,
            created_at=datetime.now(),
            status=JOB_STATUS_QUEUED,
            progress=0,
            mode=mode,
            run_mode=run_mode,
            max_insights=max_insights,
            input_pattern=input_pattern,
            config_name=config_name,
            user_id=user_id,
        )
        db.add(run)
        db.flush()  # Ensure the run is written

        result = _run_to_dict(run)

    logger.info(f"Enqueued run {run_id} for user {user_id} with status=queued")
    return result


def get_run_by_id(run_id: str) -> Optional[Dict]:
    """
    Get a run by its ID.

    Args:
        run_id: Run identifier

    Returns:
        Run dictionary or None if not found
    """
    with get_db_session() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run:
            return _run_to_dict(run)
        return None


def claim_next_job(worker_id: Optional[str] = None) -> Optional[Dict]:
    """
    Claim the next queued canonical job for processing.

    Uses SELECT ... FOR UPDATE SKIP LOCKED to safely claim a job
    in a concurrent environment. Multiple workers can call this
    safely without race conditions.

    Step 4: Only picks canonical runs (is_cached_result = false).
    Cached runs are never processed by workers - they reuse results
    from their source (canonical) run.

    Args:
        worker_id: Optional worker identifier for logging

    Returns:
        Run dictionary if a job was claimed, None if no jobs available
    """
    from sqlalchemy import text

    with get_db_session() as db:
        # Use raw SQL for the FOR UPDATE SKIP LOCKED clause
        # This is PostgreSQL-specific but that's what we're using
        # Step 4: Only pick canonical runs (is_cached_result = false)
        result = db.execute(
            text("""
                SELECT id FROM runs
                WHERE status = :status
                  AND is_cached_result = false
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """),
            {"status": JOB_STATUS_QUEUED}
        )
        row = result.fetchone()

        if not row:
            return None

        run_id = row[0]

        # Update the run to 'running' status
        run = db.query(Run).filter(Run.id == run_id).first()
        if run:
            run.status = JOB_STATUS_RUNNING
            run.started_at = datetime.now()
            run.progress = 0
            db.flush()

            worker_info = f" by worker {worker_id}" if worker_id else ""
            logger.info(f"Claimed canonical job {run_id}{worker_info}")

            return _run_to_dict(run)

        return None


def update_job_progress(run_id: str, progress: int) -> None:
    """
    Update the progress of a running job.

    Args:
        run_id: Run identifier
        progress: Progress percentage (0-100)
    """
    progress = max(0, min(100, progress))  # Clamp to 0-100

    with get_db_session() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run and run.status == JOB_STATUS_RUNNING:
            run.progress = progress
            logger.debug(f"Updated job {run_id} progress to {progress}%")


def complete_job(
    run_id: str,
    nb_insights: int,
    nb_clusters: int,
    total_cost_usd: float = 0.0,
    embed_cost_usd: float = 0.0,
    summary_cost_usd: float = 0.0,
    csv_path: Optional[str] = None,
    json_path: Optional[str] = None,
    notes: Optional[str] = None,
    run_stats: Optional[Dict] = None,
) -> None:
    """
    Mark a job as completed and store results.

    Args:
        run_id: Run identifier
        nb_insights: Number of insights generated
        nb_clusters: Number of clusters created
        total_cost_usd: Total API cost
        embed_cost_usd: Embedding cost
        summary_cost_usd: Summarization cost
        csv_path: Path to generated CSV
        json_path: Path to generated JSON
        notes: Optional notes
        run_stats: Instrumentation stats (optional)
    """
    run_stats_json = json.dumps(run_stats) if run_stats else None

    with get_db_session() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run:
            run.status = JOB_STATUS_COMPLETED
            run.completed_at = datetime.now()
            run.progress = 100
            run.nb_insights = nb_insights
            run.nb_clusters = nb_clusters
            run.total_cost_usd = total_cost_usd
            run.embed_cost_usd = embed_cost_usd
            run.summary_cost_usd = summary_cost_usd
            run.csv_path = csv_path
            run.json_path = json_path
            run.notes = notes
            run.run_stats = run_stats_json

            logger.info(f"Completed job {run_id} with {nb_insights} insights")


def fail_job(run_id: str, error_message: str) -> None:
    """
    Mark a job as failed with an error message.

    Args:
        run_id: Run identifier
        error_message: Error description (will be truncated to 2000 chars)
    """
    # Truncate error message to avoid DB issues
    if len(error_message) > 2000:
        error_message = error_message[:1997] + "..."

    with get_db_session() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run:
            run.status = JOB_STATUS_FAILED
            run.completed_at = datetime.now()
            run.error_message = error_message

            logger.error(f"Failed job {run_id}: {error_message[:100]}...")


def get_job_status(run_id: str) -> Optional[Dict]:
    """
    Get the current status of a job.

    Returns a subset of fields useful for polling:
    - status, progress, timestamps, error_message
    - nb_insights (if completed)

    Step 4: For cached runs, syncs status from the source (canonical) run.
    This ensures cached runs reflect the real-time status of the computation.

    Args:
        run_id: Run identifier

    Returns:
        Status dictionary or None if not found
    """
    with get_db_session() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run:
            # Step 4: For cached runs, get status from source run
            status = run.status
            progress = run.progress
            started_at = run.started_at
            completed_at = run.completed_at
            error_message = run.error_message
            nb_insights = run.nb_insights
            nb_clusters = run.nb_clusters

            if run.is_cached_result and run.source_run_id:
                # Sync status from the canonical (source) run
                source_run = db.query(Run).filter(Run.id == run.source_run_id).first()
                if source_run:
                    status = source_run.status
                    progress = source_run.progress
                    started_at = source_run.started_at
                    completed_at = source_run.completed_at
                    error_message = source_run.error_message
                    nb_insights = source_run.nb_insights
                    nb_clusters = source_run.nb_clusters

            return {
                "run_id": run.id,
                "status": status,
                "progress": progress,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "started_at": started_at.isoformat() if started_at else None,
                "completed_at": completed_at.isoformat() if completed_at else None,
                "error_message": error_message,
                "nb_insights": nb_insights,
                "nb_clusters": nb_clusters,
                "mode": run.mode,
                "run_mode": run.run_mode,
                "max_insights": run.max_insights,
                # Step 4: Include caching info
                "is_cached_result": run.is_cached_result,
                "source_run_id": run.source_run_id,
            }
        return None


def count_queued_jobs() -> int:
    """
    Count the number of canonical jobs in 'queued' status.

    Step 4: Only counts canonical runs (is_cached_result = false).
    Cached runs are not processed by workers.

    Useful for monitoring queue depth.

    Returns:
        Number of queued canonical jobs
    """
    with get_db_session() as db:
        return (
            db.query(Run)
            .filter(Run.status == JOB_STATUS_QUEUED)
            .filter(Run.is_cached_result == False)  # noqa: E712
            .count()
        )


def count_running_jobs() -> int:
    """
    Count the number of jobs in 'running' status.

    Useful for monitoring active workers.

    Returns:
        Number of running jobs
    """
    with get_db_session() as db:
        return db.query(Run).filter(Run.status == JOB_STATUS_RUNNING).count()


# ============================================================================
# Helper functions to convert ORM objects to dictionaries
# ============================================================================

def _run_to_dict(run: Run) -> Dict:
    """Convert Run ORM object to dictionary."""
    return {
        "id": run.id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        # User (Step 3: freemium)
        "user_id": run.user_id,
        # Job queue fields
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "progress": run.progress,
        "error_message": run.error_message,
        # Caching fields (Step 4)
        "cache_key": run.cache_key,
        "is_cached_result": run.is_cached_result,
        "source_run_id": run.source_run_id,
        # Configuration
        "config_name": run.config_name,
        "mode": run.mode,
        "run_mode": run.run_mode,
        "max_insights": run.max_insights,
        "input_pattern": run.input_pattern,
        # Results
        "nb_insights": run.nb_insights,
        "nb_clusters": run.nb_clusters,
        "total_cost_usd": run.total_cost_usd,
        "embed_cost_usd": run.embed_cost_usd,
        "summary_cost_usd": run.summary_cost_usd,
        "csv_path": run.csv_path,
        "json_path": run.json_path,
        "notes": run.notes,
        "run_stats": run.run_stats,
    }


def _insight_to_dict(insight: Insight) -> Dict:
    """Convert Insight ORM object to dictionary."""
    return {
        "id": insight.id,
        "run_id": insight.run_id,
        "rank": insight.rank,
        "mmr_rank": insight.mmr_rank,
        "cluster_id": insight.cluster_id,
        "size": insight.size,
        "sector": insight.sector,
        "title": insight.title,
        "problem": insight.problem,
        "persona": insight.persona,
        "jtbd": insight.jtbd,
        "context": insight.context,
        "mvp": insight.mvp,
        "alternatives": insight.alternatives,
        "willingness_to_pay_signal": insight.willingness_to_pay_signal,
        "monetizable": insight.monetizable,
        "pain_score_llm": insight.pain_score_llm,
        "pain_score_final": insight.pain_score_final,
        "heuristic_score": insight.heuristic_score,
        "traction_score": insight.traction_score,
        "novelty_score": insight.novelty_score,
        "trend_score": insight.trend_score,
        "founder_fit_score": insight.founder_fit_score,
        "priority_score": insight.priority_score,
        "priority_score_adjusted": insight.priority_score_adjusted,
        "keywords_matched": insight.keywords_matched,
        "source_mix": insight.source_mix,
        "example_urls": insight.example_urls,
        "created_at": insight.created_at.isoformat() if insight.created_at else None,
        # Step 5.1 / 5-bis
        "max_similarity_with_history": insight.max_similarity_with_history,
        "duplicate_of_insight_id": insight.duplicate_of_insight_id,
        "is_historical_duplicate": insight.is_historical_duplicate,
        "is_recurring_theme": insight.is_recurring_theme,
        "was_readded_by_fallback": insight.was_readded_by_fallback,
        # Step 5.2
        "solution_type": insight.solution_type,
        "recurring_revenue_potential": insight.recurring_revenue_potential,
        "saas_viable": insight.saas_viable,
        # Step 5.3
        "product_angle_title": insight.product_angle_title,
        "product_angle_summary": insight.product_angle_summary,
        "product_angle_type": insight.product_angle_type,
        "product_pricing_hint": insight.product_pricing_hint,
        "product_complexity": insight.product_complexity,
    }


def _exploration_to_dict(exploration: InsightExploration) -> Dict:
    """Convert InsightExploration ORM object to dictionary."""
    return {
        "id": exploration.id,
        "insight_id": exploration.insight_id,
        "created_at": exploration.created_at.isoformat() if exploration.created_at else None,
        "model_used": exploration.model_used,
        "exploration_text": exploration.exploration_text,
        "monetization_hypotheses": exploration.monetization_hypotheses,
        "product_variants": exploration.product_variants,
        "validation_steps": exploration.validation_steps,
    }
