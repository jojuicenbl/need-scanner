"""Add job queue columns to runs table.

Step 2 of the architecture: Scan Job Queue.
Extends the runs table to serve as a job queue with status lifecycle.

New columns:
- status: Job status (queued, running, completed, failed)
- started_at: When job started processing
- completed_at: When job finished
- progress: Progress percentage (0-100)
- error_message: Error details if failed
- run_mode: Scan mode (discover/track)
- max_insights: Requested max insights limit

Also adds indexes for efficient job picking:
- idx_runs_status: For querying by status
- idx_runs_status_created_at: Composite for job claiming queries

Revision ID: 002
Revises: 001
Create Date: 2024-12-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add job queue columns to runs table

    # Status column with default 'completed' for backwards compatibility
    # Existing runs were completed synchronously, so they should be 'completed'
    op.add_column(
        "runs",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="completed"
        )
    )

    # Timestamps for job lifecycle
    op.add_column(
        "runs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "runs",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )

    # Progress tracking (0-100)
    op.add_column(
        "runs",
        sa.Column("progress", sa.Integer, nullable=True, server_default="0")
    )

    # Error message for failed jobs
    op.add_column(
        "runs",
        sa.Column("error_message", sa.Text, nullable=True)
    )

    # Run configuration (not previously stored)
    op.add_column(
        "runs",
        sa.Column(
            "run_mode",
            sa.String(20),
            nullable=True,
            server_default="discover"
        )
    )
    op.add_column(
        "runs",
        sa.Column("max_insights", sa.Integer, nullable=True)
    )

    # Input pattern for the scan
    op.add_column(
        "runs",
        sa.Column(
            "input_pattern",
            sa.String(255),
            nullable=True,
            server_default="data/raw/posts_*.json"
        )
    )

    # Create indexes for efficient job picking
    # Index on status for filtering queued jobs
    op.create_index("idx_runs_status", "runs", ["status"])

    # Composite index for the job claiming query:
    # SELECT * FROM runs WHERE status = 'queued' ORDER BY created_at
    op.create_index(
        "idx_runs_status_created_at",
        "runs",
        ["status", "created_at"]
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_runs_status_created_at", table_name="runs")
    op.drop_index("idx_runs_status", table_name="runs")

    # Drop columns
    op.drop_column("runs", "input_pattern")
    op.drop_column("runs", "max_insights")
    op.drop_column("runs", "run_mode")
    op.drop_column("runs", "error_message")
    op.drop_column("runs", "progress")
    op.drop_column("runs", "completed_at")
    op.drop_column("runs", "started_at")
    op.drop_column("runs", "status")
