// supabase/functions/_shared/memory/attentionStrip.ts
//
// Spec Section 10, literally: four qualifying categories (conflict,
// unconfirmed decision, overdue commitment, aging/low-confidence memory),
// ranked by category weight (not recency), capped at `limit`. Never a
// generic "what changed" feed - only items that need an actual decision.

import type { CanonicalMemoryObject } from "./types.ts";

const CONFIDENCE_THRESHOLD = 0.6;

export type AttentionCategory = "conflict" | "decision" | "commitment" | "staleness" | "entity_duplicate";

export interface MemoryAttentionItem {
  kind: "memory";
  memory: CanonicalMemoryObject;
  category: "conflict" | "decision" | "commitment" | "staleness";
  weight: number;
}

// The judgment tier (entityResolution.ts) only reaches this once real
// similarity AND a real model call both failed to resolve a mention
// confidently - genuine ambiguity, not the common case. Surfaced here
// instead of a dedicated page so nothing is ever required of the customer;
// unmerged-but-flagged is a safe, permanent-if-needed state. Reuses the
// exact same /entities/merge and /entities/dismiss actions the internal
// review-queue page calls - no separate mutation path.
export interface EntityDuplicateCandidate {
  unresolvedId: string;
  mentionText: string;
  entityType: string;
  candidateEntityId: string;
  candidateName: string;
}

export interface EntityDuplicateAttentionItem extends EntityDuplicateCandidate {
  kind: "entity_duplicate";
  category: "entity_duplicate";
  weight: number;
}

export type AttentionItem = MemoryAttentionItem | EntityDuplicateAttentionItem;

export interface AttentionResult {
  items: AttentionItem[];
  total: number;
}

function hasLinkedOutcome(m: CanonicalMemoryObject, allMemories: CanonicalMemoryObject[]): boolean {
  if (m.payload.resolved_by_memory_id) return true;
  return allMemories.some((o) => o.type === "Outcome" && o.payload.resolves_memory_id === m.memory_id);
}

// `scopedToUser` in the spec's pseudocode has no other definition to draw
// from - memories aren't assigned to a specific user anywhere in this
// schema, only permission-scoped. The already-permission-filtered
// `memories` list passed in here IS that scoping (isMemoryAccessible
// re-checked by the caller before this runs), so there's nothing further
// to filter on here.
export function getAttentionItems(
  memories: CanonicalMemoryObject[],
  entityDuplicates: EntityDuplicateCandidate[] = [],
  limit = 4,
): AttentionResult {
  const now = new Date();

  const conflicts = memories.filter((m) => m.status === "unresolved");
  const unconfirmedDecisions = memories.filter((m) => m.type === "Decision" && m.payload.decision_status === "proposed");
  const overdueCommitments = memories.filter((m) =>
    m.type === "Commitment" &&
    typeof m.payload.due_date === "string" &&
    new Date(m.payload.due_date) < now &&
    !hasLinkedOutcome(m, memories)
  );
  const agingMemories = memories.filter((m) => m.freshness === "stale" && m.confidence < CONFIDENCE_THRESHOLD);

  const ranked: AttentionItem[] = [
    ...conflicts.map((m): AttentionItem => ({ kind: "memory", memory: m, category: "conflict", weight: 4 })),
    ...unconfirmedDecisions.map((m): AttentionItem => ({ kind: "memory", memory: m, category: "decision", weight: 3 })),
    ...overdueCommitments.map((m): AttentionItem => ({ kind: "memory", memory: m, category: "commitment", weight: 2 })),
    ...entityDuplicates.map((d): AttentionItem => ({ kind: "entity_duplicate", ...d, category: "entity_duplicate", weight: 2 })),
    ...agingMemories.map((m): AttentionItem => ({ kind: "memory", memory: m, category: "staleness", weight: 1 })),
  ].sort((a, b) => b.weight - a.weight);

  return { items: ranked.slice(0, limit), total: ranked.length };
}

// ── resolveMemory: the ONE mutation every Attention-strip action and
// Memory Timeline call through - never a client-side dismiss. ───────────

export type ResolutionAction = "confirm_decision" | "check_in_commitment" | "recheck_freshness" | "dismiss_conflict";

// entity_duplicate deliberately excluded - it doesn't go through
// resolveMemory at all (nothing about it lives in the memories table); the
// frontend calls /entities/merge or /entities/dismiss directly instead.
type MemoryAttentionCategory = MemoryAttentionItem["category"];

const CATEGORY_TO_ACTION: Record<MemoryAttentionCategory, ResolutionAction> = {
  conflict: "dismiss_conflict",
  decision: "confirm_decision",
  commitment: "check_in_commitment",
  staleness: "recheck_freshness",
};

export function actionForCategory(category: MemoryAttentionCategory): ResolutionAction {
  return CATEGORY_TO_ACTION[category];
}

export class MemoryNotAccessibleError extends Error {
  constructor() {
    super("This memory is not accessible to you, or does not exist.");
    this.name = "MemoryNotAccessibleError";
  }
}

/**
 * The real state mutation behind "Resolve / Confirm / Check in / Recheck".
 * Each action changes something real and persists an audit row - never a
 * client-side-only dismiss, per the spec's explicit rule that a conflict
 * still `"unresolved"` in the data must never disappear just because
 * someone closed the card.
 *
 * - dismiss_conflict: status 'unresolved' -> 'current' (closes the review,
 *   doesn't pick a winner - that's the evidence drawer / Memory Timeline's
 *   job, this just acknowledges a human looked at it).
 * - confirm_decision: payload.decision_status 'proposed' -> 'decided'.
 * - check_in_commitment / recheck_freshness: bumps observed_at to now() -
 *   freshness is computed from observed_at (see freshness.ts), so a real
 *   human re-confirmation genuinely resets it, the same way a fresh
 *   observation would. Neither of these has an obvious target `status`
 *   value in the existing MemoryStatus enum (there's no "acknowledged,
 *   still pending" state) - observed_at is the real, honest mutation
 *   available for these two, not a status change forced to fit.
 */
export async function resolveMemory(
  // deno-lint-ignore no-explicit-any
  sql: any,
  tenantId: string,
  memoryId: string,
  action: ResolutionAction,
  note: string | null,
  resolvedByActorId: string | null,
): Promise<void> {
  const rows = await sql`select status from public.memories where memory_id = ${memoryId} and tenant_id = ${tenantId}`;
  if (rows.length === 0) throw new MemoryNotAccessibleError();
  const originalStatus = rows[0].status as string;

  if (action === "dismiss_conflict") {
    await sql`update public.memories set status = 'current', updated_at = now() where memory_id = ${memoryId} and tenant_id = ${tenantId}`;
  } else if (action === "confirm_decision") {
    await sql`
      update public.memories
      set payload = jsonb_set(payload, '{decision_status}', '"decided"'::jsonb), updated_at = now()
      where memory_id = ${memoryId} and tenant_id = ${tenantId}
    `;
  } else {
    // check_in_commitment / recheck_freshness
    await sql`update public.memories set observed_at = now(), updated_at = now() where memory_id = ${memoryId} and tenant_id = ${tenantId}`;
  }

  await sql`
    insert into public.memory_resolutions (tenant_id, memory_id, action, original_status, note, resolved_by_actor_id)
    values (${tenantId}, ${memoryId}, ${action}, ${originalStatus}, ${note}, ${resolvedByActorId})
  `;
}
