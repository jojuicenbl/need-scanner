"""Authentication and authorization for Need Scanner API.

Step 3: Freemium Limits

This module provides user authentication for the API.

DEVELOPMENT MODE (current):
- Uses X-Dummy-User-Id header for user identification
- Auto-creates users on first request
- All new users get 'free' plan by default

PRODUCTION MODE (future):
- Replace with Supabase Auth / JWT token validation
- Keep the same get_current_user() interface

Usage in endpoints:
    @app.post("/runs")
    async def create_run(
        request: ScanRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_session),
    ):
        ...
"""

from typing import Optional
from datetime import datetime

from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from loguru import logger

from .database import (
    get_session,
    User,
    PLAN_FREE,
)


# Header name for development auth
DUMMY_USER_HEADER = "X-Dummy-User-Id"


class AuthenticationError(HTTPException):
    """Raised when authentication fails."""

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_or_create_user(db: Session, user_id: str) -> User:
    """
    Get existing user or create a new one.

    New users are created with:
    - plan='free'
    - email=None

    Args:
        db: Database session
        user_id: User identifier (from header or token)

    Returns:
        User model instance
    """
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        logger.info(f"Creating new user: {user_id}")
        user = User(
            id=user_id,
            email=None,
            plan=PLAN_FREE,
            created_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


async def get_current_user(
    x_dummy_user_id: Optional[str] = Header(None, alias=DUMMY_USER_HEADER),
    db: Session = Depends(get_session),
) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    DEVELOPMENT MODE:
    - Reads user ID from X-Dummy-User-Id header
    - Auto-creates user if not exists
    - Returns 401 if header is missing

    PRODUCTION MODE (future):
    - Validate JWT token from Authorization header
    - Extract user ID from token claims
    - Return 401 if token is invalid or expired

    Args:
        x_dummy_user_id: User ID from header (development)
        db: Database session

    Returns:
        User model instance

    Raises:
        HTTPException: 401 if not authenticated
    """
    if x_dummy_user_id is None:
        raise AuthenticationError(
            detail="Authentication required. Provide X-Dummy-User-Id header."
        )

    # Validate user ID format (basic check)
    user_id = x_dummy_user_id.strip()
    if not user_id or len(user_id) > 100:
        raise AuthenticationError(
            detail="Invalid user ID format."
        )

    # Get or create user
    user = get_or_create_user(db, user_id)

    logger.debug(f"Authenticated user: {user.id} (plan={user.plan})")

    return user


async def get_optional_user(
    x_dummy_user_id: Optional[str] = Header(None, alias=DUMMY_USER_HEADER),
    db: Session = Depends(get_session),
) -> Optional[User]:
    """
    FastAPI dependency to optionally get current user.

    Same as get_current_user but returns None instead of 401
    when no authentication is provided. Useful for endpoints
    that work differently for authenticated vs anonymous users.

    Args:
        x_dummy_user_id: User ID from header (development)
        db: Database session

    Returns:
        User model instance or None
    """
    if x_dummy_user_id is None:
        return None

    user_id = x_dummy_user_id.strip()
    if not user_id or len(user_id) > 100:
        return None

    return get_or_create_user(db, user_id)


def require_premium(user: User) -> None:
    """
    Helper to check if user has premium plan.

    Raises HTTPException 403 if user is on free plan.

    Args:
        user: User to check

    Raises:
        HTTPException: 403 if user is not premium
    """
    if not user.is_premium:
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "This feature requires a premium plan.",
                "code": "PREMIUM_REQUIRED",
                "plan": user.plan,
            },
        )
