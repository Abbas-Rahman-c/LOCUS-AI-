"""
Digest Router — GET /digest returns the weekly Team Pulse or personal digest.

?scope=personal  → "Your Week in Decisions" (default)
?scope=team      → "Team Pulse" (team-wide)

Uses the same mandatory Depends(get_current_tenant) every other protected
route uses — tenant_id is taken exclusively from the authenticated
TenantContext, never from query params or request body.

permission_scopes are resolved server-side from the TenantContext via
resolve_permission_scopes(), exactly as /search does — never accepted from
the caller.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import TenantContext, get_current_tenant
from common.config.voyage_config import VoyageConfigError
from database.pool import get_db_pool
from modules.ai.embeddings.provider import VoyageEmbeddingError, VoyageResponseValidationError
from modules.answering.provider import AnswerAPIError, AnswerResponseValidationError
from modules.digest.schemas import DigestResponse
from modules.digest.service import generate_team_pulse
from modules.permissions.scope_resolver import resolve_permission_scopes
from modules.ratelimit.limiter import enforce_rate_limit

log = logging.getLogger(__name__)

router = APIRouter(tags=["digest"])


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    scope: Literal["personal", "team"] = Query(
        default="personal",
        description="'personal' for Your Week in Decisions, 'team' for Team Pulse",
    ),
    ctx: TenantContext = Depends(get_current_tenant),
    _: None = Depends(enforce_rate_limit("digest")),
) -> DigestResponse:
    """Return the weekly digest for the authenticated tenant member.

    scope=personal → decisions the caller was involved in this week.
    scope=team     → all team decisions from the past 7 days.
    """
    pool = get_db_pool()
    permission_scopes = resolve_permission_scopes(ctx)
    try:
        return await generate_team_pulse(
            pool,
            ctx.tenant_id,
            permission_scopes,
            scope,
        )
    except VoyageConfigError as exc:
        log.error("Voyage configuration error during /digest: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voyage configuration error",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except (VoyageEmbeddingError, VoyageResponseValidationError) as exc:
        log.error("Query embedding failure during /digest: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Query embedding failed"
        ) from exc
    except (AnswerAPIError, AnswerResponseValidationError) as exc:
        log.error("Claude answer failure during /digest: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Digest generation failed"
        ) from exc