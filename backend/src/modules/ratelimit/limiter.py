"""
Per-tenant rate limiting for endpoints that call Claude and/or Voyage.

MVP scope: an in-memory, fixed-window counter per (tenant_id, route). This
is a real, deliberate tradeoff, not an oversight - it does NOT coordinate
across multiple backend instances, so if this app ever runs as more than
one process, each process enforces its own independent limit rather than
a shared one. That's an acceptable gap for the current single-instance
deployment and is far better than no limit at all; moving to a shared
Postgres- or Redis-backed counter is the natural next step if/when the
backend is ever scaled horizontally.

Exists specifically because of a real incident: a shared Anthropic account
hit its monthly usage cap from testing volume stacking up across the team,
with no application-level guard in place to catch it early. This doesn't
replace watching the Anthropic/Voyage dashboards - it's a cheap, immediate
backstop against one tenant (or one runaway test loop) accidentally
consuming a disproportionate share of a shared budget.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status

from app.dependencies import TenantContext, get_current_tenant


@dataclass
class _Window:
    count: int = 0
    window_start: float = field(default_factory=time.monotonic)


class RateLimiter:
    """Fixed-window limiter, keyed per (tenant_id, route_name)."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[tuple[str, str], _Window] = defaultdict(_Window)

    def check(self, tenant_id: str, route_name: str) -> tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds).

        Resets the window automatically once window_seconds has elapsed
        since it started, rather than requiring an external reset call.
        """
        key = (tenant_id, route_name)
        window = self._windows[key]
        now = time.monotonic()
        elapsed = now - window.window_start

        if elapsed >= self.window_seconds:
            window.count = 0
            window.window_start = now
            elapsed = 0.0

        if window.count >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - elapsed))
            return False, retry_after

        window.count += 1
        return True, 0


# One shared limiter for every Claude/Voyage-calling route. 20 requests per
# tenant per 5-minute window is intentionally generous for real usage while
# still catching a runaway loop or misbehaving script quickly - tune via
# the constructor args below once real usage patterns are known, not before.
_expensive_route_limiter = RateLimiter(max_requests=20, window_seconds=300)


def enforce_rate_limit(route_name: str):
    """
    FastAPI dependency factory. Usage - add as an extra Depends() alongside
    the existing get_current_tenant on any Claude/Voyage-calling route:

        @router.post("/search")
        async def search_endpoint(
            request: SearchRequest,
            ctx: TenantContext = Depends(get_current_tenant),
            _: None = Depends(enforce_rate_limit("search")),
        ):
            ...

    Depends directly on get_current_tenant (not request.state - that
    dependency never sets anything there, it just returns TenantContext),
    so this only ever runs for a genuinely authenticated caller and is
    correctly scoped per real tenant_id, never a global limit.
    """

    async def _dependency(
        ctx: TenantContext = Depends(get_current_tenant),
    ) -> None:
        allowed, retry_after = _expensive_route_limiter.check(ctx.tenant_id, route_name)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded for this endpoint. "
                    f"Try again in {retry_after} seconds."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    return _dependency