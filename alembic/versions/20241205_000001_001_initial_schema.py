"""Initial schema for Need Scanner PostgreSQL migration.

Creates tables: runs, insights, insight_explorations
Matches the existing SQLite schema for data migration compatibility.

Revision ID: 001
Revises: None
Create Date: 2024-12-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create runs table
    op.create_table(
        "runs",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("config_name", sa.String(100), nullable=True),
        sa.Column("mode", sa.String(20), nullable=True),
        sa.Column("nb_insights", sa.Integer, nullable=True),
        sa.Column("nb_clusters", sa.Integer, nullable=True),
        sa.Column("total_cost_usd", sa.Float, nullable=True),
        sa.Column("embed_cost_usd", sa.Float, nullable=True),
        sa.Column("summary_cost_usd", sa.Float, nullable=True),
        sa.Column("csv_path", sa.Text, nullable=True),
        sa.Column("json_path", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("run_stats", sa.Text, nullable=True),
    )

    # Create index on runs.created_at
    op.create_index("idx_runs_created_at", "runs", [sa.text("created_at DESC")])

    # Create insights table
    op.create_table(
        "insights",
        # Primary key
        sa.Column("id", sa.String(100), primary_key=True),
        # Foreign key
        sa.Column(
            "run_id",
            sa.String(50),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Ranking
        sa.Column("rank", sa.Integer, nullable=True),
        sa.Column("mmr_rank", sa.Integer, nullable=True),
        # Cluster info
        sa.Column("cluster_id", sa.Integer, nullable=True),
        sa.Column("size", sa.Integer, nullable=True),
        # Classification
        sa.Column("sector", sa.String(50), nullable=True),
        # Content
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("problem", sa.Text, nullable=True),
        sa.Column("persona", sa.Text, nullable=True),
        sa.Column("jtbd", sa.Text, nullable=True),
        sa.Column("context", sa.Text, nullable=True),
        sa.Column("mvp", sa.Text, nullable=True),
        sa.Column("alternatives", sa.Text, nullable=True),
        sa.Column("willingness_to_pay_signal", sa.Text, nullable=True),
        sa.Column("monetizable", sa.Integer, nullable=True),
        # Scores
        sa.Column("pain_score_llm", sa.Float, nullable=True),
        sa.Column("pain_score_final", sa.Float, nullable=True),
        sa.Column("heuristic_score", sa.Float, nullable=True),
        sa.Column("traction_score", sa.Float, nullable=True),
        sa.Column("novelty_score", sa.Float, nullable=True),
        sa.Column("trend_score", sa.Float, nullable=True),
        sa.Column("founder_fit_score", sa.Float, nullable=True),
        sa.Column("priority_score", sa.Float, nullable=True),
        sa.Column("priority_score_adjusted", sa.Float, nullable=True),
        # Metadata
        sa.Column("keywords_matched", sa.Text, nullable=True),
        sa.Column("source_mix", sa.Text, nullable=True),
        sa.Column("example_urls", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        # Step 5.1 / 5-bis: Inter-day deduplication
        sa.Column("max_similarity_with_history", sa.Float, nullable=True),
        sa.Column("duplicate_of_insight_id", sa.String(100), nullable=True),
        sa.Column("is_historical_duplicate", sa.Integer, server_default="0"),
        sa.Column("is_recurring_theme", sa.Integer, server_default="0"),
        sa.Column("was_readded_by_fallback", sa.Integer, server_default="0"),
        # Step 5.2: SaaS-ability / Productizability
        sa.Column("solution_type", sa.String(50), nullable=True),
        sa.Column("recurring_revenue_potential", sa.Float, nullable=True),
        sa.Column("saas_viable", sa.Integer, nullable=True),
        # Step 5.3: Product Ideation
        sa.Column("product_angle_title", sa.Text, nullable=True),
        sa.Column("product_angle_summary", sa.Text, nullable=True),
        sa.Column("product_angle_type", sa.String(50), nullable=True),
        sa.Column("product_pricing_hint", sa.Text, nullable=True),
        sa.Column("product_complexity", sa.Integer, nullable=True),
    )

    # Create indexes on insights
    op.create_index("idx_insights_run_id", "insights", ["run_id"])
    op.create_index("idx_insights_rank", "insights", ["rank"])
    op.create_index("idx_insights_priority_score", "insights", [sa.text("priority_score DESC")])
    op.create_index("idx_insights_sector", "insights", ["sector"])
    op.create_index("idx_insights_created_at", "insights", [sa.text("created_at DESC")])
    op.create_index("idx_insights_saas_viable", "insights", ["saas_viable"])

    # Create insight_explorations table
    op.create_table(
        "insight_explorations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "insight_id",
            sa.String(100),
            sa.ForeignKey("insights.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("model_used", sa.String(50), nullable=True),
        sa.Column("exploration_text", sa.Text, nullable=False),
        sa.Column("monetization_hypotheses", sa.Text, nullable=True),
        sa.Column("product_variants", sa.Text, nullable=True),
        sa.Column("validation_steps", sa.Text, nullable=True),
    )

    # Create index on insight_explorations
    op.create_index("idx_explorations_insight_id", "insight_explorations", ["insight_id"])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("insight_explorations")
    op.drop_table("insights")
    op.drop_table("runs")
