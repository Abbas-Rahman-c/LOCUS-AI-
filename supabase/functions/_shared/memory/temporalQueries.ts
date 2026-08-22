// supabase/functions/_shared/memory/temporalQueries.ts
//
// Literal ports of the spec's Section 5 pseudocode - pure functions over an
// already-fetched CanonicalMemoryObject[], no DB or model call inside any
// of them. getCurrentState's filter matches the spec exactly: it excludes
// only 'superseded'/'contradicted', NOT 'unresolved' - an unresolved memory
// can still be the most-recent match, since silently hiding it would
// defeat the point of surfacing conflicts. The UI (Batch 3) compensates
// with a conflict badge rather than this function hiding it.

import type { CanonicalMemoryObject, MemoryType } from "./types.ts";

export function getCurrentState(
  memories: CanonicalMemoryObject[],
  entityId: string,
  type: MemoryType,
  attributeKey?: string,
  now: Date = new Date(),
): CanonicalMemoryObject | undefined {
  const nowIso = now.toISOString();
  return memories
    .filter((m) =>
      m.entities.some((e) => e.entity_id === entityId) &&
      m.type === type &&
      (!attributeKey || m.payload.attribute_key === attributeKey) &&
      m.status !== "superseded" &&
      m.status !== "contradicted" &&
      (m.valid_until === null || m.valid_until > nowIso)
    )
    .sort((a, b) => b.valid_from.localeCompare(a.valid_from))[0];
}

export function getStateAsOf(
  memories: CanonicalMemoryObject[],
  entityId: string,
  targetDate: string,
): CanonicalMemoryObject[] {
  const matching = memories.filter((m) =>
    m.entities.some((e) => e.entity_id === entityId) &&
    m.valid_from <= targetDate &&
    (m.valid_until === null || m.valid_until > targetDate)
  );

  const groups = new Map<string, CanonicalMemoryObject[]>();
  for (const m of matching) {
    const key = `${m.type}:${m.payload.attribute_key ?? ""}`;
    const group = groups.get(key) ?? [];
    group.push(m);
    groups.set(key, group);
  }

  return [...groups.values()].map(
    (group) => group.sort((a, b) => b.valid_from.localeCompare(a.valid_from))[0],
  );
}

export interface ChangeEntry {
  current: CanonicalMemoryObject;
  previous: CanonicalMemoryObject | null;
}

export function getChangesSince(
  memories: CanonicalMemoryObject[],
  entityId: string,
  sinceTimestamp: string,
): ChangeEntry[] {
  const byId = new Map(memories.map((m) => [m.memory_id, m]));
  return memories
    .filter((m) => m.entities.some((e) => e.entity_id === entityId) && m.valid_from > sinceTimestamp)
    .map((m) => ({
      current: m,
      previous: m.supersedes ? byId.get(m.supersedes) ?? null : null,
    }));
}
