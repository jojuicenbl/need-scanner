"""Integration tests for Need Scanner FastAPI backend."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import json

from need_scanner.api import app
from need_scanner.db import init_database, save_run, save_insights, get_db_path
from need_scanner.schemas import EnrichedInsight, ClusterSummary


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Initialize database
    init_database(db_path)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def sample_run_data(temp_db):
    """Create sample run data in the test database."""
    run_id = "test_20251126_120000"

    # Save a sample run
    save_run(
        run_id=run_id,
        config_name="test",
        mode="light",
        nb_insights=2,
        nb_clusters=3,
        total_cost_usd=0.01,
        embed_cost_usd=0.005,
        summary_cost_usd=0.005,
        csv_path=f"test_{run_id}.csv",
        json_path=f"test_{run_id}.json",
        notes="Test run",
        db_path=temp_db
    )

    # Create sample insights
    insights = [
        EnrichedInsight(
            cluster_id=1,
            rank=1,
            mmr_rank=1,
            summary=ClusterSummary(
                cluster_id=1,
                size=10,
                sector="dev_tools",
                title="Test Insight 1",
                problem="Test problem 1",
                persona="Developer",
                jtbd="Test JTBD",
                context="Test context",
                mvp="Test MVP",
                alternatives=[],
                willingness_to_pay_signal="looking for paid solution",
                monetizable=True,
                pain_score_llm=8.0
            ),
            pain_score_final=8.0,
            heuristic_score=7.5,
            traction_score=6.0,
            novelty_score=7.0,
            trend_score=6.5,
            founder_fit_score=8.0,
            priority_score=7.2,
            priority_score_adjusted=7.2,
            keywords_matched=[],
            source_mix={},
            examples=[]
        ),
        EnrichedInsight(
            cluster_id=2,
            rank=2,
            mmr_rank=2,
            summary=ClusterSummary(
                cluster_id=2,
                size=8,
                sector="business_pme",
                title="Test Insight 2",
                problem="Test problem 2",
                persona="Small Business Owner",
                jtbd="Test JTBD 2",
                context="Test context 2",
                mvp="Test MVP 2",
                alternatives=[],
                willingness_to_pay_signal="willing to pay",
                monetizable=True,
                pain_score_llm=7.0
            ),
            pain_score_final=7.0,
            heuristic_score=6.5,
            traction_score=5.5,
            novelty_score=6.5,
            trend_score=6.0,
            founder_fit_score=7.0,
            priority_score=6.5,
            priority_score_adjusted=6.5,
            keywords_matched=[],
            source_mix={},
            examples=[]
        )
    ]

    save_insights(
        run_id=run_id,
        insights=insights,
        db_path=temp_db
    )

    return {
        "run_id": run_id,
        "insights": insights,
        "db_path": temp_db
    }


# ============================================================================
# Tests - General Endpoints
# ============================================================================

def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Need Scanner API"
    assert data["version"] == "3.0.0"
    assert "endpoints" in data


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


# ============================================================================
# Tests - Runs Management
# ============================================================================

def test_list_runs_empty(client):
    """Test listing runs when database is empty."""
    response = client.get("/runs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_runs_with_data(client, sample_run_data):
    """Test listing runs with sample data."""
    # Note: This test requires the API to use the temp database
    # In a real scenario, you'd need to configure the API to use temp_db
    # For now, this is a placeholder test
    pass


def test_get_run_insights_not_found(client):
    """Test getting insights for non-existent run."""
    response = client.get("/runs/nonexistent_run/insights")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


# ============================================================================
# Tests - Insights Management
# ============================================================================

def test_get_insight_not_found(client):
    """Test getting non-existent insight."""
    response = client.get("/insights/nonexistent_insight")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


# ============================================================================
# Tests - Scan Creation
# ============================================================================

def test_create_scan_invalid_mode(client):
    """Test creating scan with invalid mode."""
    response = client.post(
        "/runs",
        json={"mode": "invalid_mode"}
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Invalid mode" in data["detail"]


def test_create_scan_missing_data(client):
    """Test creating scan with missing input data."""
    response = client.post(
        "/runs",
        json={
            "mode": "light",
            "input_pattern": "nonexistent/*.json"
        }
    )
    # This should fail because no data files exist
    assert response.status_code in [404, 500]


# ============================================================================
# Tests - Exploration
# ============================================================================

def test_explore_insight_not_found(client):
    """Test exploring non-existent insight."""
    response = client.post(
        "/insights/nonexistent_insight/explore",
        json={}
    )
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_get_explorations_empty(client):
    """Test getting explorations for non-existent insight."""
    response = client.get("/insights/nonexistent_insight/explorations")
    # This should return empty list, not error
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


# ============================================================================
# Tests - Request Validation
# ============================================================================

def test_scan_request_validation(client):
    """Test scan request validation."""
    # Valid request
    valid_request = {
        "mode": "light",
        "max_insights": 10
    }
    # Note: Will fail due to missing data, but should pass validation
    response = client.post("/runs", json=valid_request)
    # We expect 404 (no data) or 500, not 422 (validation error)
    assert response.status_code != 422


def test_explore_request_validation(client):
    """Test explore request validation."""
    # Empty request should be valid (uses defaults)
    response = client.post(
        "/insights/test_insight/explore",
        json={}
    )
    # Should get 404 (insight not found), not 422 (validation error)
    assert response.status_code != 422


# ============================================================================
# Tests - Query Parameters
# ============================================================================

def test_runs_limit_validation(client):
    """Test runs endpoint limit parameter validation."""
    # Valid limit
    response = client.get("/runs?limit=5")
    assert response.status_code == 200

    # Limit too high (should be capped at 100)
    response = client.get("/runs?limit=200")
    assert response.status_code == 422  # Validation error


def test_insights_filters(client):
    """Test insights endpoint filter parameters."""
    run_id = "test_run"

    # Test sector filter
    response = client.get(f"/runs/{run_id}/insights?sector=dev_tools")
    # Should get 404 (run not found), but query params should be valid
    assert response.status_code != 422

    # Test min_priority filter
    response = client.get(f"/runs/{run_id}/insights?min_priority=5.0")
    assert response.status_code != 422

    # Test combined filters
    response = client.get(f"/runs/{run_id}/insights?sector=dev_tools&min_priority=6.0&limit=5")
    assert response.status_code != 422


# ============================================================================
# Integration Test (requires data)
# ============================================================================

@pytest.mark.skip(reason="Requires actual data files and can be slow")
def test_full_scan_workflow(client):
    """
    Full integration test: create scan, list runs, get insights, explore.

    This test is skipped by default because it:
    - Requires actual data files in data/raw/
    - Makes real API calls to OpenAI
    - Can be slow

    To run: pytest tests/test_api.py::test_full_scan_workflow -v
    """
    # 1. Create a scan
    response = client.post(
        "/runs",
        json={"mode": "light", "max_insights": 3}
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # 2. List runs
    response = client.get("/runs?limit=1")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) > 0
    assert runs[0]["id"] == run_id

    # 3. Get insights
    response = client.get(f"/runs/{run_id}/insights")
    assert response.status_code == 200
    insights = response.json()
    assert len(insights) > 0

    # 4. Get insight detail
    insight_id = insights[0]["id"]
    response = client.get(f"/insights/{insight_id}")
    assert response.status_code == 200
    insight = response.json()
    assert insight["id"] == insight_id

    # 5. Explore insight (skipped - too expensive)
    # response = client.post(
    #     f"/insights/{insight_id}/explore",
    #     json={"model": "gpt-4o-mini"}
    # )
    # assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
