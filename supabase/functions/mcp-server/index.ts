// supabase/functions/mcp-server/index.ts
//
// MCP (Model Context Protocol) Server — read-only MVP
// Exposes two tools for AI agents (Claude, Cursor, Windsurf, internal copilot):
//   - search_decisions(query, filters, ...) → ranked list of decisions
//   - get_decision_context(id)             → full decision record + source links
//
// Write tool (log_decision) is explicitly NOT in scope for this version.
// The write path stays fully human + pipeline controlled.
//
// BLOCKER: Real retrieval (vector + keyword search) is owned by the DS team.
// search_decisions() stubs that call with a clearly marked TODO.
// When the DS team's retrieve_decisions() function is merged, swap in the real call.
// Agreed interface (confirmed with Natnael): { query, tenant_id, filters?, limit?, offset? } → DecisionRecord[]

import { withTenant } from "../_shared/db.ts";

// ---------------------------------------------------------------------------
// Types — agreed with Natnael, grounded in migration 003_public_design_schema
// ---------------------------------------------------------------------------

interface Actor {
  id: string;
  role: "decided_by" | "mentioned";
}

interface DecisionRecord {
  id: string;
  decision_statement: string;
  rationale: string | null;
  alternatives_considered: string[];
  actors: Actor[];
  status: "proposed" | "decided" | "superseded";
  confidence: number;
  source_links: string[];
  relevance_score?: number;
}

interface DecisionContextRecord extends DecisionRecord {
  superseded_by: string | null;
  created_at: string;
  updated_at: string;
  // reconstructed_thread will be added once DS retrieval is wired in
}

// ---------------------------------------------------------------------------
// Tool: search_decisions
// ---------------------------------------------------------------------------

interface SearchDecisionsParams {
  query: string;
  tenant_id: string;
  filters?: {
    status?: "proposed" | "decided" | "superseded";
    confidence_min?: number;
    actor?: string;
    date_range?: { from: string; to: string };
  };
  limit?: number;
  offset?: number;
}

async function searchDecisions(params: SearchDecisionsParams): Promise<DecisionRecord[]> {
  const { query, tenant_id, filters, limit = 10, offset = 0 } = params;

  // BLOCKED on Natnael's Auth + Multi-Tenancy work (Phase 3).
  // Once his auth middleware is merged, tenant_id should come from the
  // verified JWT/session, not from the caller's params directly.
  if (!tenant_id) throw new Error("tenant_id is required");
  if (!query) throw new Error("query is required");

  // TODO: Replace this stub with the DS team's retrieve_decisions() once their
  // vector + keyword retrieval is built and merged (they own the retrieval layer,
  // same as they own classification and extraction).
  // Agreed call shape (confirmed with Natnael):
  //   const results = await retrieve_decisions({ query, tenant_id, filters, limit, offset })
  //   return results  // already shaped as DecisionRecord[]
  //
  // For now: fall back to a simple keyword search against the DB directly,
  // under locus_app with app.current_tenant_id set (row-level security).
  const rows = await withTenant(tenant_id, async (sql) => {
    // Build optional filter fragments
    const status = filters?.status ?? null;
    const confidenceMin = filters?.confidence_min ?? null;
    const dateFrom = filters?.date_range?.from ?? null;
    const dateTo = filters?.date_range?.to ?? null;

    return await sql`
      select
        d.id,
        d.decision_statement,
        d.rationale,
        d.alternatives_considered,
        d.status,
        d.confidence,
        d.superseded_by,
        d.created_at,
        d.updated_at,
        coalesce(
          (
            select json_agg(json_build_object('actor_id', da.actor_id, 'role', da.role))
            from public.decision_actors da
            where da.decision_id = d.id and da.tenant_id = d.tenant_id
          ),
          '[]'::json
        ) as decision_actors,
        coalesce(
          (
            select json_agg(json_build_object('permalink', ds.permalink))
            from public.decision_sources ds
            where ds.decision_id = d.id and ds.tenant_id = d.tenant_id
          ),
          '[]'::json
        ) as decision_sources
      from public.decisions d
      where d.tenant_id = ${tenant_id}::uuid
        and (${status}::text is null or d.status = ${status})
        and (${confidenceMin}::float8 is null or d.confidence >= ${confidenceMin})
        and (${dateFrom}::timestamptz is null or d.created_at >= ${dateFrom}::timestamptz)
        and (${dateTo}::timestamptz is null or d.created_at <= ${dateTo}::timestamptz)
        and (
          ${query}::text = ''
          or d.decision_statement ilike '%' || ${query} || '%'
        )
      order by d.created_at desc
      limit ${limit}
      offset ${offset}
    `;
  });

  return rows.map((row) => ({
    id: row.id,
    decision_statement: row.decision_statement,
    rationale: row.rationale ?? null,
    alternatives_considered: row.alternatives_considered ?? [],
    actors: (row.decision_actors ?? []).map((a: { actor_id: string; role: string }) => ({
      id: a.actor_id,
      role: a.role,
    })),
    status: row.status,
    confidence: row.confidence,
    source_links: (row.decision_sources ?? [])
      .map((s: { permalink: string | null }) => s.permalink)
      .filter(Boolean),
  }));
}

// ---------------------------------------------------------------------------
// Tool: get_decision_context
// ---------------------------------------------------------------------------

interface GetDecisionContextParams {
  id: string;
  tenant_id: string;
}

async function getDecisionContext(params: GetDecisionContextParams): Promise<DecisionContextRecord | null> {
  const { id, tenant_id } = params;

  if (!tenant_id) throw new Error("tenant_id is required");
  if (!id) throw new Error("id is required");

  const data = await withTenant(tenant_id, async (sql) => {
    const rows = await sql`
      select
        d.id,
        d.decision_statement,
        d.rationale,
        d.alternatives_considered,
        d.status,
        d.confidence,
        d.superseded_by,
        d.created_at,
        d.updated_at,
        coalesce(
          (
            select json_agg(json_build_object('actor_id', da.actor_id, 'role', da.role))
            from public.decision_actors da
            where da.decision_id = d.id and da.tenant_id = d.tenant_id
          ),
          '[]'::json
        ) as decision_actors,
        coalesce(
          (
            select json_agg(json_build_object('permalink', ds.permalink))
            from public.decision_sources ds
            where ds.decision_id = d.id and ds.tenant_id = d.tenant_id
          ),
          '[]'::json
        ) as decision_sources
      from public.decisions d
      where d.id = ${id}::uuid
        and d.tenant_id = ${tenant_id}::uuid
      limit 1
    `;
    return rows[0] ?? null;
  });

  if (!data) return null;

  return {
    id: data.id,
    decision_statement: data.decision_statement,
    rationale: data.rationale ?? null,
    alternatives_considered: data.alternatives_considered ?? [],
    actors: (data.decision_actors ?? []).map((a: { actor_id: string; role: string }) => ({
      id: a.actor_id,
      role: a.role,
    })),
    status: data.status,
    confidence: data.confidence,
    superseded_by: data.superseded_by ?? null,
    source_links: (data.decision_sources ?? [])
      .map((s: { permalink: string | null }) => s.permalink)
      .filter(Boolean),
    created_at: data.created_at,
    updated_at: data.updated_at,
  };
}

// ---------------------------------------------------------------------------
// MCP JSON-RPC dispatcher
// ---------------------------------------------------------------------------

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  let body: { method: string; params: Record<string, unknown> };
  try {
    body = await req.json();
  } catch {
    return jsonError("Invalid JSON body", 400);
  }

  const { method, params } = body;

  try {
    switch (method) {
      case "search_decisions": {
        const results = await searchDecisions(params as unknown as SearchDecisionsParams);
        return jsonOk({ results });
      }

      case "get_decision_context": {
        const record = await getDecisionContext(params as unknown as GetDecisionContextParams);
        if (!record) return jsonError("Decision not found", 404);
        return jsonOk(record);
      }

      default:
        return jsonError(`Unknown method: ${method}. Available: search_decisions, get_decision_context`, 400);
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal error";
    console.error(`[mcp-server] ${method} error:`, message);
    return jsonError(message, 500);
  }
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function jsonOk(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function jsonError(message: string, status: number): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
