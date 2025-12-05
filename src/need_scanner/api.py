"""FastAPI backend for Need Scanner.

Step 2 Architecture: Scan Job Queue
===================================
- POST /runs: Enqueues a scan job (returns immediately)
- GET /runs/{run_id}: Poll for job status and progress
- Worker process picks up jobs and runs scans asynchronously

The HTTP API no longer runs scans synchronously. All scan work
is done by the worker process (see need_scanner.worker).
"""

import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
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
async def create_run(request: ScanRequest):
    """
    Create a new scan job (enqueue only).

    This endpoint creates a scan job in the queue and returns immediately.
    The actual scan will be processed asynchronously by a worker process.

    **Important:** This endpoint does NOT run the scan synchronously.
    Poll `GET /runs/{run_id}` to check job status and progress.

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
        logger.info(f"Enqueuing new scan job: mode={request.mode}, run_mode={request.run_mode}, max_insights={request.max_insights}")

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

        # Enqueue the job (does NOT run the scan)
        run_data = enqueue_run(
            run_id=run_id,
            mode=request.mode,
            run_mode=request.run_mode,
            max_insights=request.max_insights,
            input_pattern=request.input_pattern,
            config_name=request.config_name,
        )

        logger.info(f"Scan job enqueued: run_id={run_id}")

        return ScanResponse(
            run_id=run_id,
            status="queued",
            created_at=run_data["created_at"],
            mode=request.mode,
            run_mode=request.run_mode,
            max_insights=request.max_insights,
            message=f"Job queued successfully. Poll GET /runs/{run_id} for status."
        )

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


@app.get("/runs/{run_id}/insights", response_model=List[InsightSummary], tags=["Runs"])
async def get_run_insights_endpoint(
    run_id: str,
    limit: Optional[int] = Query(None, description="Maximum number of insights to return", ge=1),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    min_priority: Optional[float] = Query(None, description="Minimum priority score", ge=0, le=10),
    saas_viable_only: bool = Query(False, description="Only return SaaS-viable insights"),
    include_duplicates: bool = Query(False, description="Include historical duplicates"),
    solution_type: Optional[str] = Query(None, description="Filter by solution type (saas_b2b, saas_b2c, tooling_dev, etc.)")
):
    """
    Get insights for a specific run.

    Returns all insights for the given run_id, optionally filtered.

    **Query Parameters:**
    - `limit`: Maximum number of insights to return
    - `sector`: Filter by sector (e.g., 'dev_tools', 'business_pme')
    - `min_priority`: Minimum priority score (0-10)
    - `saas_viable_only`: Only return SaaS-viable insights (default: false)
    - `include_duplicates`: Include historical duplicates (default: false)
    - `solution_type`: Filter by solution type (saas_b2b, saas_b2c, tooling_dev, api_product, service_only, content_only, hardware_required, regulation_policy, impractical_unclear)
    """
    try:
        insights = get_run_insights(run_id=run_id, limit=None)  # Get all, filter later

        if not insights:
            raise HTTPException(status_code=404, detail=f"No insights found for run_id: {run_id}")

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

        # Apply limit after filtering
        if limit:
            filtered_insights = filtered_insights[:limit]

        return [
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
    request: ExploreRequest = ExploreRequest()
):
    """
    Perform deep exploration of an insight using a heavy LLM.

    This endpoint triggers a comprehensive analysis of the insight, including:
    - Market analysis
    - 2-3 monetization hypotheses
    - 2-3 product variants (MVP to ambitious vision)
    - 3 concrete validation steps

    The exploration is saved to the database and can be retrieved later.

    **Example:**
    ```json
    {
        "model": "gpt-4o"
    }
    ```
    """
    try:
        # Get insight from database
        insight = get_insight_by_id(insight_id=insight_id)

        if not insight:
            raise HTTPException(status_code=404, detail=f"Insight not found: {insight_id}")

        logger.info(f"Exploring insight {insight_id} with LLM...")

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

        # Save to database
        exploration_id = save_exploration(
            insight_id=insight_id,
            model_used=exploration_result["model_used"],
            exploration_text=exploration_result["full_text"],
            monetization_hypotheses=json.dumps(exploration_result.get("monetization_ideas", [])),
            product_variants=json.dumps(exploration_result.get("product_variants", [])),
            validation_steps=json.dumps(exploration_result.get("validation_steps", []))
        )

        logger.info(f"Exploration {exploration_id} saved for insight {insight_id}")

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
