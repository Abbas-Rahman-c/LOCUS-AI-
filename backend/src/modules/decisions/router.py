"""
Decisions router — protected API endpoints for reading decisions.

All routes require a valid tenant-scoped JWT via get_current_tenant().
No route is callable without authentication.
"""
from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import TenantContext, get_current_tenant
from database.pool import get_db_pool
from modules.decisions import service
from modules.decisions.schemas import (
    DecisionCreate, DecisionListResponse, DecisionOut,
    RadarCorrectionFeedback, StatusUpdate,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.get(
    "",
    response_model=DecisionListResponse,
    summary="List decisions for the authenticated tenant",
)
async def list_decisions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(get_current_tenant),
) -> DecisionListResponse:
    """Return all decisions belonging to the caller's tenant, newest first."""
    pool = get_db_pool()
    return await service.list_decisions(
        tenant_id=ctx.tenant_id,
        pool=pool,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{decision_id}",
    response_model=DecisionOut,
    summary="Get a single decision by ID",
)
async def get_decision(
    decision_id: uuid.UUID,
    ctx: TenantContext = Depends(get_current_tenant),
) -> DecisionOut:
    """
    Fetch a decision by its UUID.

    Returns 404 when the decision does not exist OR belongs to another tenant —
    the caller cannot distinguish the two cases, which prevents UUID probing.
    """
    pool = get_db_pool()
    decision = await service.get_decision(
        decision_id=decision_id,
        tenant_id=ctx.tenant_id,
        pool=pool,
    )
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    return decision


@router.post(
    "",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new decision record",
)
async def create_decision(
    body: DecisionCreate,
    ctx: TenantContext = Depends(get_current_tenant),
) -> DecisionOut:
    """Create a new decision record in the authenticated tenant's workspace."""
    pool = get_db_pool()
    try:
        return await service.create_decision(
            data=body,
            tenant_id=ctx.tenant_id,
            pool=pool,
        )
    except Exception as exc:
        log.exception("Failed to create decision")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create decision",
        ) from exc


@router.patch(
    "/{decision_id}/status",
    response_model=DecisionOut,
    summary="Update the status of a decision",
)
async def patch_decision_status(
    decision_id: uuid.UUID,
    body: StatusUpdate,
    ctx: TenantContext = Depends(get_current_tenant),
) -> DecisionOut:
    """
    Update the status of a decision (e.g. from 'proposed' to 'decided').

    Returns 404 if the decision does not exist or belongs to another tenant.
    """
    pool = get_db_pool()
    try:
        return await service.patch_decision_status(
            decision_id=decision_id,
            new_status=body.status,
            tenant_id=ctx.tenant_id,
            pool=pool,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.exception("Failed to update decision status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update decision status",
        ) from exc


@router.post(
    "/{decision_id}/supersede",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Supersede an existing decision with a new one",
)
async def supersede_decision(
    decision_id: uuid.UUID,
    body: DecisionCreate,
    ctx: TenantContext = Depends(get_current_tenant),
) -> DecisionOut:
    """
    Supersede an existing decision record with a new one.

    The old decision status is updated to 'superseded', and its `superseded_by`
    field links to the newly created decision. Neither record is deleted.

    Returns 404 if the old decision does not exist or belongs to another tenant.
    """
    pool = get_db_pool()
    try:
        return await service.supersede_decision(
            old_decision_id=decision_id,
            new_data=body,
            tenant_id=ctx.tenant_id,
            pool=pool,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.exception("Failed to supersede decision")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to supersede decision",
        ) from exc


@router.post(
    "/{decision_id}/correct",
    status_code=status.HTTP_200_OK,
    summary="Apply a Radar correction and capture it as a training signal",
)
async def correct_decision(
    decision_id: uuid.UUID,
    body: RadarCorrectionFeedback,
    ctx: TenantContext = Depends(get_current_tenant),
) -> dict:
    """
    Apply a Radar correction (confirm / edit / reject) to a decision AND
    write a permanent, queryable record of the correction to radar_corrections.

    Corrections are NEVER silently in-place. Every action produces:
    - The appropriate status/supersede change on the decision itself.
    - A radar_corrections row that captures the original statement, the action
      taken, and (for edits) what it was changed to — independently queryable
      from the decision's current state for training/evaluation purposes.

    action must be one of:
      - 'confirmed'  → marks the decision as 'decided', no content change
      - 'rejected'   → marks the decision as 'superseded', no new decision
      - 'edited'     → supersedes with corrected_statement (required for this action)
    """
    if body.action not in ("confirmed", "edited", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be one of: 'confirmed', 'edited', 'rejected'",
        )
    if body.action == "edited" and not body.corrected_statement:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="corrected_statement is required when action is 'edited'",
        )

    pool = get_db_pool()

    # Fetch the decision to capture the original state before any change
    decision = await service.get_decision(
        decision_id=decision_id,
        tenant_id=ctx.tenant_id,
        pool=pool,
    )
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")

    original_statement = decision.decision_statement
    original_status = decision.status

    # Ensure correction payload has the correct decision_id
    correction = body.model_copy(update={"decision_id": decision_id})

    try:
        if body.action == "confirmed":
            await service.patch_decision_status(
                decision_id=decision_id,
                new_status="decided",
                tenant_id=ctx.tenant_id,
                pool=pool,
            )

        elif body.action == "rejected":
            await service.patch_decision_status(
                decision_id=decision_id,
                new_status="superseded",
                tenant_id=ctx.tenant_id,
                pool=pool,
            )

        else:  # edited
            from modules.decisions.schemas import DecisionCreate
            edit_data = DecisionCreate(
                decision_statement=body.corrected_statement or "",
                rationale=decision.rationale,
                alternatives_considered=decision.alternatives_considered,
                status="decided",
                scope=decision.scope,
                confidence=decision.confidence,
            )
            await service.supersede_decision(
                old_decision_id=decision_id,
                new_data=edit_data,
                tenant_id=ctx.tenant_id,
                pool=pool,
            )

        # Always write the training signal — independent of the decision's new state
        correction_id = await service.record_radar_correction(
            correction=correction,
            original_statement=original_statement,
            original_status=original_status,
            tenant_id=ctx.tenant_id,
            pool=pool,
        )

        return {
            "status": "ok",
            "action": body.action,
            "decision_id": str(decision_id),
            "correction_id": str(correction_id),
        }

    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Failed to apply Radar correction for decision %s", decision_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply correction",
        ) from exc


@router.get(
    "/{decision_id}/corrections",
    summary="List all Radar corrections recorded for a decision",
)
async def list_corrections(
    decision_id: uuid.UUID,
    ctx: TenantContext = Depends(get_current_tenant),
) -> dict:
    """
    Return all radar_corrections records for a given decision, newest first.

    This endpoint is the authoritative source for what corrections were made
    to a decision — independently queryable from the decision's current state.
    Evaluation harnesses and training pipelines read from here.
    """
    pool = get_db_pool()
    try:
        corrections = await service.get_radar_corrections(
            decision_id=decision_id,
            tenant_id=ctx.tenant_id,
            pool=pool,
        )
        return {"decision_id": str(decision_id), "corrections": corrections, "total": len(corrections)}
    except Exception as exc:
        log.exception("Failed to fetch corrections for decision %s", decision_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch corrections",
        ) from exc
