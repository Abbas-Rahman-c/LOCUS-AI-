"""
User prompt limit service for tracking and enforcing per-entity Claude API limits.

Implements a weekly rolling window limit of 250 prompts per entity for Claude API calls.
Uses the user_limits table to track usage across the 7-day window.
The limit_key can represent email, user_id, organization_id, or other identifier
depending on the desired rate limiting scope.
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


async def get_user_limit_key_from_id(pool: asyncpg.Pool, user_id: str) -> str:
    """
    Get user limit key from auth.users table using user_id.
    
    Currently uses email as the limit key, but this can be extended to use
    user_id, organization_id, or other identifiers based on rate limiting requirements.
    
    Args:
        pool: Database connection pool
        user_id: The user's UUID from JWT token
        
    Returns:
        The limit key (currently user's email address)
        
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
        log.error("Database error fetching user limit key: %s", exc)
        raise UserLimitError(f"Failed to fetch user limit key: {exc}") from exc


async def check_and_increment_prompt_limit(
    pool: asyncpg.Pool,
    limit_key: str,
) -> bool:
    """
    Check if entity is within their weekly prompt limit and increment if allowed.
    
    This implements a rolling 7-day window:
    - If the current window has expired (> 7 days since window_start), reset the counter
    - If the entity has exceeded 250 prompts in the current window, return False
    - Otherwise, increment the counter and return True
    
    Args:
        pool: Database connection pool
        limit_key: The entity identifier (email, user_id, organization_id, etc.)
        
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
                    WHERE limit_key = $1 AND limit_type = $2
                    FOR UPDATE
                    """,
                    limit_key,
                    LIMIT_TYPE
                )
                
                now = datetime.now(timezone.utc)
                
                if row is None:
                    # No existing record - create one with count = 1
                    await conn.execute(
                        """
                        INSERT INTO public.user_limits (limit_key, limit_type, window_start, prompt_count)
                        VALUES ($1, $2, $3, 1)
                        """,
                        limit_key,
                        LIMIT_TYPE,
                        now
                    )
                    log.info("Created new limit record for entity %s", limit_key)
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
                        WHERE limit_key = $2 AND limit_type = $3
                        """,
                        now,
                        limit_key,
                        LIMIT_TYPE
                    )
                    log.info("Reset limit window for entity %s", limit_key)
                    return True
                
                # Check if limit exceeded
                if prompt_count >= WEEKLY_PROMPT_LIMIT:
                    log.warning(
                        "Entity %s exceeded weekly prompt limit: %d/%d",
                        limit_key,
                        prompt_count,
                        WEEKLY_PROMPT_LIMIT
                    )
                    return False
                
                # Increment counter
                await conn.execute(
                    """
                    UPDATE public.user_limits
                    SET prompt_count = prompt_count + 1
                    WHERE limit_key = $1 AND limit_type = $2
                    """,
                    limit_key,
                    LIMIT_TYPE
                )
                log.debug(
                    "Incremented prompt count for entity %s: %d/%d",
                    limit_key,
                    prompt_count + 1,
                    WEEKLY_PROMPT_LIMIT
                )
                return True
                
    except asyncpg.PostgresError as exc:
        log.error("Database error in check_and_increment_prompt_limit: %s", exc)
        raise UserLimitError(f"Failed to check/increment prompt limit: {exc}") from exc


async def get_user_prompt_usage(
    pool: asyncpg.Pool,
    limit_key: str,
) -> dict:
    """
    Get current prompt usage statistics for an entity.
    
    Args:
        pool: Database connection pool
        limit_key: The entity identifier (email, user_id, organization_id, etc.)
        
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
                WHERE limit_key = $1 AND limit_type = $2
                """,
                limit_key,
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
    1. Gets the user's limit key from their user_id (currently email)
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
        # Get user limit key (currently email, but can be extended)
        limit_key = await get_user_limit_key_from_id(pool, user_id)
        
        # Check and increment limit
        allowed = await check_and_increment_prompt_limit(pool, limit_key)
        
        if not allowed:
            # Get usage info for the error message
            usage = await get_user_prompt_usage(pool, limit_key)
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
