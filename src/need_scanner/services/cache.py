"""Caching service for scan results.

Step 4: Caching of Daily Results

This module provides functions for:
- Building deterministic cache keys for scan configurations
- Finding existing canonical runs for cache reuse
- Creating cached runs that reference canonical runs

The caching strategy:
- cache_key = SHA256(JSON({mode, run_mode, max_insights, input_pattern, date}))
- Canonical runs (is_cached_result=false) are actually computed by workers
- Cached runs (is_cached_result=true) reuse results from a canonical run

Cache key includes:
- mode: "light" or "deep"
- run_mode: "discover" or "track"
- max_insights: int or None
- input_pattern: glob pattern for input files
- date: UTC date (resets cache daily)

Cache key does NOT include:
- user_id: We want cross-user reuse
- config_name: Optional label, not part of scan logic
"""

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any

from loguru import logger
from sqlalchemy.orm import Session

from ..database import Run
from ..database.models import (
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
)


def build_cache_key(
    mode: str,
    run_mode: str,
    max_insights: Optional[int],
    input_pattern: str,
    now: Optional[datetime] = None,
) -> str:
    """
    Build a deterministic cache key for a scan configuration.

    The cache key is a SHA256 hash of the scan parameters plus the date.
    This ensures:
    - Same config on same day = same cache key (cross-user reuse)
    - Cache resets daily at midnight UTC

    Args:
        mode: Scan mode ('light' or 'deep')
        run_mode: Run mode ('discover' or 'track')
        max_insights: Maximum number of insights (or None)
        input_pattern: Glob pattern for input files
        now: Optional datetime for date calculation (defaults to UTC now)

    Returns:
        64-character hex string (SHA256 hash)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Build signature dict with all cache-relevant parameters
    # Sorted keys ensure deterministic JSON serialization
    signature: Dict[str, Any] = {
        "date": now.date().isoformat(),  # e.g. "2024-12-06"
        "input_pattern": input_pattern,
        "max_insights": max_insights,
        "mode": mode,
        "run_mode": run_mode,
    }

    # Serialize deterministically
    signature_json = json.dumps(signature, sort_keys=True, separators=(",", ":"))

    # Compute SHA256 hash
    cache_key = hashlib.sha256(signature_json.encode("utf-8")).hexdigest()

    logger.debug(f"Built cache_key={cache_key[:16]}... for signature={signature}")

    return cache_key


def find_canonical_run_by_cache_key(
    db: Session,
    cache_key: str,
) -> Optional[Run]:
    """
    Find an existing canonical run for the given cache key.

    A canonical run is one that:
    - Has the same cache_key
    - is_cached_result = false (actually computed, not a cache reference)
    - status is 'running' or 'completed' (not failed or queued)

    If multiple matches exist, returns the oldest (first created) one.
    This ensures all cached runs point to the same canonical run.

    Args:
        db: Database session
        cache_key: The cache key to search for

    Returns:
        The canonical Run if found, None otherwise
    """
    canonical_run = (
        db.query(Run)
        .filter(Run.cache_key == cache_key)
        .filter(Run.is_cached_result == False)  # noqa: E712 (SQLAlchemy comparison)
        .filter(Run.status.in_([JOB_STATUS_RUNNING, JOB_STATUS_COMPLETED]))
        .order_by(Run.created_at.asc())
        .first()
    )

    if canonical_run:
        logger.info(
            f"Found canonical run {canonical_run.id} (status={canonical_run.status}) "
            f"for cache_key={cache_key[:16]}..."
        )
    else:
        logger.debug(f"No canonical run found for cache_key={cache_key[:16]}...")

    return canonical_run


def create_cached_run(
    db: Session,
    canonical_run: Run,
    user_id: str,
    run_id: str,
    mode: str,
    run_mode: str,
    max_insights: Optional[int],
    input_pattern: str,
    config_name: Optional[str] = None,
) -> Run:
    """
    Create a cached run that reuses results from a canonical run.

    The cached run:
    - Has is_cached_result = true
    - Points to canonical run via source_run_id
    - Mirrors the canonical run's status and progress
    - Counts as a scan for the user (freemium accounting)

    Args:
        db: Database session
        canonical_run: The canonical run to reference
        user_id: User creating this run
        run_id: Unique run ID for the new run
        mode: Scan mode (should match canonical run)
        run_mode: Run mode (should match canonical run)
        max_insights: Max insights (should match canonical run)
        input_pattern: Input pattern (should match canonical run)
        config_name: Optional configuration name

    Returns:
        The newly created cached Run
    """
    now = datetime.now(timezone.utc)

    # Mirror the canonical run's status
    # If canonical is completed, mark as completed
    # If canonical is running, mark as running (user sees progress)
    status = canonical_run.status
    progress = canonical_run.progress if canonical_run.progress else 0
    completed_at = canonical_run.completed_at if status == JOB_STATUS_COMPLETED else None

    # Copy result metadata if completed
    nb_insights = canonical_run.nb_insights if status == JOB_STATUS_COMPLETED else None
    nb_clusters = canonical_run.nb_clusters if status == JOB_STATUS_COMPLETED else None

    cached_run = Run(
        id=run_id,
        created_at=now,
        user_id=user_id,
        # Caching fields
        cache_key=canonical_run.cache_key,
        is_cached_result=True,
        source_run_id=canonical_run.id,
        # Status mirrors canonical run
        status=status,
        progress=progress,
        started_at=canonical_run.started_at,
        completed_at=completed_at,
        # Configuration
        config_name=config_name,
        mode=mode,
        run_mode=run_mode,
        max_insights=max_insights,
        input_pattern=input_pattern,
        # Results (if completed)
        nb_insights=nb_insights,
        nb_clusters=nb_clusters,
        # Cost fields are 0 for cached runs (no compute)
        total_cost_usd=0.0,
        embed_cost_usd=0.0,
        summary_cost_usd=0.0,
    )

    db.add(cached_run)
    db.flush()  # Ensure the run is written

    logger.info(
        f"Created cached run {run_id} (user={user_id}) "
        f"referencing canonical run {canonical_run.id} (status={status})"
    )

    return cached_run


def create_canonical_run(
    db: Session,
    user_id: str,
    run_id: str,
    cache_key: str,
    mode: str,
    run_mode: str,
    max_insights: Optional[int],
    input_pattern: str,
    config_name: Optional[str] = None,
) -> Run:
    """
    Create a new canonical run that will be processed by the worker.

    The canonical run:
    - Has is_cached_result = false
    - Has source_run_id = NULL
    - Gets status = 'queued' for worker pickup
    - Will have insights stored once completed

    Args:
        db: Database session
        user_id: User creating this run
        run_id: Unique run ID
        cache_key: The cache key for this configuration + date
        mode: Scan mode ('light' or 'deep')
        run_mode: Run mode ('discover' or 'track')
        max_insights: Maximum number of insights
        input_pattern: Glob pattern for input files
        config_name: Optional configuration name

    Returns:
        The newly created canonical Run
    """
    now = datetime.now(timezone.utc)

    canonical_run = Run(
        id=run_id,
        created_at=now,
        user_id=user_id,
        # Caching fields
        cache_key=cache_key,
        is_cached_result=False,
        source_run_id=None,
        # Queued for worker pickup
        status=JOB_STATUS_QUEUED,
        progress=0,
        # Configuration
        config_name=config_name,
        mode=mode,
        run_mode=run_mode,
        max_insights=max_insights,
        input_pattern=input_pattern,
    )

    db.add(canonical_run)
    db.flush()  # Ensure the run is written

    logger.info(
        f"Created canonical run {run_id} (user={user_id}) "
        f"with cache_key={cache_key[:16]}... status=queued"
    )

    return canonical_run


def get_effective_run_id_for_insights(run: Run) -> str:
    """
    Get the run ID to use when querying insights.

    For cached runs, insights are stored on the canonical run.
    This function returns the appropriate run ID to query.

    Args:
        run: The run to get insights for

    Returns:
        The run ID where insights are stored
    """
    if run.is_cached_result and run.source_run_id:
        logger.debug(
            f"Run {run.id} is cached, using source_run_id={run.source_run_id} for insights"
        )
        return run.source_run_id

    return run.id
