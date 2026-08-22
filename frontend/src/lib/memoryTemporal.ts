// frontend/src/lib/memoryTemporal.ts
//
// Deliberate duplication, not an oversight: this is the same literal port
// of the spec's Section 5 pseudocode as
// supabase/functions/_shared/memory/temporalQueries.ts, kept in TypeScript
// here so MemoryTimelinePage's point-in-time slider can reconstruct state
// entirely client-side against the already-fetched memory list - zero
// network round trip per slider move, which is the whole point of the
// control. If this ever needs to change, change both copies.

import type { CanonicalMemory } from './api'

export function getStateAsOf(memories: CanonicalMemory[], entityId: string, targetDate: string): CanonicalMemory[] {
  const matching = memories.filter(
    (m) =>
      m.entities.some((e) => e.entity_id === entityId) &&
      m.valid_from <= targetDate &&
      (m.valid_until === null || m.valid_until > targetDate),
  )

  const groups = new Map<string, CanonicalMemory[]>()
  for (const m of matching) {
    const key = `${m.type}:${(m.payload.attribute_key as string | undefined) ?? ''}`
    const group = groups.get(key) ?? []
    group.push(m)
    groups.set(key, group)
  }

  return [...groups.values()].map((group) => group.sort((a, b) => b.valid_from.localeCompare(a.valid_from))[0])
}
