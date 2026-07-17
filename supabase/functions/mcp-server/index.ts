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

import { getServiceClient } from "../_shared/supabase.ts";

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
  // For now: fall back to a simple full-text search against the DB directly.
  const supabase = getServiceClient();

  let dbQuery = supabase
    .from("decisions")
    .select(`
      id,
      decision_statement,
      rationale,
      alternatives_considered,
      status,
      confidence,
      superseded_by,
      created_at,
      updated_at,
      decision_actors ( actor_id, role ),
      decision_sources ( permalink )
    `)
    .eq("tenant_id", tenant_id)  // tenant isolation — enforced server-side
    .range(offset, offset + limit - 1);

  // Apply optional filters
  if (filters?.status) dbQuery = dbQuery.eq("status", filters.status);
  if (filters?.confidence_min !== undefined) dbQuery = dbQuery.gte("confidence", filters.confidence_min);
  if (filters?.date_range?.from) dbQuery = dbQuery.gte("created_at", filters.date_range.from);
  if (filters?.date_range?.to) dbQuery = dbQuery.lte("created_at", filters.date_range.to);
  if (filters?.actor) dbQuery = dbQuery.eq("decision_actors.actor_id", filters.actor);

  // Simple keyword match against FTS index until vector search is ready
  if (query) dbQuery = dbQuery.textSearch("decision_statement", query, { type: "websearch" });

  const { data, error } = await dbQuery;
  if (error) throw new Error(`search_decisions DB error: ${error.message}`);

  return (data ?? []).map((row: any) => ({
    id: row.id,
    decision_statement: row.decision_statement,
    rationale: row.rationale ?? null,
    alternatives_considered: row.alternatives_considered ?? [],
    actors: (row.decision_actors ?? []).map((a: any) => ({ id: a.actor_id, role: a.role })),
    status: row.status,
    confidence: row.confidence,
    source_links: (row.decision_sources ?? []).map((s: any) => s.permalink),
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

  const supabase = getServiceClient();

  const { data, error } = await supabase
    .from("decisions")
    .select(`
      id,
      decision_statement,
      rationale,
      alternatives_considered,
      status,
      confidence,
      superseded_by,
      created_at,
      updated_at,
      decision_actors ( actor_id, role ),
      decision_sources ( permalink )
    `)
    .eq("id", id)
    .eq("tenant_id", tenant_id)  // tenant isolation — never skip this
    .single();

  if (error) {
    if (error.code === "PGRST116") return null; // not found
    throw new Error(`get_decision_context DB error: ${error.message}`);
  }

  return {
    id: data.id,
    decision_statement: data.decision_statement,
    rationale: data.rationale ?? null,
    alternatives_considered: data.alternatives_considered ?? [],
    actors: (data.decision_actors ?? []).map((a: any) => ({ id: a.actor_id, role: a.role })),
    status: data.status,
    confidence: data.confidence,
    superseded_by: data.superseded_by ?? null,
    source_links: (data.decision_sources ?? []).map((s: any) => s.permalink),
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
        const results = await searchDecisions(params as SearchDecisionsParams);
        return jsonOk({ results });
      }

      case "get_decision_context": {
        const record = await getDecisionContext(params as GetDecisionContextParams);
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
