"""Database configuration and engine setup for PostgreSQL.

Reads DATABASE_URL from environment and creates SQLAlchemy engine.
Fails fast with clear error if DATABASE_URL is not set.
"""

import os
from functools import lru_cache
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from loguru import logger


class DatabaseConfigError(Exception):
    """Raised when database configuration is missing or invalid."""
    pass


def get_database_url() -> str:
    """
    Get the database URL from environment.

    Expects DATABASE_URL in standard Postgres format:
    postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DBNAME

    Returns:
        Database URL string

    Raises:
        DatabaseConfigError: If DATABASE_URL is not set
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise DatabaseConfigError(
            "DATABASE_URL environment variable is not set.\n"
            "Please set it to your PostgreSQL connection string.\n"
            "Example: postgresql+psycopg2://user:password@localhost:5432/needscanner\n"
            "For Supabase: postgresql+psycopg2://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
        )

    # Validate basic format
    if not database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise DatabaseConfigError(
            f"DATABASE_URL must be a PostgreSQL URL.\n"
            f"Got: {database_url[:30]}...\n"
            f"Expected format: postgresql+psycopg2://user:password@host:port/dbname"
        )

    # Normalize to use psycopg2 driver explicitly
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return database_url


@lru_cache(maxsize=1)
def get_engine(echo: bool = False) -> Engine:
    """
    Get or create the SQLAlchemy engine (singleton).

    Args:
        echo: If True, log all SQL statements (for debugging)

    Returns:
        SQLAlchemy Engine instance

    Raises:
        DatabaseConfigError: If DATABASE_URL is invalid
    """
    database_url = get_database_url()

    logger.info(f"Creating database engine for PostgreSQL")
    logger.debug(f"Database URL: {database_url[:50]}...")

    engine = create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10,
    )

    return engine


def test_connection() -> bool:
    """
    Test the database connection.

    Returns:
        True if connection successful

    Raises:
        Exception: If connection fails
    """
    engine = get_engine()

    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        raise
