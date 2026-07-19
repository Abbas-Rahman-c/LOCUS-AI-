"""
Retrieval service — retrieval + synthesis pipeline with dual-layer tenant isolation.
"""
from __future__ import annotations

import json
import logging
import uuid
import os
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Any

import asyncpg
from anthropic import AsyncAnthropic

from database.tenant_connection import tenant_conn
from modules.security.tenant_guard import assert_tenant_scope
from modules.security.encryption import decrypt_raw_content

log = logging.getLogger(__name__)

APPROVED_MODELS = {
    "claude-haiku-4-5-20251001",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
}


def get_synthesis_model() -> str:
    """Validate and return the synthesis model configuration."""
    model = os.environ.get("ANTHROPIC_SYNTHESIS_MODEL", "claude-haiku-4-5-20251001")
    if model not in APPROVED_MODELS:
        raise RuntimeError(
            f"ANTHROPIC_SYNTHESIS_MODEL '{model}' is not in approved list: {sorted(APPROVED_MODELS)}"
        )
    return model


def get_anthropic_client() -> AsyncAnthropic:
    """Initialize and return the Anthropic client, failing loudly if API key is missing."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or api_key.strip() == "":
        raise RuntimeError("ANTHROPIC_API_KEY is not set; refusing to run with a fake key")
    return AsyncAnthropic(api_key=api_key)


def extract_event_text(raw_content: dict, source: str) -> str:
    """Helper to extract clean text from raw event payloads."""
    if not isinstance(raw_content, dict):
        return str(raw_content)
    if source == "gmail":
        subject = raw_content.get("subject", "")
        body = raw_content.get("body", "")
        if subject:
            return f"Subject: {subject}\n{body}"
        return body

    # Fallback to check common content fields:
    for field in ["text", "body", "content", "message", "description", "snippet"]:
        val = raw_content.get(field)
        if val and isinstance(val, str):
            return val

    # If no string field found, fallback to json string representation
    return json.dumps(raw_content)


async def retrieve_decisions(
    query: str,
    tenant_id: uuid.UUID | str,
    filters: dict | None = None,
    limit: int = 10,
    offset: int = 0,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    """
    Search and retrieve decisions scoped to tenant_id with filtering and pagination.
    
    Output shape matches the agreed interface exactly:
    - id
    - decision_statement
    - rationale
    - alternatives_considered
    - actors: { id, role }[]
    - status
    - confidence
    - source_links: string[]
    - relevance_score
    """
    if pool is None:
        from database.pool import get_db_pool
        pool = get_db_pool()

    tenant_uuid = uuid.UUID(str(tenant_id))
    params: list[Any] = [tenant_uuid]
    where_clauses = ["tenant_id = $1"]

    if filters:
        if filters.get("status"):
            params.append(filters["status"])
            where_clauses.append(f"status = ${len(params)}")

        if filters.get("confidence_min") is not None:
            params.append(float(filters["confidence_min"]))
            where_clauses.append(f"confidence >= ${len(params)}")

        if filters.get("actor"):
            params.append(uuid.UUID(str(filters["actor"])))
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM decision_actors da WHERE da.decision_id = decisions.id AND da.tenant_id = decisions.tenant_id AND da.actor_id = ${len(params)})"
            )

        if filters.get("date_range"):
            dr = filters["date_range"]
            start_date = dr.get("start") or dr.get("start_date")
            end_date = dr.get("end") or dr.get("end_date")

            if start_date:
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                params.append(start_date)
                where_clauses.append(f"created_at >= ${len(params)}")

            if end_date:
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                params.append(end_date)
                where_clauses.append(f"created_at <= ${len(params)}")

    query_str = query.strip()
    if query_str:
        params.append(query_str)
        fts_param_idx = len(params)
        where_clauses.append(
            f"to_tsvector('english', decision_statement || ' ' || COALESCE(rationale, '')) @@ plainto_tsquery('english', ${fts_param_idx})"
        )
        select_fields = f"""
            id, tenant_id, decision_statement, rationale, alternatives_considered, status, confidence, created_at, updated_at,
            ts_rank(
                to_tsvector('english', decision_statement || ' ' || COALESCE(rationale, '')),
                plainto_tsquery('english', ${fts_param_idx})
            ) AS relevance_score
        """
        order_by = "relevance_score DESC, created_at DESC"
    else:
        select_fields = """
            id, tenant_id, decision_statement, rationale, alternatives_considered, status, confidence, created_at, updated_at,
            NULL::float AS relevance_score
        """
        order_by = "created_at DESC"

    params.append(limit)
    limit_idx = len(params)
    params.append(offset)
    offset_idx = len(params)

    sql = f"""
        SELECT {select_fields}
        FROM decisions
        WHERE {" AND ".join(where_clauses)}
        ORDER BY {order_by}
        LIMIT ${limit_idx} OFFSET ${offset_idx}
    """

    async with tenant_conn(pool, tenant_uuid) as conn:
        rows = await conn.fetch(sql, *params)

        decision_ids = [r["id"] for r in rows]
        actors_by_decision = {}
        sources_by_decision = {}

        if decision_ids:
            # Query decision actors
            actor_rows = await conn.fetch(
                """
                SELECT tenant_id, decision_id, actor_id, role
                FROM decision_actors
                WHERE decision_id = ANY($1) AND tenant_id = $2
                """,
                decision_ids,
                tenant_uuid,
            )
            for ar in actor_rows:
                assert_tenant_scope(ar["tenant_id"], tenant_uuid)
                dec_id = ar["decision_id"]
                if dec_id not in actors_by_decision:
                    actors_by_decision[dec_id] = []
                actors_by_decision[dec_id].append({
                    "id": str(ar["actor_id"]),
                    "role": ar["role"]
                })

            # Query decision sources
            source_rows = await conn.fetch(
                """
                SELECT tenant_id, decision_id, permalink
                FROM decision_sources
                WHERE decision_id = ANY($1) AND tenant_id = $2
                """,
                decision_ids,
                tenant_uuid,
            )
            for sr in source_rows:
                assert_tenant_scope(sr["tenant_id"], tenant_uuid)
                dec_id = sr["decision_id"]
                if dec_id not in sources_by_decision:
                    sources_by_decision[dec_id] = []
                sources_by_decision[dec_id].append(sr["permalink"])

    results = []
    for r in rows:
        assert_tenant_scope(r["tenant_id"], tenant_uuid)
        dec_id = r["id"]
        results.append({
            "id": str(dec_id),
            "decision_statement": r["decision_statement"],
            "rationale": r["rationale"],
            "alternatives_considered": list(r["alternatives_considered"]) if r["alternatives_considered"] is not None else [],
            "actors": actors_by_decision.get(dec_id, []),
            "status": r["status"],
            "confidence": float(r["confidence"]),
            "source_links": sources_by_decision.get(dec_id, []),
            "relevance_score": float(r["relevance_score"]) if r["relevance_score"] is not None else None
        })

    return results


async def get_decision_context(
    decision_id: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    pool: asyncpg.Pool,
) -> dict | None:
    """
    Lookup a decision by ID and reconstruct its conversation context/thread.
    
    Returns the full decision record + `thread_context`.
    """
    dec_uuid = uuid.UUID(str(decision_id))
    tenant_uuid = uuid.UUID(str(tenant_id))

    async with tenant_conn(pool, tenant_uuid) as conn:
        row = await conn.fetchrow(
            """
            SELECT id, tenant_id, decision_statement, rationale, alternatives_considered,
                   status, confidence, origin_raw_event_id, created_at, updated_at
            FROM decisions
            WHERE id = $1 AND tenant_id = $2
            """,
            dec_uuid,
            tenant_uuid,
        )
        if row is None:
            return None

        assert_tenant_scope(row["tenant_id"], tenant_uuid)

        # Fetch actors
        actor_rows = await conn.fetch(
            """
            SELECT tenant_id, actor_id, role
            FROM decision_actors
            WHERE decision_id = $1 AND tenant_id = $2
            """,
            dec_uuid,
            tenant_uuid,
        )
        actors = []
        for ar in actor_rows:
            assert_tenant_scope(ar["tenant_id"], tenant_uuid)
            actors.append({
                "id": str(ar["actor_id"]),
                "role": ar["role"]
            })

        # Fetch sources
        source_rows = await conn.fetch(
            """
            SELECT tenant_id, raw_event_id, permalink
            FROM decision_sources
            WHERE decision_id = $1 AND tenant_id = $2
            """,
            dec_uuid,
            tenant_uuid,
        )
        sources = []
        raw_event_ids = []
        if row["origin_raw_event_id"]:
            raw_event_ids.append(row["origin_raw_event_id"])

        for sr in source_rows:
            assert_tenant_scope(sr["tenant_id"], tenant_uuid)
            sources.append(sr["permalink"])
            if sr["raw_event_id"]:
                raw_event_ids.append(sr["raw_event_id"])

        thread_context = ""
        if raw_event_ids:
            # Try thread ref lookup
            thread_ref_rows = await conn.fetch(
                """
                SELECT DISTINCT thread_ref
                FROM raw_events
                WHERE id = ANY($1) AND tenant_id = $2 AND thread_ref IS NOT NULL
                """,
                raw_event_ids,
                tenant_uuid,
            )
            thread_refs = [tr["thread_ref"] for tr in thread_ref_rows]

            if thread_refs:
                thread_event_rows = await conn.fetch(
                    """
                    SELECT tenant_id, id, source, actor, received_at, raw_content
                    FROM raw_events
                    WHERE thread_ref = ANY($1) AND tenant_id = $2
                    ORDER BY received_at ASC
                    """,
                    thread_refs,
                    tenant_uuid,
                )
                events_list = []
                for er in thread_event_rows:
                    assert_tenant_scope(er["tenant_id"], tenant_uuid)
                    try:
                        raw_bytes = bytes(er["raw_content"])
                        plaintext = decrypt_raw_content(raw_bytes).decode("utf-8")
                        envelope_content = json.loads(plaintext)

                        raw_payload = envelope_content.get("raw_content", {})
                        body_text = extract_event_text(raw_payload, er["source"])
                        events_list.append(
                            f"[{er['received_at'].isoformat()}] {er['actor']} ({er['source']}): {body_text}"
                        )
                    except Exception as e:
                        log.warning("Failed to decrypt or parse event %s: %s", er["id"], e)
                if events_list:
                    thread_context = "\n".join(events_list)

        if raw_event_ids and not thread_context:
            # Fallback to linked events directly
            event_rows = await conn.fetch(
                """
                SELECT tenant_id, id, source, actor, received_at, raw_content
                FROM raw_events
                WHERE id = ANY($1) AND tenant_id = $2
                ORDER BY received_at ASC
                """,
                raw_event_ids,
                tenant_uuid,
            )
            events_list = []
            for er in event_rows:
                assert_tenant_scope(er["tenant_id"], tenant_uuid)
                try:
                    raw_bytes = bytes(er["raw_content"])
                    plaintext = decrypt_raw_content(raw_bytes).decode("utf-8")
                    envelope_content = json.loads(plaintext)

                    raw_payload = envelope_content.get("raw_content", {})
                    body_text = extract_event_text(raw_payload, er["source"])
                    events_list.append(
                        f"[{er['received_at'].isoformat()}] {er['actor']} ({er['source']}): {body_text}"
                    )
                except Exception as e:
                    log.warning("Failed to decrypt or parse event %s: %s", er["id"], e)
            if events_list:
                thread_context = "\n".join(events_list)

    return {
        "id": str(row["id"]),
        "decision_statement": row["decision_statement"],
        "rationale": row["rationale"],
        "alternatives_considered": list(row["alternatives_considered"]) if row["alternatives_considered"] is not None else [],
        "actors": actors,
        "status": row["status"],
        "confidence": float(row["confidence"]),
        "source_links": sources,
        "relevance_score": None,
        "thread_context": thread_context
    }


async def synthesize_answer(
    query: str,
    retrieved_decisions: List[Dict[str, Any]],
) -> AsyncGenerator[str, None]:
    """
    Streams a cited answer based strictly on retrieved decisions.
    
    Ensures safe initialization, whitelisted model validation, and sanitized errors.
    """
    if not retrieved_decisions:
        yield json.dumps({"type": "message", "content": "I couldn't find any relevant decisions to answer your question."}) + "\n"
        return

    try:
        client = get_anthropic_client()
        model = get_synthesis_model()
    except Exception as e:
        log.exception("Initialization of Anthropic client failed")
        yield json.dumps({"type": "error", "content": "Configuration error: Synthesis service is currently unavailable."}) + "\n"
        return

    context = ""
    for i, dec in enumerate(retrieved_decisions):
        context += f"[Decision {i+1}]: {dec.get('decision_statement')}\n"
        context += f"Rationale: {dec.get('rationale') or 'N/A'}\n"
        context += f"Source ID: {dec.get('id')}\n"
        if dec.get("source_links"):
            context += f"Source Links: {', '.join(dec.get('source_links'))}\n"
        if dec.get("actors"):
            actor_strs = [f"{a['id']} ({a['role']})" for a in dec["actors"]]
            context += f"Actors: {', '.join(actor_strs)}\n"
        context += "\n"

    system_prompt = (
        "You are an expert answering questions strictly grounded in retrieved decisions. "
        "You must cite the decisions you use using the format [Decision X]. "
        "If the retrieved decisions do not contain the answer, decline explicitly and never guess. "
        "Do not use external knowledge."
    )

    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    try:
        stream = await client.messages.create(
            max_tokens=1024,
            messages=[{"role": "user", "content": user_prompt}],
            model=model,
            system=system_prompt,
            stream=True,
        )

        async for event in stream:
            if event.type == "content_block_delta":
                text = getattr(event.delta, "text", None)
                if text is not None:
                    yield json.dumps({"type": "content", "content": text}) + "\n"

    except Exception as e:
        log.exception("Error during answer synthesis streaming")
        yield json.dumps({"type": "error", "content": "An error occurred while generating the answer. Please try again later."}) + "\n"
