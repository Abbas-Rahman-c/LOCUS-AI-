// supabase/functions/_shared/memory/loadMemories.ts
//
// Assembles real CanonicalMemoryObject rows from the join tables
// (memory_entities, memory_source_events + memory_fixture_events,
// memory_citations) - the one place entities[]/source_events[]/citations[]
// get turned back into the JSON shape, matching this codebase's existing
// decision_actors/decision_sources precedent (join tables in Postgres,
// assembled at read time, never raw arrays in the column itself).

import type { CanonicalMemoryObject, EntityRef, SourceEventRef, Citation } from "./types.ts";
import { computeFreshness } from "./freshness.ts";

// deno-lint-ignore no-explicit-any
export async function loadMemoriesForTenant(sql: any, tenantId: string, entityId?: string): Promise<CanonicalMemoryObject[]> {
  const memoryRows = entityId
    ? await sql`
        select distinct m.* from public.memories m
        join public.memory_entities me on me.memory_id = m.memory_id
        where m.tenant_id = ${tenantId} and me.entity_id = ${entityId}
        order by m.valid_from desc
      `
    : await sql`select * from public.memories where tenant_id = ${tenantId} order by valid_from desc`;

  if (memoryRows.length === 0) return [];
  const memoryIds = memoryRows.map((r: { memory_id: string }) => r.memory_id);

  const entityRows = await sql`
    select me.memory_id, e.entity_id, e.entity_type, e.canonical_name
    from public.memory_entities me
    join public.entities e on e.entity_id = me.entity_id
    where me.memory_id = any(${memoryIds})
  `;
  const sourceRows = await sql`
    select mse.memory_id, mfe.id as event_id, mfe.source, mfe.source_id, mfe.permission_scope
    from public.memory_source_events mse
    join public.memory_fixture_events mfe on mfe.id = mse.fixture_event_id
    where mse.memory_id = any(${memoryIds})
  `;
  const citationRows = await sql`
    select mc.memory_id, mfe.id as event_id, mfe.source, mfe.source_id, mc.excerpt_ref
    from public.memory_citations mc
    join public.memory_fixture_events mfe on mfe.id = mc.fixture_event_id
    where mc.memory_id = any(${memoryIds})
  `;
  // memory_conflicts only ever stores the 'conflict' relationship (see
  // reconcile.ts), one directed row per pair (memory_id = the newer side,
  // related_memory_id = the candidate it conflicted with). A memory can be
  // on either side depending on which one triggered the check, so this has
  // to match on both columns to find every unresolved memory's sibling.
  const conflictRows = await sql`
    select memory_id, related_memory_id from public.memory_conflicts
    where tenant_id = ${tenantId} and (memory_id = any(${memoryIds}) or related_memory_id = any(${memoryIds}))
  `;

  const entitiesByMemory = new Map<string, EntityRef[]>();
  for (const r of entityRows) {
    const list = entitiesByMemory.get(r.memory_id) ?? [];
    list.push({ entity_id: r.entity_id, entity_type: r.entity_type, canonical_name: r.canonical_name });
    entitiesByMemory.set(r.memory_id, list);
  }
  const sourcesByMemory = new Map<string, SourceEventRef[]>();
  // Union of every source event's permission_scope - a memory is visible to
  // anyone who could see ANY of the events it was built from, same
  // least-restrictive convention resolvePermissionScopes already uses for a
  // multi-source decision. An empty union (all source events unscoped, or
  // no source events with a real scope) means workspace-wide, matching
  // isMemoryAccessible's own "empty = granted" rule.
  const scopesByMemory = new Map<string, Set<string>>();
  for (const r of sourceRows) {
    const list = sourcesByMemory.get(r.memory_id) ?? [];
    list.push({ event_id: r.event_id, source: r.source, source_id: r.source_id, url: null });
    sourcesByMemory.set(r.memory_id, list);

    const scopes = scopesByMemory.get(r.memory_id) ?? new Set<string>();
    for (const s of (r.permission_scope as string[] | null) ?? []) scopes.add(s);
    scopesByMemory.set(r.memory_id, scopes);
  }
  const citationsByMemory = new Map<string, Citation[]>();
  for (const r of citationRows) {
    const list = citationsByMemory.get(r.memory_id) ?? [];
    list.push({
      source_event: { event_id: r.event_id, source: r.source, source_id: r.source_id, url: null },
      excerpt_ref: r.excerpt_ref,
    });
    citationsByMemory.set(r.memory_id, list);
  }

  const siblingByMemory = new Map<string, string>();
  for (const r of conflictRows) {
    siblingByMemory.set(r.memory_id, r.related_memory_id);
    siblingByMemory.set(r.related_memory_id, r.memory_id);
  }

  const now = new Date();
  return memoryRows.map((row: Record<string, unknown>): CanonicalMemoryObject => ({
    memory_id: row.memory_id as string,
    organization_id: row.tenant_id as string,
    type: row.type as CanonicalMemoryObject["type"],
    title: row.title as string,
    summary: row.summary as string,
    payload: (row.payload as Record<string, unknown>) ?? {},
    entities: entitiesByMemory.get(row.memory_id as string) ?? [],
    occurred_at: new Date(row.occurred_at as string).toISOString(),
    valid_from: new Date(row.valid_from as string).toISOString(),
    valid_until: row.valid_until ? new Date(row.valid_until as string).toISOString() : null,
    observed_at: new Date(row.observed_at as string).toISOString(),
    source_events: sourcesByMemory.get(row.memory_id as string) ?? [],
    citations: citationsByMemory.get(row.memory_id as string) ?? [],
    confidence: Number(row.confidence),
    freshness: computeFreshness(
      row.type as CanonicalMemoryObject["type"],
      row.valid_from as string,
      row.observed_at as string,
      now,
    ),
    authority: row.authority !== null ? Number(row.authority) : null,
    status: row.status as CanonicalMemoryObject["status"],
    supersedes: (row.supersedes as string | null) ?? null,
    contradicted_by: siblingByMemory.get(row.memory_id as string) ?? null,
    permissions: {
      inherited_from: sourcesByMemory.get(row.memory_id as string) ?? [],
      visible_to: Array.from(scopesByMemory.get(row.memory_id as string) ?? []),
    },
    embedding: [],
    searchable_text: row.searchable_text as string,
  }));
}
