"""
AI pipeline decision persistence — atomically writes one decision, its
decision_sources row, and its decision_actors rows from a single validated
ExtractionResult.

This is a separate write path from modules.decisions.service (the public
CRUD API): the AI pipeline never calls create_decision()/supersede_decision()
and this module never exposes a router. The two paths share the same table,
schema conventions, and dual-layer tenant isolation (tenant_conn for RLS,
assert_tenant_scope() as the Layer 2 re-check), but persist_decision_from_
extraction() additionally writes decision_sources and decision_actors in the
same transaction, which the public CRUD path does not do.

permission_scope is copied verbatim from the triggering EventEnvelope -
empty means workspace-wide (see modules.ingestion.envelope.schemas.
EventEnvelope.permission_scope's field description and modules.permissions.
repository's evidence trail); this module never substitutes a default that
would change that meaning.

Idempotency: origin_raw_event_id is checked before inserting. If a decision
already exists for (tenant_id, origin_raw_event_id), its id is returned
without inserting a second decision, source, or actor row. public.decisions
has no UNIQUE constraint on origin_raw_event_id (only the FK to raw_events),
so this check-then-insert is a best-effort guard against a retried pipeline
run creating a duplicate decision, not a database-enforced one - the same
"fast check first, tolerate a residual race" shape already used by
modules.ingestion.dedup.ledger for raw_events. A genuine concurrent race
(two workers persisting the same raw_event_id at the same instant) could
still produce two decisions; closing that gap would need a real UNIQUE
constraint, which is a schema change out of scope here.
"""
from __future__ import annotations

import logging
import uuid

import asyncpg

from database.tenant_connection import tenant_conn
from modules.ai.extraction.schemas import ActorRole, ExtractionResult
from modules.ingestion.envelope.schemas import EventEnvelope
from modules.security.tenant_guard import assert_tenant_scope

log = logging.getLogger(__name__)

# actors.<column> to resolve an extraction's source_actor_id against, keyed
# by the triggering event's source. Mirrors public.actors' provider-native
# identifier columns (email, slack_user_id, notion_user_id).
_ACTOR_IDENTIFIER_COLUMN_BY_SOURCE: dict[str, str] = {
    "gmail": "email",
    "slack": "slack_user_id",
    "notion": "notion_user_id",
}


class PipelinePersistenceError(Exception):
    """Base class for all persist_decision_from_extraction() failures."""


class UnsupportedActorSourceError(PipelinePersistenceError):
    """event.source has no known actors identifier column to resolve against."""


class ActorResolutionError(PipelinePersistenceError):
    """Failed to find or create an actors row for a referenced actor."""


class DecisionPersistenceError(PipelinePersistenceError):
    """The decision/source/actor writes failed at the database level."""


async def _resolve_actor_id(
    conn: asyncpg.Connection,
    tenant_id: uuid.UUID,
    source: str,
    source_actor_id: str,
) -> uuid.UUID:
    """Find or create the actors row referenced by one ActorReference.

    public.actors only has a UNIQUE constraint on (tenant_id, email), so
    email-sourced lookups use a real upsert; slack_user_id/notion_user_id
    fall back to select-then-insert (no unique constraint to upsert
    against) - see this module's docstring for the accepted residual race.
    """
    try:
        column = _ACTOR_IDENTIFIER_COLUMN_BY_SOURCE[source]
    except KeyError as exc:
        raise UnsupportedActorSourceError(f"No actor identifier column for source={source!r}") from exc

    try:
        if column == "email":
            row = await conn.fetchrow(
                f"""
                INSERT INTO actors (tenant_id, email, kind)
                VALUES ($1, $2, 'internal')
                ON CONFLICT (tenant_id, email) DO UPDATE SET email = EXCLUDED.email
                RETURNING id
                """,
                tenant_id,
                source_actor_id,
            )
            return row["id"]

        existing = await conn.fetchrow(
            f"SELECT id FROM actors WHERE tenant_id = $1 AND {column} = $2",
            tenant_id,
            source_actor_id,
        )
        if existing is not None:
            return existing["id"]

        created = await conn.fetchrow(
            f"""
            INSERT INTO actors (tenant_id, {column}, kind)
            VALUES ($1, $2, 'internal')
            RETURNING id
            """,
            tenant_id,
            source_actor_id,
        )
        return created["id"]
    except asyncpg.PostgresError as exc:
        raise ActorResolutionError(
            f"Failed to resolve actor source={source!r} source_actor_id={source_actor_id!r}: {exc}"
        ) from exc


async def persist_decision_from_extraction(
    pool: asyncpg.Pool,
    tenant_id: uuid.UUID | str,
    event: EventEnvelope,
    extraction: ExtractionResult,
    origin_raw_event_id: uuid.UUID,
    source_permalink: str | None = None,
    scope: str = "team",
    scope_actor_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Atomically persist one decision, its source, and its actors.

    Runs entirely inside tenant_conn(pool, tenant_id) - one transaction, one
    RLS-scoped connection. Returns the decision's id (a pre-existing one if
    origin_raw_event_id already has a decision - see module docstring).
    Raises DecisionPersistenceError on any database failure, or
    ActorResolutionError/UnsupportedActorSourceError if an extracted actor
    can't be resolved to an actors row - either way the whole transaction
    rolls back, so no partial decision/source/actor state is ever left
    behind.
    """
    tenant_uuid = uuid.UUID(str(tenant_id))

    try:
        async with tenant_conn(pool, tenant_uuid) as conn:
            existing = await conn.fetchrow(
                "SELECT id, tenant_id FROM decisions WHERE tenant_id = $1 AND origin_raw_event_id = $2",
                tenant_uuid,
                origin_raw_event_id,
            )
            if existing is not None:
                assert_tenant_scope(existing["tenant_id"], tenant_uuid)
                log.info(
                    "Decision already persisted for origin_raw_event_id=%s - returning existing decision_id=%s",
                    origin_raw_event_id, existing["id"],
                )
                return existing["id"]

            decision_row = await conn.fetchrow(
                """
                INSERT INTO decisions (
                    tenant_id, record_type, decision_statement, rationale,
                    alternatives_considered, status, scope, scope_actor_id,
                    confidence, permission_scope, origin_raw_event_id
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
                ) RETURNING id, tenant_id
                """,
                tenant_uuid,
                extraction.record_type.value,
                extraction.decision_statement,
                extraction.rationale,
                extraction.alternatives_considered,
                extraction.status.value,
                scope,
                scope_actor_id,
                extraction.confidence,
                list(event.permission_scope),
                origin_raw_event_id,
            )
            assert_tenant_scope(decision_row["tenant_id"], tenant_uuid)
            decision_id = decision_row["id"]

            if source_permalink:
                await conn.execute(
                    """
                    INSERT INTO decision_sources (tenant_id, decision_id, raw_event_id, permalink)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (decision_id, permalink) DO NOTHING
                    """,
                    tenant_uuid,
                    decision_id,
                    origin_raw_event_id,
                    source_permalink,
                )

            for actor_ref in extraction.actors:
                actor_id = await _resolve_actor_id(
                    conn, tenant_uuid, event.source, actor_ref.source_actor_id
                )
                await conn.execute(
                    """
                    INSERT INTO decision_actors (tenant_id, decision_id, actor_id, role)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (decision_id, actor_id, role) DO NOTHING
                    """,
                    tenant_uuid,
                    decision_id,
                    actor_id,
                    actor_ref.role.value if isinstance(actor_ref.role, ActorRole) else actor_ref.role,
                )
    except asyncpg.PostgresError as exc:
        raise DecisionPersistenceError(f"Failed to persist decision: {exc}") from exc

    log.info(
        "Persisted decision id=%s tenant=%s origin_raw_event_id=%s actor_count=%d",
        decision_id, tenant_uuid, origin_raw_event_id, len(extraction.actors),
    )
    return decision_id
