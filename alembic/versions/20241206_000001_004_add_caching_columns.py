"""Add caching columns to runs table.

Step 4: Caching of Daily Results

Adds:
- cache_key: Deterministic key for scan configuration + date
- is_cached_result: Whether this run reuses another run's results
- source_run_id: FK to the canonical run (for cached runs)
- Composite index for efficient cache lookups

This enables reusing scan results across users on the same day
while maintaining per-user run records for freemium accounting.

Revision ID: 004
Revises: 003
Create Date: 2024-12-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # 1. Add cache_key column
    # =========================================================================
    # Deterministic key representing scan configuration + date
    # Format: SHA256 hash of JSON {mode, run_mode, max_insights, date}
    op.add_column(
        "runs",
        sa.Column("cache_key", sa.Text(), nullable=True),
    )

    # =========================================================================
    # 2. Add is_cached_result column
    # =========================================================================
    # false = canonical run (actually computed by worker)
    # true = per-user run that reuses another run's results
    op.add_column(
        "runs",
        sa.Column(
            "is_cached_result",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # =========================================================================
    # 3. Add source_run_id column
    # =========================================================================
    # For cached runs: points to the canonical run whose results are reused
    # For canonical runs: NULL
    op.add_column(
        "runs",
        sa.Column("source_run_id", sa.String(50), nullable=True),
    )

    # Add foreign key constraint (self-referential)
    op.create_foreign_key(
        "fk_runs_source_run_id",
        "runs",
        "runs",
        ["source_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # =========================================================================
    # 4. Add indexes for efficient cache lookups
    # =========================================================================
    # Composite index for finding canonical runs by cache_key
    # Used by: POST /runs to find existing canonical run for the same config+day
    op.create_index(
        "idx_runs_cache_key_canonical",
        "runs",
        ["cache_key", "is_cached_result", "created_at"],
    )

    # Index on source_run_id for finding cached runs pointing to a canonical run
    op.create_index(
        "idx_runs_source_run_id",
        "runs",
        ["source_run_id"],
    )


def downgrade() -> None:
    # Remove in reverse order

    # 4. Drop indexes
    op.drop_index("idx_runs_source_run_id", table_name="runs")
    op.drop_index("idx_runs_cache_key_canonical", table_name="runs")

    # 3. Drop source_run_id
    op.drop_constraint("fk_runs_source_run_id", "runs", type_="foreignkey")
    op.drop_column("runs", "source_run_id")

    # 2. Drop is_cached_result
    op.drop_column("runs", "is_cached_result")

    # 1. Drop cache_key
    op.drop_column("runs", "cache_key")
