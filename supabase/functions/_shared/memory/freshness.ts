// supabase/functions/_shared/memory/freshness.ts
//
// Computed on read, never stored (see schema migration's comment on
// memories.status - 'stale' is kept in the enum for completeness but
// nothing writes it; this function is what actually determines staleness).
// Per-type thresholds are calibrated defaults, not spec-given numbers -
// spec only says "Commitment should go stale faster than Context."

import type { FreshnessState, MemoryType } from "./types.ts";

const DAY_MS = 24 * 60 * 60 * 1000;

const THRESHOLDS: Record<MemoryType, { agingDays: number; staleDays: number }> = {
  Commitment: { agingDays: 3, staleDays: 7 },
  Blocker: { agingDays: 3, staleDays: 10 },
  CustomerSignal: { agingDays: 7, staleDays: 21 },
  Change: { agingDays: 14, staleDays: 45 },
  Requirement: { agingDays: 14, staleDays: 60 },
  Context: { agingDays: 30, staleDays: 90 },
  Decision: { agingDays: 30, staleDays: 90 },
  Rationale: { agingDays: 30, staleDays: 90 },
  Outcome: { agingDays: 30, staleDays: 90 },
};

export function computeFreshness(
  type: MemoryType,
  validFrom: string,
  observedAt: string,
  now: Date = new Date(),
): FreshnessState {
  const anchor = validFrom || observedAt;
  const ageMs = now.getTime() - new Date(anchor).getTime();
  const { agingDays, staleDays } = THRESHOLDS[type];
  if (ageMs < agingDays * DAY_MS) return "fresh";
  if (ageMs < staleDays * DAY_MS) return "aging";
  return "stale";
}
