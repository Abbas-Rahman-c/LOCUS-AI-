// frontend/src/lib/entityActivity.ts
//
// Pure functions computing each entity's activity signal from the
// already-fetched memory list - same "zero extra network call" approach
// as memoryTemporal.ts's point-in-time reconstruction. One visual per
// entity card (a 7-unit density row), not a chart plus a number plus a
// trend arrow, per the explicit "one visual only" instruction.

import type { CanonicalMemory } from './api'

export interface EntityActivity {
  weeklyCounts: number[] // 7 buckets, oldest -> most recent week
  lastActiveAt: string | null // most recent valid_from among this entity's memories
  totalCount: number
}

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

export function computeEntityActivity(memories: CanonicalMemory[], entityId: string, now: Date = new Date()): EntityActivity {
  const weeklyCounts = new Array(7).fill(0)
  let lastActiveAt: string | null = null
  let totalCount = 0

  for (const m of memories) {
    if (!m.entities.some((e) => e.entity_id === entityId)) continue
    totalCount++
    const validFrom = new Date(m.valid_from)
    if (!lastActiveAt || validFrom.toISOString() > lastActiveAt) lastActiveAt = validFrom.toISOString()

    const ageMs = now.getTime() - validFrom.getTime()
    const weeksAgo = Math.floor(ageMs / WEEK_MS)
    if (weeksAgo >= 0 && weeksAgo < 7) {
      weeklyCounts[6 - weeksAgo]++
    }
  }

  return { weeklyCounts, lastActiveAt, totalCount }
}

export function isActiveThisWeek(activity: EntityActivity, now: Date = new Date()): boolean {
  if (!activity.lastActiveAt) return false
  return now.getTime() - new Date(activity.lastActiveAt).getTime() < WEEK_MS
}

export function relativeRecencyLabel(lastActiveAt: string | null, now: Date = new Date()): string {
  if (!lastActiveAt) return 'no activity yet'
  const ms = now.getTime() - new Date(lastActiveAt).getTime()
  const days = Math.floor(ms / (24 * 60 * 60 * 1000))
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks} week${weeks === 1 ? '' : 's'} ago`
  const months = Math.floor(days / 30)
  return `${months} month${months === 1 ? '' : 's'} ago`
}
