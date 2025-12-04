"""Tests for database module."""

import pytest
from pathlib import Path
import tempfile
import os

from src.need_scanner.db import (
    init_database,
    generate_run_id,
    save_run,
    save_insights,
    get_latest_run,
    list_runs,
    get_run_insights
)
from src.need_scanner.schemas import EnrichedInsight, EnrichedClusterSummary


def test_init_database():
    """Test database initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        init_database(db_path)

        assert db_path.exists()


def test_generate_run_id():
    """Test run ID generation."""
    run_id = generate_run_id()

    assert isinstance(run_id, str)
    assert len(run_id) > 0
    assert "_" in run_id  # Format: YYYYMMDD_HHMMSS


def test_save_and_load_run():
    """Test saving and loading run metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_database(db_path)

        run_id = "test_run_001"

        save_run(
            run_id=run_id,
            config_name="test_config",
            mode="deep",
            nb_insights=10,
            nb_clusters=5,
            total_cost_usd=0.05,
            db_path=db_path
        )

        # Get latest run
        latest = get_latest_run(db_path)
        assert latest is not None
        assert latest['id'] == run_id
        assert latest['mode'] == "deep"
        assert latest['nb_insights'] == 10

        # List runs
        runs = list_runs(limit=10, db_path=db_path)
        assert len(runs) == 1
        assert runs[0]['id'] == run_id


def test_save_and_load_insights():
    """Test saving and loading insights."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_database(db_path)

        run_id = "test_run_002"

        # Create mock insights
        summary = EnrichedClusterSummary(
            cluster_id=1,
            size=5,
            title="Test Problem",
            problem="Test problem description",
            persona="Test User",
            jtbd="Test JTBD",
            context="Test context",
            monetizable=True,
            mvp="Test MVP",
            alternatives=["Tool1", "Tool2"],
            willingness_to_pay_signal="looking for solution",
            pain_score_llm=8,
            sector="dev_tools"
        )

        insight = EnrichedInsight(
            cluster_id=1,
            rank=1,
            priority_score=7.5,
            examples=[{"url": "https://example.com/post1"}],
            summary=summary,
            pain_score_final=8,
            heuristic_score=7.0,
            traction_score=6.5,
            novelty_score=7.2,
            trend_score=6.8,
            founder_fit_score=8.5,
            source_mix=["reddit", "hn"]
        )

        # Save run first
        save_run(
            run_id=run_id,
            config_name="test",
            mode="deep",
            nb_insights=1,
            nb_clusters=1,
            db_path=db_path
        )

        # Save insights
        save_insights(run_id, [insight], db_path)

        # Load insights
        loaded = get_run_insights(run_id, db_path=db_path)

        assert len(loaded) == 1
        assert loaded[0]['title'] == "Test Problem"
        assert loaded[0]['priority_score'] == 7.5
        assert loaded[0]['trend_score'] == 6.8
        assert loaded[0]['founder_fit_score'] == 8.5
        assert loaded[0]['sector'] == "dev_tools"


def test_multiple_runs():
    """Test handling multiple runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_database(db_path)

        # Create multiple runs
        for i in range(5):
            run_id = f"test_run_{i:03d}"
            save_run(
                run_id=run_id,
                config_name="test",
                mode="deep" if i % 2 == 0 else "light",
                nb_insights=i + 1,
                nb_clusters=i + 1,
                db_path=db_path
            )

        # List runs
        runs = list_runs(limit=10, db_path=db_path)

        assert len(runs) == 5

        # Verify latest is first
        assert runs[0]['id'] == "test_run_004"

        # Test limit
        limited = list_runs(limit=2, db_path=db_path)
        assert len(limited) == 2
