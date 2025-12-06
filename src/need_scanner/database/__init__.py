"""Database package for Need Scanner - PostgreSQL with SQLAlchemy.

Step 2 Architecture: The `runs` table serves as both job queue and results storage.
Status lifecycle: queued -> running -> completed / failed

Step 3 Architecture: Freemium limits
- Users table with plan ('free' or 'premium')
- Runs and explorations linked to users via user_id
"""

from .config import get_database_url, get_engine, DatabaseConfigError
from .models import (
    Base,
    User,
    Run,
    Insight,
    InsightExploration,
    # Job status constants
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    VALID_JOB_STATUSES,
    # Plan constants (Step 3)
    PLAN_FREE,
    PLAN_PREMIUM,
    VALID_PLANS,
)
from .session import get_session, get_db_session, SessionLocal, init_db, check_db_connection

__all__ = [
    # Config
    "get_database_url",
    "get_engine",
    "DatabaseConfigError",
    # Models
    "Base",
    "User",
    "Run",
    "Insight",
    "InsightExploration",
    # Job status constants
    "JOB_STATUS_QUEUED",
    "JOB_STATUS_RUNNING",
    "JOB_STATUS_COMPLETED",
    "JOB_STATUS_FAILED",
    "VALID_JOB_STATUSES",
    # Plan constants (Step 3)
    "PLAN_FREE",
    "PLAN_PREMIUM",
    "VALID_PLANS",
    # Session management
    "get_session",
    "get_db_session",
    "SessionLocal",
    "init_db",
    "check_db_connection",
]
