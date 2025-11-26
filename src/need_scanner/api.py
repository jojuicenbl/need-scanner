"""FastAPI backend for Need Scanner."""

import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

from .core import run_scan as core_run_scan
from .db import (
    init_database,
    list_runs,
    get_run_insights,
    get_insight_by_id,
    save_exploration,
    get_explorations_for_insight,
    get_db_path
)
from .llm import explore_insight_with_llm
from .config import get_config


# Initialize FastAPI app
app = FastAPI(
    title="Need Scanner API",
    description="HTTP API for launching scans, retrieving insights, and exploring opportunities",
    version="3.0.0"
)


# ============================================================================
# Pydantic Models
# ============================================================================

class ScanRequest(BaseModel):
    """Request model for creating a new scan."""
    config_name: Optional[str] = Field(None, description="Configuration name (optional)")
    mode: str = Field("deep", description="Scan mode: 'light' or 'deep'")
    max_insights: Optional[int] = Field(None, description="Maximum number of insights to generate")
    input_pattern: str = Field("data/raw/posts_*.json", description="Glob pattern for input files")

    class Config:
        json_schema_extra = {
            "example": {
                "mode": "deep",
                "max_insights": 20
            }
        }


class ScanResponse(BaseModel):
    """Response model for scan creation."""
    run_id: str
    status: str = "started"
    message: str


class RunSummary(BaseModel):
    """Summary of a scan run."""
    id: str
    created_at: str
    config_name: Optional[str]
    mode: str
    nb_insights: int
    nb_clusters: int
    total_cost_usd: float


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
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Runs Management
# ============================================================================

@app.post("/runs", response_model=ScanResponse, tags=["Runs"])
async def create_run(
    request: ScanRequest,
    background_tasks: BackgroundTasks
):
    """
    Launch a new scan run.

    This endpoint starts a new scan in the background and returns immediately
    with the run_id. The scan will process posts, generate insights, and save
    results to the database.

    **Mode options:**
    - `light`: Use lightweight model for all insights (faster, cheaper)
    - `deep`: Use heavy model for top insights (better quality)

    **Example:**
    ```json
    {
        "mode": "deep",
        "max_insights": 20
    }
    ```
    """
    try:
        logger.info(f"Creating new scan run: mode={request.mode}, max_insights={request.max_insights}")

        # Validate mode
        if request.mode not in ["light", "deep"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode '{request.mode}'. Must be 'light' or 'deep'."
            )

        # Run scan synchronously (for now - could be made async with background tasks)
        run_id = core_run_scan(
            config_name=request.config_name,
            mode=request.mode,
            max_insights=request.max_insights,
            input_pattern=request.input_pattern,
            save_to_db=True
        )

        return ScanResponse(
            run_id=run_id,
            status="completed",
            message=f"Scan completed successfully. Run ID: {run_id}"
        )

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating scan run: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/runs", response_model=List[RunSummary], tags=["Runs"])
async def get_runs(
    limit: int = Query(10, description="Maximum number of runs to return", ge=1, le=100)
):
    """
    List recent scan runs.

    Returns a list of runs ordered by creation date (most recent first).

    **Query Parameters:**
    - `limit`: Maximum number of runs to return (1-100, default: 10)
    """
    try:
        runs = list_runs(limit=limit)

        return [
            RunSummary(
                id=run["id"],
                created_at=run["created_at"],
                config_name=run.get("config_name"),
                mode=run["mode"],
                nb_insights=run["nb_insights"],
                nb_clusters=run["nb_clusters"],
                total_cost_usd=run.get("total_cost_usd", 0.0)
            )
            for run in runs
        ]

    except Exception as e:
        logger.error(f"Error fetching runs: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/runs/{run_id}/insights", response_model=List[InsightSummary], tags=["Runs"])
async def get_run_insights_endpoint(
    run_id: str,
    limit: Optional[int] = Query(None, description="Maximum number of insights to return", ge=1),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    min_priority: Optional[float] = Query(None, description="Minimum priority score", ge=0, le=10)
):
    """
    Get insights for a specific run.

    Returns all insights for the given run_id, optionally filtered by sector
    and minimum priority score.

    **Query Parameters:**
    - `limit`: Maximum number of insights to return
    - `sector`: Filter by sector (e.g., 'dev_tools', 'business_pme')
    - `min_priority`: Minimum priority score (0-10)
    """
    try:
        insights = get_run_insights(run_id=run_id, limit=limit)

        if not insights:
            raise HTTPException(status_code=404, detail=f"No insights found for run_id: {run_id}")

        # Apply filters
        filtered_insights = insights

        if sector:
            filtered_insights = [i for i in filtered_insights if i.get("sector") == sector]

        if min_priority is not None:
            filtered_insights = [i for i in filtered_insights if i.get("priority_score", 0) >= min_priority]

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
                founder_fit_score=insight.get("founder_fit_score")
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
