// supabase/functions/_shared/memory/attentionStrip.ts
//
// Spec Section 10, literally: four qualifying categories (conflict,
// unconfirmed decision, overdue commitment, aging/low-confidence memory),
// ranked by category weight (not recency), capped at `limit`. Never a
// generic "what changed" feed - only items that need an actual decision.

import type { CanonicalMemoryObject } from "./types.ts";

const CONFIDENCE_THRESHOLD = 0.6;

export type AttentionCategory = "conflict" | "decision" | "commitment" | "staleness";

export interface AttentionItem {
  memory: CanonicalMemoryObject;
  category: AttentionCategory;
  weight: number;
}

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
export function getAttentionItems(memories: CanonicalMemoryObject[], limit = 4): AttentionResult {
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
    ...conflicts.map((m): AttentionItem => ({ memory: m, category: "conflict", weight: 4 })),
    ...unconfirmedDecisions.map((m): AttentionItem => ({ memory: m, category: "decision", weight: 3 })),
    ...overdueCommitments.map((m): AttentionItem => ({ memory: m, category: "commitment", weight: 2 })),
    ...agingMemories.map((m): AttentionItem => ({ memory: m, category: "staleness", weight: 1 })),
  ].sort((a, b) => b.weight - a.weight);

  return { items: ranked.slice(0, limit), total: ranked.length };
}

// ── resolveMemory: the ONE mutation every Attention-strip action and
// Memory Timeline call through - never a client-side dismiss. ───────────

export type ResolutionAction = "confirm_decision" | "check_in_commitment" | "recheck_freshness" | "dismiss_conflict";

const CATEGORY_TO_ACTION: Record<AttentionCategory, ResolutionAction> = {
  conflict: "dismiss_conflict",
  decision: "confirm_decision",
  commitment: "check_in_commitment",
  staleness: "recheck_freshness",
};

export function actionForCategory(category: AttentionCategory): ResolutionAction {
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
