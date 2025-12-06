"""Add users table and user_id to runs/explorations for freemium limits.

Step 3: Freemium Limits

Creates:
- users table with id, email, plan, created_at
- user_id FK on runs table
- user_id FK on insight_explorations table
- Indexes for efficient limit queries

Revision ID: 003
Revises: 002
Create Date: 2024-12-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Valid plan values
PLAN_FREE = "free"
PLAN_PREMIUM = "premium"


def upgrade() -> None:
    # =========================================================================
    # 1. Create users table
    # =========================================================================
    op.create_table(
        "users",
        sa.Column("id", sa.String(100), primary_key=True),  # UUID or external ID
        sa.Column("email", sa.String(255), nullable=True, unique=True),
        sa.Column("plan", sa.String(20), nullable=False, server_default=PLAN_FREE),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Index for email lookups
    op.create_index("idx_users_email", "users", ["email"], unique=True)
    # Index for plan-based queries
    op.create_index("idx_users_plan", "users", ["plan"])

    # =========================================================================
    # 2. Add user_id to runs table
    # =========================================================================
    op.add_column(
        "runs",
        sa.Column("user_id", sa.String(100), nullable=True),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_runs_user_id",
        "runs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Index for efficient user scan count queries
    # Used by: ensure_can_run_scan() to count today's scans
    op.create_index("idx_runs_user_id", "runs", ["user_id"])
    op.create_index(
        "idx_runs_user_created_date",
        "runs",
        ["user_id", sa.text("DATE(created_at)")],
    )

    # =========================================================================
    # 3. Add user_id to insight_explorations table
    # =========================================================================
    op.add_column(
        "insight_explorations",
        sa.Column("user_id", sa.String(100), nullable=True),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_insight_explorations_user_id",
        "insight_explorations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Index for efficient user exploration count queries
    # Used by: ensure_can_explore_insight() to count monthly explorations
    op.create_index("idx_explorations_user_id", "insight_explorations", ["user_id"])
    op.create_index(
        "idx_explorations_user_created_month",
        "insight_explorations",
        ["user_id", sa.text("DATE_TRUNC('month', created_at)")],
    )


def downgrade() -> None:
    # Remove indexes and columns in reverse order

    # 3. Remove from insight_explorations
    op.drop_index("idx_explorations_user_created_month", table_name="insight_explorations")
    op.drop_index("idx_explorations_user_id", table_name="insight_explorations")
    op.drop_constraint("fk_insight_explorations_user_id", "insight_explorations", type_="foreignkey")
    op.drop_column("insight_explorations", "user_id")

    # 2. Remove from runs
    op.drop_index("idx_runs_user_created_date", table_name="runs")
    op.drop_index("idx_runs_user_id", table_name="runs")
    op.drop_constraint("fk_runs_user_id", "runs", type_="foreignkey")
    op.drop_column("runs", "user_id")

    # 1. Drop users table
    op.drop_index("idx_users_plan", table_name="users")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")
