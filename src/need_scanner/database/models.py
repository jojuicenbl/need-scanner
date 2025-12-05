"""SQLAlchemy ORM models for Need Scanner.

Tables:
- runs: Scan run metadata AND job queue (Step 2 architecture)
- insights: Individual insights from each run
- insight_explorations: Deep explorations of insights

Note: Primary keys preserve the existing format (timestamp-based strings)
for backwards compatibility with existing data. New UUID columns can be
added later if needed.

Job Queue Architecture (Step 2):
The `runs` table serves as both job queue and results storage.
Status lifecycle: queued → running → completed / failed
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# Valid job status values
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

VALID_JOB_STATUSES = {JOB_STATUS_QUEUED, JOB_STATUS_RUNNING, JOB_STATUS_COMPLETED, JOB_STATUS_FAILED}


class Run(Base):
    """Scan run metadata and job queue entry.

    This table serves dual purposes:
    1. Job queue: tracks pending/running scans with status lifecycle
    2. Results storage: stores completed scan metadata and statistics

    Status lifecycle:
    - queued: Job created, waiting for worker to pick it up
    - running: Worker is processing the scan
    - completed: Scan finished successfully
    - failed: Scan failed with an error
    """

    __tablename__ = "runs"

    # Primary key: timestamp-based ID like "20251126_143022"
    id = Column(String(50), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # =========================================================================
    # Job Queue Fields (Step 2)
    # =========================================================================

    # Job status: queued → running → completed / failed
    status = Column(String(20), nullable=False, default=JOB_STATUS_QUEUED)

    # Job lifecycle timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Progress tracking (0-100)
    progress = Column(Integer, nullable=True, default=0)

    # Error details if status == 'failed'
    error_message = Column(Text, nullable=True)

    # =========================================================================
    # Run Configuration (job parameters)
    # =========================================================================

    config_name = Column(String(100), nullable=True)
    mode = Column(String(20), nullable=True)  # "light" or "deep"
    run_mode = Column(String(20), nullable=True, default="discover")  # "discover" or "track"
    max_insights = Column(Integer, nullable=True)
    input_pattern = Column(String(255), nullable=True, default="data/raw/posts_*.json")

    # =========================================================================
    # Results Summary (populated after completion)
    # =========================================================================

    nb_insights = Column(Integer, nullable=True)
    nb_clusters = Column(Integer, nullable=True)

    # Cost tracking
    total_cost_usd = Column(Float, nullable=True)
    embed_cost_usd = Column(Float, nullable=True)
    summary_cost_usd = Column(Float, nullable=True)

    # Output paths
    csv_path = Column(Text, nullable=True)
    json_path = Column(Text, nullable=True)

    # Additional metadata
    notes = Column(Text, nullable=True)
    run_stats = Column(Text, nullable=True)  # JSON string for instrumentation stats

    # =========================================================================
    # Relationships
    # =========================================================================

    insights = relationship("Insight", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_runs_created_at", created_at.desc()),
        Index("idx_runs_status", "status"),
        Index("idx_runs_status_created_at", "status", "created_at"),
    )

    def __repr__(self):
        return f"<Run(id={self.id}, status={self.status}, mode={self.mode}, progress={self.progress})>"


class Insight(Base):
    """Individual insight from a scan run."""

    __tablename__ = "insights"

    # Primary key: format "{run_id}_cluster_{cluster_id}"
    id = Column(String(100), primary_key=True)

    # Foreign key to runs
    run_id = Column(String(50), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)

    # Ranking
    rank = Column(Integer, nullable=True)
    mmr_rank = Column(Integer, nullable=True)

    # Cluster info
    cluster_id = Column(Integer, nullable=True)
    size = Column(Integer, nullable=True)

    # Classification
    sector = Column(String(50), nullable=True)

    # Content
    title = Column(Text, nullable=False)
    problem = Column(Text, nullable=True)
    persona = Column(Text, nullable=True)
    jtbd = Column(Text, nullable=True)
    context = Column(Text, nullable=True)
    mvp = Column(Text, nullable=True)
    alternatives = Column(Text, nullable=True)  # JSON array
    willingness_to_pay_signal = Column(Text, nullable=True)
    monetizable = Column(Integer, nullable=True)  # 0/1 boolean

    # Scores
    pain_score_llm = Column(Float, nullable=True)
    pain_score_final = Column(Float, nullable=True)
    heuristic_score = Column(Float, nullable=True)
    traction_score = Column(Float, nullable=True)
    novelty_score = Column(Float, nullable=True)
    trend_score = Column(Float, nullable=True)
    founder_fit_score = Column(Float, nullable=True)
    priority_score = Column(Float, nullable=True)
    priority_score_adjusted = Column(Float, nullable=True)

    # Metadata
    keywords_matched = Column(Text, nullable=True)  # JSON array
    source_mix = Column(Text, nullable=True)  # JSON array
    example_urls = Column(Text, nullable=True)  # JSON array
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Step 5.1 / 5-bis: Inter-day deduplication
    max_similarity_with_history = Column(Float, nullable=True)
    duplicate_of_insight_id = Column(String(100), nullable=True)
    is_historical_duplicate = Column(Integer, default=0)  # 0/1 boolean
    is_recurring_theme = Column(Integer, default=0)  # 0/1 boolean
    was_readded_by_fallback = Column(Integer, default=0)  # 0/1 boolean

    # Step 5.2: SaaS-ability / Productizability
    solution_type = Column(String(50), nullable=True)
    recurring_revenue_potential = Column(Float, nullable=True)
    saas_viable = Column(Integer, nullable=True)  # 0/1/NULL boolean

    # Step 5.3: Product Ideation
    product_angle_title = Column(Text, nullable=True)
    product_angle_summary = Column(Text, nullable=True)
    product_angle_type = Column(String(50), nullable=True)
    product_pricing_hint = Column(Text, nullable=True)
    product_complexity = Column(Integer, nullable=True)

    # Relationships
    run = relationship("Run", back_populates="insights")
    explorations = relationship("InsightExploration", back_populates="insight", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_insights_run_id", run_id),
        Index("idx_insights_rank", rank),
        Index("idx_insights_priority_score", priority_score.desc()),
        Index("idx_insights_sector", sector),
        Index("idx_insights_created_at", created_at.desc()),
        Index("idx_insights_saas_viable", saas_viable),
    )

    def __repr__(self):
        return f"<Insight(id={self.id}, title={self.title[:30]}..., priority={self.priority_score})>"


class InsightExploration(Base):
    """Deep exploration of an insight using LLM."""

    __tablename__ = "insight_explorations"

    # Auto-incrementing primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to insights
    insight_id = Column(String(100), ForeignKey("insights.id", ondelete="CASCADE"), nullable=False)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    model_used = Column(String(50), nullable=True)

    # Content
    exploration_text = Column(Text, nullable=False)
    monetization_hypotheses = Column(Text, nullable=True)  # JSON string
    product_variants = Column(Text, nullable=True)  # JSON string
    validation_steps = Column(Text, nullable=True)  # JSON string

    # Relationships
    insight = relationship("Insight", back_populates="explorations")

    __table_args__ = (
        Index("idx_explorations_insight_id", insight_id),
    )

    def __repr__(self):
        return f"<InsightExploration(id={self.id}, insight_id={self.insight_id}, model={self.model_used})>"
