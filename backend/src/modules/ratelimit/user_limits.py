"""
User prompt limit service for tracking and enforcing per-user Claude API limits.

Implements a weekly rolling window limit of 250 prompts per user for Claude API calls.
Uses the user_limits table to track usage across the 7-day window.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import Depends, HTTPException, status

from app.dependencies import TenantContext, get_current_tenant
from database.pool import get_db_pool

log = logging.getLogger(__name__)

# Configuration constants
WEEKLY_PROMPT_LIMIT = 250
WINDOW_DAYS = 7
LIMIT_TYPE = "claude_weekly_prompts"


class UserLimitError(Exception):
    """Raised when user limit operations fail."""
    pass


async def get_user_email_from_id(pool: asyncpg.Pool, user_id: str) -> str:
    """
    Get user email from auth.users table using user_id.
    
    Args:
        pool: Database connection pool
        user_id: The user's UUID from JWT token
        
    Returns:
        The user's email address
        
    Raises:
        UserLimitError: If user lookup fails
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT email
                FROM auth.users
                WHERE id = $1
                """,
                user_id
            )
            if row is None:
                raise UserLimitError(f"User not found: {user_id}")
            return row["email"]
    except asyncpg.PostgresError as exc:
        log.error("Database error fetching user email: %s", exc)
        raise UserLimitError(f"Failed to fetch user email: {exc}") from exc


async def check_and_increment_prompt_limit(
    pool: asyncpg.Pool,
    user_email: str,
) -> bool:
    """
    Check if user is within their weekly prompt limit and increment if allowed.
    
    This implements a rolling 7-day window:
    - If the current window has expired (> 7 days since window_start), reset the counter
    - If the user has exceeded 250 prompts in the current window, return False
    - Otherwise, increment the counter and return True
    
    Args:
        pool: Database connection pool
        user_email: The user's email address (used as identifier)
        
    Returns:
        True if the request is allowed (limit not exceeded), False otherwise
        
    Raises:
        UserLimitError: If database operations fail
    """
    try:
        async with pool.acquire() as conn:
            # Use a transaction to ensure atomicity
            async with conn.transaction():
                # First, try to get existing record
                row = await conn.fetchrow(
                    """
                    SELECT window_start, prompt_count
                    FROM public.user_limits
                    WHERE email = $1 AND limit_type = $2
                    FOR UPDATE
                    """,
                    user_email,
                    LIMIT_TYPE
                )
                
                now = datetime.now(timezone.utc)
                
                if row is None:
                    # No existing record - create one with count = 1
                    await conn.execute(
                        """
                        INSERT INTO public.user_limits (email, limit_type, window_start, prompt_count)
                        VALUES ($1, $2, $3, 1)
                        """,
                        user_email,
                        LIMIT_TYPE,
                        now
                    )
                    log.info("Created new limit record for user %s", user_email)
                    return True
                
                window_start = row["window_start"]
                prompt_count = row["prompt_count"]
                
                # Check if window has expired (7 days)
                window_expiry = window_start + timedelta(days=WINDOW_DAYS)
                if now >= window_expiry:
                    # Reset the window - start new window with count = 1
                    await conn.execute(
                        """
                        UPDATE public.user_limits
                        SET window_start = $1, prompt_count = 1
                        WHERE email = $2 AND limit_type = $3
                        """,
                        now,
                        user_email,
                        LIMIT_TYPE
                    )
                    log.info("Reset limit window for user %s", user_email)
                    return True
                
                # Check if limit exceeded
                if prompt_count >= WEEKLY_PROMPT_LIMIT:
                    log.warning(
                        "User %s exceeded weekly prompt limit: %d/%d",
                        user_email,
                        prompt_count,
                        WEEKLY_PROMPT_LIMIT
                    )
                    return False
                
                # Increment counter
                await conn.execute(
                    """
                    UPDATE public.user_limits
                    SET prompt_count = prompt_count + 1
                    WHERE email = $1 AND limit_type = $2
                    """,
                    user_email,
                    LIMIT_TYPE
                )
                log.debug(
                    "Incremented prompt count for user %s: %d/%d",
                    user_email,
                    prompt_count + 1,
                    WEEKLY_PROMPT_LIMIT
                )
                return True
                
    except asyncpg.PostgresError as exc:
        log.error("Database error in check_and_increment_prompt_limit: %s", exc)
        raise UserLimitError(f"Failed to check/increment prompt limit: {exc}") from exc


async def get_user_prompt_usage(
    pool: asyncpg.Pool,
    user_email: str,
) -> dict:
    """
    Get current prompt usage statistics for a user.
    
    Args:
        pool: Database connection pool
        user_email: The user's email address
        
    Returns:
        Dictionary with current usage information:
        {
            "prompt_count": int,
            "limit": int,
            "window_start": datetime,
            "window_end": datetime,
            "remaining": int
        }
        
    Raises:
        UserLimitError: If database operations fail
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT window_start, prompt_count
                FROM public.user_limits
                WHERE email = $1 AND limit_type = $2
                """,
                user_email,
                LIMIT_TYPE
            )
            
            if row is None:
                # No usage yet
                now = datetime.now(timezone.utc)
                return {
                    "prompt_count": 0,
                    "limit": WEEKLY_PROMPT_LIMIT,
                    "window_start": now,
                    "window_end": now + timedelta(days=WINDOW_DAYS),
                    "remaining": WEEKLY_PROMPT_LIMIT
                }
            
            window_start = row["window_start"]
            prompt_count = row["prompt_count"]
            window_end = window_start + timedelta(days=WINDOW_DAYS)
            
            return {
                "prompt_count": prompt_count,
                "limit": WEEKLY_PROMPT_LIMIT,
                "window_start": window_start,
                "window_end": window_end,
                "remaining": max(0, WEEKLY_PROMPT_LIMIT - prompt_count)
            }
            
    except asyncpg.PostgresError as exc:
        log.error("Database error in get_user_prompt_usage: %s", exc)
        raise UserLimitError(f"Failed to get prompt usage: {exc}") from exc


async def enforce_user_prompt_limit(
    pool: asyncpg.Pool,
    user_id: str,
) -> None:
    """
    FastAPI dependency function to enforce user prompt limits.
    
    This function:
    1. Gets the user's email from their user_id
    2. Checks if they're within their weekly prompt limit
    3. Increments their usage if allowed
    4. Raises HTTP 429 if limit exceeded
    
    Args:
        pool: Database connection pool
        user_id: The user's UUID from JWT token
        
    Raises:
        HTTPException: With status 429 if limit exceeded
        UserLimitError: If database operations fail
    """
    try:
        # Get user email
        user_email = await get_user_email_from_id(pool, user_id)
        
        # Check and increment limit
        allowed = await check_and_increment_prompt_limit(pool, user_email)
        
        if not allowed:
            # Get usage info for the error message
            usage = await get_user_prompt_usage(pool, user_email)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Weekly prompt limit exceeded ({usage['prompt_count']}/{usage['limit']}). "
                    f"Window resets on {usage['window_end'].strftime('%Y-%m-%d %H:%M:%S UTC')}."
                ),
                headers={
                    "Retry-After": str(int((usage['window_end'] - datetime.now(timezone.utc)).total_seconds())),
                    "X-PromptLimit": str(usage['limit']),
                    "X-PromptUsed": str(usage['prompt_count']),
                    "X-PromptRemaining": str(usage['remaining']),
                    "X-WindowReset": usage['window_end'].isoformat()
                }
            )
            
    except UserLimitError as exc:
        log.error("User limit enforcement failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enforce prompt limit"
        ) from exc


def enforce_user_prompt_limit_dependency():
    """
    FastAPI dependency factory for enforcing user prompt limits.
    
    Usage in route handlers:
        @router.post("/search")
        async def search_endpoint(
            request: SearchRequest,
            ctx: TenantContext = Depends(get_current_tenant),
            _: None = Depends(enforce_user_prompt_limit_dependency()),
        ):
            ...
    
    This dependency:
    - Extracts the authenticated user context
    - Enforces the weekly 250 prompt limit per user
    - Raises HTTP 429 if limit exceeded
    """
    
    async def _dependency(
        ctx: TenantContext = Depends(get_current_tenant),
    ) -> None:
        pool = get_db_pool()
        await enforce_user_prompt_limit(pool, ctx.user_id)
    
    return _dependency
