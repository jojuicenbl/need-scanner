"""FastAPI backend for Need Scanner.

Step 2 Architecture: Scan Job Queue
===================================
- POST /runs: Enqueues a scan job (returns immediately)
- GET /runs/{run_id}: Poll for job status and progress
- Worker process picks up jobs and runs scans asynchronously

Step 3 Architecture: Freemium Limits
====================================
- All scan/explore endpoints require authentication
- Free users: 1 scan/day, 3 explorations/month, 10 insights/run
- Premium users: unlimited

The HTTP API no longer runs scans synchronously. All scan work
is done by the worker process (see need_scanner.worker).
"""

import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from .db import (
    init_database,
    list_runs,
    get_run_insights,
    get_insight_by_id,
    save_exploration,
    get_explorations_for_insight,
    get_db_path,
    generate_run_id,
    enqueue_run,
    get_run_by_id,
    get_job_status,
    count_queued_jobs,
    count_running_jobs,
)
from .services.cache import (
    build_cache_key,
    find_canonical_run_by_cache_key,
    create_cached_run,
    create_canonical_run,
    get_effective_run_id_for_insights,
)
from .database import get_session, User, Run
from .auth import get_current_user, get_optional_user
from .limits import (
    ensure_can_run_scan,
    ensure_can_explore_insight,
    get_insight_limit_for_user,
    ensure_can_export,
    get_user_usage_stats,
    FREE_INSIGHTS_PER_RUN,
)
from .llm import explore_insight_with_llm
from .config import get_config


# Initialize FastAPI app
app = FastAPI(
    title="Need Scanner API",
    description="HTTP API for launching scans, retrieving insights, and exploring opportunities",
    version="3.0.0"
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Models
# ============================================================================

class ScanRequest(BaseModel):
    """Request model for creating a new scan job.

    This creates a job in the queue. The actual scan will be
    processed by a worker process asynchronously.
    """
    config_name: Optional[str] = Field(None, description="Configuration name (optional)")
    mode: str = Field("deep", description="Scan mode: 'light' or 'deep'")
    max_insights: Optional[int] = Field(None, description="Maximum number of insights to generate", ge=1, le=100)
    input_pattern: str = Field("data/raw/posts_*.json", description="Glob pattern for input files")
    run_mode: str = Field("discover", description="Run mode: 'discover' (filter duplicates/non-SaaS) or 'track' (show all)")

    class Config:
        json_schema_extra = {
            "example": {
                "mode": "deep",
                "max_insights": 20,
                "run_mode": "discover"
            }
        }


class ScanResponse(BaseModel):
    """Response model for scan job creation.

    The job is queued and will be processed by a worker.
    Poll GET /runs/{run_id} to check progress.
    """
    run_id: str
    status: str = "queued"
    created_at: str
    mode: str
    run_mode: str
    max_insights: Optional[int]
    message: str = "Job queued successfully. Poll GET /runs/{run_id} for status."


class RunStatus(BaseModel):
    """Status of a scan run (for polling).

    Use this to check job progress and completion.
    """
    run_id: str
    status: str  # queued, running, completed, failed
    progress: int  # 0-100
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    # Results (available after completion)
    nb_insights: Optional[int]
    nb_clusters: Optional[int]
    # Configuration
    mode: Optional[str]
    run_mode: Optional[str]
    max_insights: Optional[int]


class RunSummary(BaseModel):
    """Summary of a scan run for list views."""
    id: str
    created_at: str
    status: str
    progress: int
    config_name: Optional[str]
    mode: Optional[str]
    run_mode: Optional[str]
    nb_insights: Optional[int]
    nb_clusters: Optional[int]
    total_cost_usd: Optional[float]


class InsightSummary(BaseModel):
    """Summary of an insight for list views."""
    id: str
    run_id: str
    rank: int
    sector: Optional[str]
    title: str
    problem: Optional[str]
    priority_score: float
    pain_score_final: Optional[float]
    trend_score: Optional[float]
    founder_fit_score: Optional[float]
    # Step 5 / 5-bis additions
    solution_type: Optional[str] = None
    saas_viable: Optional[bool] = None
    is_historical_duplicate: Optional[bool] = None
    is_recurring_theme: Optional[bool] = None
    was_readded_by_fallback: Optional[bool] = None
    product_angle_title: Optional[str] = None


class InsightDetail(BaseModel):
    """Complete insight details."""
    id: str
    run_id: str
    rank: int
    mmr_rank: Optional[int]
    cluster_id: int
    size: int
    sector: Optional[str]
    title: str
    problem: Optional[str]
    persona: Optional[str]
    jtbd: Optional[str]
    context: Optional[str]
    mvp: Optional[str]
    alternatives: Optional[str]
    willingness_to_pay_signal: Optional[str]
    monetizable: Optional[int]
    pain_score_llm: Optional[float]
    pain_score_final: Optional[float]
    heuristic_score: Optional[float]
    traction_score: Optional[float]
    novelty_score: Optional[float]
    trend_score: Optional[float]
    founder_fit_score: Optional[float]
    priority_score: float
    priority_score_adjusted: Optional[float]
    keywords_matched: Optional[str]
    source_mix: Optional[str]
    example_urls: Optional[str]
    created_at: str
    # Step 5.1 / 5-bis: Inter-day deduplication
    max_similarity_with_history: Optional[float] = None
    duplicate_of_insight_id: Optional[str] = None
    is_historical_duplicate: Optional[bool] = None
    is_recurring_theme: Optional[bool] = None
    was_readded_by_fallback: Optional[bool] = None
    # Step 5.2: SaaS-ability / Productizability
    solution_type: Optional[str] = None
    recurring_revenue_potential: Optional[float] = None
    saas_viable: Optional[bool] = None
    # Step 5.3: Product Ideation
    product_angle_title: Optional[str] = None
    product_angle_summary: Optional[str] = None
    product_angle_type: Optional[str] = None
    product_pricing_hint: Optional[str] = None
    product_complexity: Optional[int] = None


class ExploreRequest(BaseModel):
    """Request model for exploring an insight."""
    model: Optional[str] = Field(None, description="LLM model to use (defaults to heavy model)")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "gpt-4o"
            }
        }


class ExplorationResponse(BaseModel):
    """Response model for insight exploration."""
    exploration_id: int
    insight_id: str
    full_text: str
    monetization_ideas: Optional[List[str]]
    product_variants: Optional[List[str]]
    validation_steps: Optional[List[str]]
    model_used: str
    cost_usd: float
    created_at: str


class ExplorationSummary(BaseModel):
    """Summary of an exploration."""
    id: int
    insight_id: str
    model_used: Optional[str]
    created_at: str
    preview: str  # First 200 chars of exploration_text


class InsightsResponse(BaseModel):
    """Response model for insights with freemium limit metadata.

    For free users, only up to 10 insights are returned.
    has_more indicates there are additional insights available with premium.
    """
    items: List[InsightSummary]
    total_count: int  # Total insights in the run (before limit)
    returned_count: int  # Number of insights returned
    has_more: bool  # True if there are more insights than returned
    limit_applied: Optional[int]  # The limit that was applied (None for premium)


class UsageStatsResponse(BaseModel):
    """Response model for user usage statistics."""
    plan: str
    is_premium: bool
    scans: dict
    explorations: dict
    insights_per_run: Optional[int]
    can_export: bool


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("Initializing Need Scanner API...")
    init_database()
    logger.info(f"Database initialized at {get_db_path()}")


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """API root endpoint."""
    return {
        "name": "Need Scanner API",
        "version": "3.0.0",
        "status": "running",
        "endpoints": {
            "POST /runs": "Launch a new scan",
            "GET /runs": "List recent runs",
            "GET /runs/{run_id}/insights": "Get insights for a run",
            "GET /insights/{insight_id}": "Get insight details",
            "POST /insights/{insight_id}/explore": "Explore an insight deeply",
            "GET /insights/{insight_id}/explorations": "Get explorations for an insight"
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint."""
    from .database import check_db_connection

    db_healthy = False
    try:
        db_healthy = check_db_connection()
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")

    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/queue/status", tags=["General"])
async def queue_status():
    """
    Get the current status of the job queue.

    Useful for monitoring queue depth and worker activity.

    **Example response:**
    ```json
    {
        "queued_jobs": 3,
        "running_jobs": 1,
        "timestamp": "2025-12-05T14:30:22"
    }
    ```
    """
    try:
        queued = count_queued_jobs()
        running = count_running_jobs()

        return {
            "queued_jobs": queued,
            "running_jobs": running,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching queue status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================================
# Runs Management
# ============================================================================

@app.post("/runs", response_model=ScanResponse, tags=["Runs"])
async def create_run(
    request: ScanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Create a new scan job (enqueue only).

    **Requires authentication.** Free users are limited to 1 scan per day.

    This endpoint creates a scan job in the queue and returns immediately.
    The actual scan will be processed asynchronously by a worker process.

    **Important:** This endpoint does NOT run the scan synchronously.
    Poll `GET /runs/{run_id}` to check job status and progress.

    **Caching (Step 4):**
    If a scan with the same configuration has already been run today,
    the results will be reused (cached). The run still counts toward
    your daily limit, but no new computation is performed.

    **Freemium limits:**
    - Free users: 1 scan per day
    - Premium users: unlimited scans

    **Mode options:**
    - `light`: Use lightweight model for all insights (faster, cheaper)
    - `deep`: Use heavy model for top insights (better quality)

    **Run mode options:**
    - `discover`: Filter out duplicates and non-SaaS insights (default)
    - `track`: Show all insights including duplicates

    **Example request:**
    ```json
    {
        "mode": "deep",
        "max_insights": 20,
        "run_mode": "discover"
    }
    ```

    **Example response:**
    ```json
    {
        "run_id": "20251205_143022",
        "status": "queued",
        "created_at": "2025-12-05T14:30:22",
        "mode": "deep",
        "run_mode": "discover",
        "max_insights": 20,
        "message": "Job queued successfully. Poll GET /runs/{run_id} for status."
    }
    ```
    """
    try:
        logger.info(f"User {current_user.id} requesting scan: mode={request.mode}, run_mode={request.run_mode}")

        # Step 3: Check freemium limits
        # Note: This counts existing runs for this user today.
        # Cached runs still count toward the limit (by design).
        ensure_can_run_scan(current_user, db)

        # Validate mode
        if request.mode not in ["light", "deep"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode '{request.mode}'. Must be 'light' or 'deep'."
            )

        # Validate run_mode
        if request.run_mode not in ["discover", "track"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid run_mode '{request.run_mode}'. Must be 'discover' or 'track'."
            )

        # Generate run ID
        run_id = generate_run_id()

        # =====================================================================
        # Step 4: Caching logic
        # =====================================================================
        # Build cache key for this scan configuration + today's date
        cache_key = build_cache_key(
            mode=request.mode,
            run_mode=request.run_mode,
            max_insights=request.max_insights,
            input_pattern=request.input_pattern,
        )

        # Try to find an existing canonical run with this cache key
        canonical_run = find_canonical_run_by_cache_key(db, cache_key)

        if canonical_run:
            # ===== Case A or B: Reuse existing canonical run =====
            # Create a cached run that references the canonical run
            cached_run = create_cached_run(
                db=db,
                canonical_run=canonical_run,
                user_id=current_user.id,
                run_id=run_id,
                mode=request.mode,
                run_mode=request.run_mode,
                max_insights=request.max_insights,
                input_pattern=request.input_pattern,
                config_name=request.config_name,
            )

            # Commit the transaction
            db.commit()

            # Determine appropriate message based on status
            if canonical_run.status == "completed":
                message = f"Results available (cached from today's scan). Use GET /runs/{run_id}/insights."
            else:
                message = f"Scan in progress. Poll GET /runs/{run_id} for status."

            logger.info(
                f"Created cached run {run_id} for user {current_user.id} "
                f"(source={canonical_run.id}, status={cached_run.status})"
            )

            return ScanResponse(
                run_id=run_id,
                status=cached_run.status,
                created_at=cached_run.created_at.isoformat() if cached_run.created_at else datetime.now().isoformat(),
                mode=request.mode,
                run_mode=request.run_mode,
                max_insights=request.max_insights,
                message=message,
            )

        else:
            # ===== Case C: No canonical run found, create new one =====
            new_run = create_canonical_run(
                db=db,
                user_id=current_user.id,
                run_id=run_id,
                cache_key=cache_key,
                mode=request.mode,
                run_mode=request.run_mode,
                max_insights=request.max_insights,
                input_pattern=request.input_pattern,
                config_name=request.config_name,
            )

            # Commit the transaction
            db.commit()

            logger.info(f"Scan job enqueued: run_id={run_id} for user {current_user.id}")

            return ScanResponse(
                run_id=run_id,
                status="queued",
                created_at=new_run.created_at.isoformat() if new_run.created_at else datetime.now().isoformat(),
                mode=request.mode,
                run_mode=request.run_mode,
                max_insights=request.max_insights,
                message=f"Job queued successfully. Poll GET /runs/{run_id} for status."
            )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error enqueuing scan job: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/runs", response_model=List[RunSummary], tags=["Runs"])
async def get_runs(
    limit: int = Query(10, description="Maximum number of runs to return", ge=1, le=100)
):
    """
    List recent scan runs.

    Returns a list of runs ordered by creation date (most recent first).
    Includes job status information for monitoring.

    **Query Parameters:**
    - `limit`: Maximum number of runs to return (1-100, default: 10)
    """
    try:
        runs = list_runs(limit=limit)

        return [
            RunSummary(
                id=run["id"],
                created_at=run["created_at"],
                status=run.get("status", "completed"),  # Default for legacy runs
                progress=run.get("progress", 100),  # Default for legacy runs
                config_name=run.get("config_name"),
                mode=run.get("mode"),
                run_mode=run.get("run_mode"),
                nb_insights=run.get("nb_insights"),
                nb_clusters=run.get("nb_clusters"),
                total_cost_usd=run.get("total_cost_usd", 0.0)
            )
            for run in runs
        ]

    except Exception as e:
        logger.error(f"Error fetching runs: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/runs/{run_id}", response_model=RunStatus, tags=["Runs"])
async def get_run_status(run_id: str):
    """
    Get the status of a specific scan run.

    Use this endpoint to poll for job progress and completion.
    Call this periodically (e.g., every 2-5 seconds) to track job status.

    **Status values:**
    - `queued`: Job is waiting to be processed
    - `running`: Job is being processed by a worker
    - `completed`: Job finished successfully
    - `failed`: Job failed with an error

    **Example response (running):**
    ```json
    {
        "run_id": "20251205_143022",
        "status": "running",
        "progress": 40,
        "created_at": "2025-12-05T14:30:22",
        "started_at": "2025-12-05T14:30:25",
        "completed_at": null,
        "error_message": null,
        "nb_insights": null,
        "nb_clusters": null,
        "mode": "deep",
        "run_mode": "discover",
        "max_insights": 20
    }
    ```

    **Example response (completed):**
    ```json
    {
        "run_id": "20251205_143022",
        "status": "completed",
        "progress": 100,
        "created_at": "2025-12-05T14:30:22",
        "started_at": "2025-12-05T14:30:25",
        "completed_at": "2025-12-05T14:32:10",
        "error_message": null,
        "nb_insights": 18,
        "nb_clusters": 25,
        "mode": "deep",
        "run_mode": "discover",
        "max_insights": 20
    }
    ```
    """
    try:
        status = get_job_status(run_id)

        if not status:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

        return RunStatus(
            run_id=status["run_id"],
            status=status["status"],
            progress=status.get("progress", 0),
            created_at=status.get("created_at"),
            started_at=status.get("started_at"),
            completed_at=status.get("completed_at"),
            error_message=status.get("error_message"),
            nb_insights=status.get("nb_insights"),
            nb_clusters=status.get("nb_clusters"),
            mode=status.get("mode"),
            run_mode=status.get("run_mode"),
            max_insights=status.get("max_insights"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching run status for {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/runs/{run_id}/insights", response_model=InsightsResponse, tags=["Runs"])
async def get_run_insights_endpoint(
    run_id: str,
    limit: Optional[int] = Query(None, description="Maximum number of insights to return", ge=1),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    min_priority: Optional[float] = Query(None, description="Minimum priority score", ge=0, le=10),
    saas_viable_only: bool = Query(False, description="Only return SaaS-viable insights"),
    include_duplicates: bool = Query(False, description="Include historical duplicates"),
    solution_type: Optional[str] = Query(None, description="Filter by solution type (saas_b2b, saas_b2c, tooling_dev, etc.)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get insights for a specific run.

    **Requires authentication.**

    **Caching (Step 4):**
    For cached runs, insights are automatically fetched from the canonical
    (source) run. The experience is transparent to the user.

    **Freemium limits:**
    - Free users: Maximum 10 insights visible per run
    - Premium users: All insights visible

    Returns insights for the given run_id, optionally filtered.
    The response includes metadata about whether there are more insights
    available (for free users who hit the limit).

    **Query Parameters:**
    - `limit`: Maximum number of insights to return
    - `sector`: Filter by sector (e.g., 'dev_tools', 'business_pme')
    - `min_priority`: Minimum priority score (0-10)
    - `saas_viable_only`: Only return SaaS-viable insights (default: false)
    - `include_duplicates`: Include historical duplicates (default: false)
    - `solution_type`: Filter by solution type
    """
    try:
        # =====================================================================
        # Step 4: Handle cached runs
        # =====================================================================
        # First, get the run to check if it's a cached run
        run = db.query(Run).filter(Run.id == run_id).first()

        if not run:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

        # Determine the effective run ID for querying insights
        # For cached runs, we query insights from the source (canonical) run
        effective_run_id = get_effective_run_id_for_insights(run)

        # If this is a cached run pointing to a still-running canonical run,
        # there may be no insights yet
        if run.is_cached_result and run.source_run_id:
            source_run = db.query(Run).filter(Run.id == run.source_run_id).first()
            if source_run and source_run.status not in ["completed"]:
                # Canonical run is still running, return empty with status info
                return InsightsResponse(
                    items=[],
                    total_count=0,
                    returned_count=0,
                    has_more=False,
                    limit_applied=get_insight_limit_for_user(current_user),
                )
            elif not source_run:
                # Source run was deleted - this should not happen in normal operation
                logger.error(f"Cached run {run_id} references missing source_run_id={run.source_run_id}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal error: source run not found for cached run {run_id}"
                )

        # Get insights using the effective run ID
        insights = get_run_insights(run_id=effective_run_id, limit=None)  # Get all, filter later

        if not insights:
            # No insights yet - could be a run that just completed with 0 insights
            # or a run that's still in progress
            return InsightsResponse(
                items=[],
                total_count=0,
                returned_count=0,
                has_more=False,
                limit_applied=get_insight_limit_for_user(current_user),
            )

        # Apply filters
        filtered_insights = insights

        if sector:
            filtered_insights = [i for i in filtered_insights if i.get("sector") == sector]

        if min_priority is not None:
            filtered_insights = [i for i in filtered_insights if i.get("priority_score", 0) >= min_priority]

        if saas_viable_only:
            filtered_insights = [i for i in filtered_insights if i.get("saas_viable") == 1]

        if not include_duplicates:
            # Step 5-bis: Keep insights that were re-added by fallback, even if they are duplicates
            filtered_insights = [
                i for i in filtered_insights
                if not i.get("is_historical_duplicate") or i.get("was_readded_by_fallback")
            ]

        if solution_type:
            filtered_insights = [i for i in filtered_insights if i.get("solution_type") == solution_type]

        # Track total count before freemium limit
        total_count = len(filtered_insights)

        # Step 3: Apply freemium insight limit
        freemium_limit = get_insight_limit_for_user(current_user)

        # User-specified limit takes precedence only if smaller than freemium limit
        effective_limit = None
        if freemium_limit is not None:
            if limit is not None:
                effective_limit = min(limit, freemium_limit)
            else:
                effective_limit = freemium_limit
        elif limit is not None:
            effective_limit = limit

        # Apply effective limit
        if effective_limit is not None:
            filtered_insights = filtered_insights[:effective_limit]

        returned_count = len(filtered_insights)
        has_more = returned_count < total_count

        items = [
            InsightSummary(
                id=insight["id"],
                run_id=insight["run_id"],
                rank=insight["rank"],
                sector=insight.get("sector"),
                title=insight["title"],
                problem=insight.get("problem"),
                priority_score=insight["priority_score"],
                pain_score_final=insight.get("pain_score_final"),
                trend_score=insight.get("trend_score"),
                founder_fit_score=insight.get("founder_fit_score"),
                solution_type=insight.get("solution_type"),
                saas_viable=bool(insight.get("saas_viable")) if insight.get("saas_viable") is not None else None,
                is_historical_duplicate=bool(insight.get("is_historical_duplicate")) if insight.get("is_historical_duplicate") is not None else None,
                is_recurring_theme=bool(insight.get("is_recurring_theme")) if insight.get("is_recurring_theme") is not None else None,
                was_readded_by_fallback=bool(insight.get("was_readded_by_fallback")) if insight.get("was_readded_by_fallback") is not None else None,
                product_angle_title=insight.get("product_angle_title")
            )
            for insight in filtered_insights
        ]

        return InsightsResponse(
            items=items,
            total_count=total_count,
            returned_count=returned_count,
            has_more=has_more,
            limit_applied=freemium_limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching insights for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================================
# Insights Management
# ============================================================================

@app.get("/insights/{insight_id}", response_model=InsightDetail, tags=["Insights"])
async def get_insight(insight_id: str):
    """
    Get complete details for a specific insight.

    Returns all fields for the given insight, including scores, content,
    and metadata.
    """
    try:
        insight = get_insight_by_id(insight_id=insight_id)

        if not insight:
            raise HTTPException(status_code=404, detail=f"Insight not found: {insight_id}")

        return InsightDetail(**insight)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching insight {insight_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================================
# Insight Exploration
# ============================================================================

@app.post("/insights/{insight_id}/explore", response_model=ExplorationResponse, tags=["Exploration"])
async def explore_insight(
    insight_id: str,
    request: ExploreRequest = ExploreRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Perform deep exploration of an insight using a heavy LLM.

    **Requires authentication.** Free users are limited to 3 explorations per month.

    This endpoint triggers a comprehensive analysis of the insight, including:
    - Market analysis
    - 2-3 monetization hypotheses
    - 2-3 product variants (MVP to ambitious vision)
    - 3 concrete validation steps

    The exploration is saved to the database and can be retrieved later.

    **Freemium limits:**
    - Free users: 3 deep explorations per month
    - Premium users: unlimited explorations

    **Example:**
    ```json
    {
        "model": "gpt-4o"
    }
    ```
    """
    try:
        # Step 3: Check freemium limits
        ensure_can_explore_insight(current_user, db)

        # Get insight from database
        insight = get_insight_by_id(insight_id=insight_id)

        if not insight:
            raise HTTPException(status_code=404, detail=f"Insight not found: {insight_id}")

        logger.info(f"User {current_user.id} exploring insight {insight_id} with LLM...")

        # Call LLM for exploration
        exploration_result = explore_insight_with_llm(
            insight_title=insight["title"],
            insight_problem=insight.get("problem", ""),
            persona=insight.get("persona"),
            context=insight.get("context"),
            pain_score=insight.get("pain_score_final"),
            trend_score=insight.get("trend_score"),
            model=request.model
        )

        # Save to database with user_id
        exploration_id = save_exploration(
            insight_id=insight_id,
            model_used=exploration_result["model_used"],
            exploration_text=exploration_result["full_text"],
            monetization_hypotheses=json.dumps(exploration_result.get("monetization_ideas", [])),
            product_variants=json.dumps(exploration_result.get("product_variants", [])),
            validation_steps=json.dumps(exploration_result.get("validation_steps", [])),
            user_id=current_user.id,
        )

        logger.info(f"Exploration {exploration_id} saved for insight {insight_id} by user {current_user.id}")

        return ExplorationResponse(
            exploration_id=exploration_id,
            insight_id=insight_id,
            full_text=exploration_result["full_text"],
            monetization_ideas=exploration_result.get("monetization_ideas"),
            product_variants=exploration_result.get("product_variants"),
            validation_steps=exploration_result.get("validation_steps"),
            model_used=exploration_result["model_used"],
            cost_usd=exploration_result["cost_usd"],
            created_at=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exploring insight {insight_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/insights/{insight_id}/explorations", response_model=List[ExplorationSummary], tags=["Exploration"])
async def get_insight_explorations(insight_id: str):
    """
    Get all explorations for a specific insight.

    Returns a list of explorations performed on this insight, ordered by
    creation date (most recent first).
    """
    try:
        explorations = get_explorations_for_insight(insight_id=insight_id)

        if not explorations:
            return []

        return [
            ExplorationSummary(
                id=exp["id"],
                insight_id=exp["insight_id"],
                model_used=exp.get("model_used"),
                created_at=exp["created_at"],
                preview=exp["exploration_text"][:200] + "..." if len(exp["exploration_text"]) > 200 else exp["exploration_text"]
            )
            for exp in explorations
        ]

    except Exception as e:
        logger.error(f"Error fetching explorations for insight {insight_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================================
# Export Endpoints (Premium Only)
# ============================================================================

@app.get("/runs/{run_id}/export/csv", tags=["Export"])
async def export_run_csv(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Export run insights as CSV.

    **Premium only.** Free users cannot export data.

    Returns a CSV file containing all insights from the run.
    """
    # Step 3: Check export permission
    ensure_can_export(current_user)

    # TODO: Implement actual CSV export
    # For now, return a stub that indicates the feature is available
    raise HTTPException(
        status_code=501,
        detail="CSV export is not yet implemented. This endpoint is reserved for premium users."
    )


@app.get("/runs/{run_id}/export/json", tags=["Export"])
async def export_run_json(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Export run insights as JSON.

    **Premium only.** Free users cannot export data.

    Returns a JSON file containing all insights from the run.
    """
    # Step 3: Check export permission
    ensure_can_export(current_user)

    # TODO: Implement actual JSON export
    # For now, return a stub that indicates the feature is available
    raise HTTPException(
        status_code=501,
        detail="JSON export is not yet implemented. This endpoint is reserved for premium users."
    )


# ============================================================================
# User & Usage Stats
# ============================================================================

@app.get("/me", tags=["User"])
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user information.

    Returns basic user info including plan status.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "plan": current_user.plan,
        "is_premium": current_user.is_premium,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }


@app.get("/me/usage", response_model=UsageStatsResponse, tags=["User"])
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Get current user's usage statistics.

    Returns current usage counts and remaining quota for:
    - Scans (daily limit for free users)
    - Deep explorations (monthly limit for free users)
    - Insight visibility (per-run limit for free users)
    - Export capability

    Useful for displaying remaining quota in the UI.
    """
    stats = get_user_usage_stats(current_user, db)
    return UsageStatsResponse(**stats)


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
