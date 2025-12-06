"""Freemium usage limits for Need Scanner.

Step 3: Freemium Limits

This module centralizes all freemium limit logic:
- Scan limits (1/day for free users)
- Deep exploration limits (3/month for free users)
- Insight visibility limits (10/run for free users)
- Export restrictions (premium only)

Limits are enforced by raising HTTPException with clear error messages.

Configuration:
- Limits are defined as constants at the top of this file
- To change limits, update the constants
- Premium users bypass all limits

Usage:
    from need_scanner.limits import ensure_can_run_scan, ensure_can_explore_insight

    @app.post("/runs")
    async def create_run(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_session),
    ):
        ensure_can_run_scan(current_user, db)
        # ... create run
"""

from typing import Optional
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from loguru import logger

from .database import User, Run, InsightExploration, PLAN_FREE


# =============================================================================
# Freemium Limit Constants
# =============================================================================

# Free tier limits
FREE_SCANS_PER_DAY = 1
FREE_EXPLORATIONS_PER_MONTH = 3
FREE_INSIGHTS_PER_RUN = 10

# Premium tier limits (None = unlimited)
PREMIUM_SCANS_PER_DAY = None
PREMIUM_EXPLORATIONS_PER_MONTH = None
PREMIUM_INSIGHTS_PER_RUN = None


# =============================================================================
# Error Codes
# =============================================================================

ERROR_SCAN_LIMIT = "SCAN_LIMIT_REACHED"
ERROR_EXPLORATION_LIMIT = "EXPLORATION_LIMIT_REACHED"
ERROR_EXPORT_RESTRICTED = "EXPORT_RESTRICTED"


# =============================================================================
# Limit Check Functions
# =============================================================================

def count_user_scans_today(user: User, db: Session) -> int:
    """
    Count how many scans the user has created today.

    Uses the runs table with created_at date comparison.

    Args:
        user: User to check
        db: Database session

    Returns:
        Number of scans created today
    """
    today = date.today()

    count = (
        db.query(func.count(Run.id))
        .filter(Run.user_id == user.id)
        .filter(func.date(Run.created_at) == today)
        .scalar()
    )

    return count or 0


def count_user_explorations_this_month(user: User, db: Session) -> int:
    """
    Count how many deep explorations the user has created this month.

    Uses the insight_explorations table with month/year comparison.

    Args:
        user: User to check
        db: Database session

    Returns:
        Number of explorations created this calendar month
    """
    today = date.today()

    count = (
        db.query(func.count(InsightExploration.id))
        .filter(InsightExploration.user_id == user.id)
        .filter(func.extract("year", InsightExploration.created_at) == today.year)
        .filter(func.extract("month", InsightExploration.created_at) == today.month)
        .scalar()
    )

    return count or 0


def ensure_can_run_scan(user: User, db: Session) -> None:
    """
    Check if user can create a new scan.

    Free users: limited to FREE_SCANS_PER_DAY scans per day
    Premium users: unlimited

    Args:
        user: User attempting to create scan
        db: Database session

    Raises:
        HTTPException: 403 if limit reached
    """
    # Premium users bypass all limits
    if user.is_premium:
        return

    # Count today's scans
    scans_today = count_user_scans_today(user, db)

    if scans_today >= FREE_SCANS_PER_DAY:
        logger.warning(
            f"User {user.id} hit scan limit: {scans_today}/{FREE_SCANS_PER_DAY} today"
        )
        raise HTTPException(
            status_code=403,
            detail={
                "detail": f"Free plan limit reached: {FREE_SCANS_PER_DAY} market scan per day. Upgrade to run more scans.",
                "code": ERROR_SCAN_LIMIT,
                "plan": user.plan,
                "limit": {
                    "scans_per_day": FREE_SCANS_PER_DAY,
                    "used_today": scans_today,
                },
            },
        )

    logger.debug(f"User {user.id} can run scan: {scans_today}/{FREE_SCANS_PER_DAY} today")


def ensure_can_explore_insight(user: User, db: Session) -> None:
    """
    Check if user can create a new deep exploration.

    Free users: limited to FREE_EXPLORATIONS_PER_MONTH per month
    Premium users: unlimited

    Args:
        user: User attempting to create exploration
        db: Database session

    Raises:
        HTTPException: 403 if limit reached
    """
    # Premium users bypass all limits
    if user.is_premium:
        return

    # Count this month's explorations
    explorations_this_month = count_user_explorations_this_month(user, db)

    if explorations_this_month >= FREE_EXPLORATIONS_PER_MONTH:
        logger.warning(
            f"User {user.id} hit exploration limit: {explorations_this_month}/{FREE_EXPLORATIONS_PER_MONTH} this month"
        )
        raise HTTPException(
            status_code=403,
            detail={
                "detail": f"Free plan limit reached: {FREE_EXPLORATIONS_PER_MONTH} deep explorations per month. Upgrade for unlimited explorations.",
                "code": ERROR_EXPLORATION_LIMIT,
                "plan": user.plan,
                "limit": {
                    "explorations_per_month": FREE_EXPLORATIONS_PER_MONTH,
                    "used_this_month": explorations_this_month,
                },
            },
        )

    logger.debug(
        f"User {user.id} can explore: {explorations_this_month}/{FREE_EXPLORATIONS_PER_MONTH} this month"
    )


def get_insight_limit_for_user(user: User) -> Optional[int]:
    """
    Get the insight visibility limit for a user.

    Free users: LIMITED to FREE_INSIGHTS_PER_RUN
    Premium users: None (unlimited)

    Args:
        user: User to check

    Returns:
        Maximum number of insights to show, or None for unlimited
    """
    if user.is_premium:
        return PREMIUM_INSIGHTS_PER_RUN  # None = unlimited

    return FREE_INSIGHTS_PER_RUN


def ensure_can_export(user: User) -> None:
    """
    Check if user can export data (CSV/JSON).

    Free users: NOT allowed
    Premium users: allowed

    Args:
        user: User attempting to export

    Raises:
        HTTPException: 403 if not allowed
    """
    if user.is_premium:
        return

    logger.warning(f"User {user.id} attempted export on free plan")
    raise HTTPException(
        status_code=403,
        detail={
            "detail": "Exports are only available on the premium plan.",
            "code": ERROR_EXPORT_RESTRICTED,
            "plan": user.plan,
        },
    )


# =============================================================================
# Usage Stats (for API responses)
# =============================================================================

def get_user_usage_stats(user: User, db: Session) -> dict:
    """
    Get current usage statistics for a user.

    Useful for showing remaining quota in UI.

    Args:
        user: User to check
        db: Database session

    Returns:
        Dictionary with usage stats and limits
    """
    scans_today = count_user_scans_today(user, db)
    explorations_this_month = count_user_explorations_this_month(user, db)

    return {
        "plan": user.plan,
        "is_premium": user.is_premium,
        "scans": {
            "used_today": scans_today,
            "limit_per_day": FREE_SCANS_PER_DAY if user.is_free else None,
            "remaining_today": max(0, FREE_SCANS_PER_DAY - scans_today) if user.is_free else None,
        },
        "explorations": {
            "used_this_month": explorations_this_month,
            "limit_per_month": FREE_EXPLORATIONS_PER_MONTH if user.is_free else None,
            "remaining_this_month": max(0, FREE_EXPLORATIONS_PER_MONTH - explorations_this_month) if user.is_free else None,
        },
        "insights_per_run": FREE_INSIGHTS_PER_RUN if user.is_free else None,
        "can_export": user.is_premium,
    }
