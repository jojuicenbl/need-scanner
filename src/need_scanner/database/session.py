"""Database session management for Need Scanner.

Provides:
- SessionLocal: Session factory for creating database sessions
- get_session: FastAPI dependency for request-scoped sessions
- init_db: Initialize database schema (creates tables)
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from .config import get_engine
from .models import Base


# Create session factory (lazy initialization)
_SessionLocal = None


def get_session_factory() -> sessionmaker:
    """Get or create the session factory."""
    global _SessionLocal

    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )

    return _SessionLocal


def SessionLocal() -> Session:
    """Create a new database session."""
    factory = get_session_factory()
    return factory()


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Yields a session that is automatically closed after the request.
    Use with Depends() in FastAPI routes.

    Example:
        @app.get("/runs")
        def list_runs(db: Session = Depends(get_session)):
            return db.query(Run).all()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions (non-FastAPI usage).

    Example:
        with get_db_session() as db:
            runs = db.query(Run).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Initialize the database by creating all tables.

    Note: In production, use Alembic migrations instead.
    This function is useful for development and testing.
    """
    engine = get_engine()

    logger.info("Initializing database schema...")

    # Create all tables defined in models
    Base.metadata.create_all(bind=engine)

    logger.info("Database schema initialized successfully")


def check_db_connection() -> bool:
    """
    Verify database connection is working.

    Returns:
        True if connection successful, raises exception otherwise
    """
    from sqlalchemy import text

    engine = get_engine()

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise
