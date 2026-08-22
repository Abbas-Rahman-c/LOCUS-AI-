// supabase/functions/_shared/memory/reconcile.ts
//
// writeMemory(): the spec's "reject any memory with zero source_events at
// write time" rule, enforced here so every caller gets it for free.
//
// detectConflicts()/classifyRelation() (Batch 2, spec Section 6): one
// Claude call per new memory, batched across all candidates sharing
// (tenant_id, type, attribute_key), classifying same_fact | update |
// conflict | different_concept. Applied exactly as the spec's pseudocode
// states - same_fact and update auto-resolve silently (no human review,
// matching the spec's own code: only `conflict` calls
// queueForHumanReview), conflict is the ONLY outcome that ever sets
// status='unresolved' and writes a memory_conflicts row. Never a 3-way
// contradicts/duplicates/unrelated call like the old decision_conflicts
// pipeline - always the literal 4-way relation.

import { redactFinancialInfoDeep } from "../financialRedaction.ts";

export interface MemoryWriteInput {
  tenantId: string;
  type: string;
  title: string;
  summary: string;
  payload: Record<string, unknown>;
  entityIds: string[];
  occurredAt: string;
  validFrom: string;
  confidence: number;
  searchableText: string;
  sourceEventIds: string[]; // memory_fixture_events.id[]
  citations: { fixtureEventId: string; excerptRef: string }[];
}

export class ZeroSourceEventsError extends Error {
  constructor() {
    super("Refusing to write a memory with zero source_events - every memory needs at least one.");
    this.name = "ZeroSourceEventsError";
  }
}

// deno-lint-ignore no-explicit-any
export async function writeMemory(sql: any, input: MemoryWriteInput): Promise<string> {
  if (input.sourceEventIds.length === 0) {
    throw new ZeroSourceEventsError();
  }

  const safePayload = redactFinancialInfoDeep(input.payload);

  const rows = await sql`
    insert into public.memories (
      tenant_id, type, title, summary, payload, occurred_at, valid_from,
      confidence, status, searchable_text
    ) values (
      ${input.tenantId}, ${input.type}, ${input.title}, ${input.summary},
      ${sql.json(safePayload)}, ${input.occurredAt}, ${input.validFrom},
      ${input.confidence}, 'current', ${input.searchableText}
    )
    returning memory_id
  `;
  const memoryId = rows[0].memory_id as string;

  for (const entityId of input.entityIds) {
    await sql`
      insert into public.memory_entities (memory_id, entity_id, tenant_id)
      values (${memoryId}, ${entityId}, ${input.tenantId})
      on conflict do nothing
    `;
  }

  for (const fixtureEventId of input.sourceEventIds) {
    await sql`
      insert into public.memory_source_events (memory_id, fixture_event_id, tenant_id)
      values (${memoryId}, ${fixtureEventId}, ${input.tenantId})
      on conflict do nothing
    `;
  }

  for (const citation of input.citations) {
    await sql`
      insert into public.memory_citations (tenant_id, memory_id, fixture_event_id, excerpt_ref)
      values (${input.tenantId}, ${memoryId}, ${citation.fixtureEventId}, ${citation.excerptRef})
    `;
  }

  return memoryId;
}

// ── Reconciliation ─────────────────────────────────────────────────────

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const RECONCILE_MODEL = Deno.env.get("ANTHROPIC_EXTRACT_MODEL") ?? "claude-haiku-4-5-20251001";

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

const RECONCILE_SYSTEM_PROMPT = `You compare one new memory against a short list of existing memories about the same underlying attribute (same entity, same type, same attribute_key), and classify how each candidate relates to the new one.

Four possible relations:
- same_fact: the candidate and the new memory describe the exact same fact, just restated. No new information.
- update: the new memory is a natural evolution of the same fact - the candidate's value has genuinely changed (a date moved, an owner changed, a status advanced). This is normal, expected change over time.
- conflict: the candidate and the new memory make genuinely incompatible claims about the same specific thing, and it is not clear which one is correct. This is NOT the same as an update - use conflict only when the two claims cannot both be true and neither is obviously superseding the other.
- different_concept: despite matching on entity/type/attribute_key, the two memories are actually about different underlying facts (e.g. a beta-launch date vs. a public-launch date are different concepts even if worded similarly).

Worked example: "the public launch is September 1st", "the beta starts September 10th", and "the public launch is September 15th" - the beta date and either public-launch date are different_concept (different facts). But the two public-launch dates (Sept 1 vs Sept 15) are the SAME fact with two different claimed values - if one is clearly a later correction of the other (e.g. the Sept 15 one explicitly says "we're pushing it back"), classify as update. If both are stated with equal confidence and neither explicitly supersedes the other, classify as conflict.

Recency, stated source authority, and how specific/explicit each claim is are only ever used to decide between update and conflict (is this a clear evolution, or a real disagreement) - NEVER to pick a winner once something is classified conflict. A conflict is reported, never silently resolved.`;

const RECONCILE_TOOL = {
  name: "record_relation_classification",
  description: "Classify how each candidate memory relates to the new memory.",
  input_schema: {
    type: "object",
    properties: {
      classifications: {
        type: "array",
        items: {
          type: "object",
          properties: {
            candidate_number: { type: "integer" },
            relationship: { type: "string", enum: ["same_fact", "update", "conflict", "different_concept"] },
            reason: { type: "string" },
            confidence: { type: "number", minimum: 0, maximum: 1 },
          },
          required: ["candidate_number", "relationship", "reason", "confidence"],
          additionalProperties: false,
        },
      },
    },
    required: ["classifications"],
    additionalProperties: false,
  },
};

export interface ReconciliationCandidate {
  memory_id: string;
  title: string;
  summary: string;
  valid_from: string;
}

export interface RelationClassification {
  candidate_number: number;
  relationship: "same_fact" | "update" | "conflict" | "different_concept";
  reason: string;
  confidence: number;
}

export async function classifyRelation(
  newMemory: { title: string; summary: string; valid_from: string },
  candidates: ReconciliationCandidate[],
): Promise<RelationClassification[]> {
  if (candidates.length === 0) return [];

  const candidateList = candidates
    .map((c, i) => `${i + 1}. "${c.title}" - ${c.summary} (valid_from: ${c.valid_from})`)
    .join("\n");
  const userMessage = `New memory: "${newMemory.title}" - ${newMemory.summary} (valid_from: ${newMemory.valid_from})\n\nExisting candidates:\n${candidateList}`;

  const resp = await fetchWithTimeout("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({
      model: RECONCILE_MODEL,
      max_tokens: 1024,
      temperature: 0,
      system: [{ type: "text", text: RECONCILE_SYSTEM_PROMPT, cache_control: { type: "ephemeral" } }],
      messages: [{ role: "user", content: userMessage }],
      tools: [RECONCILE_TOOL],
      tool_choice: { type: "tool", name: "record_relation_classification" },
    }),
  }, 30_000);

  if (!resp.ok) throw new Error(`Anthropic API error ${resp.status}: ${await resp.text()}`);
  const data = await resp.json();
  const block = (data.content ?? []).find((b: { type?: string }) => b.type === "tool_use");
  if (!block) throw new Error("Claude did not return a tool_use block for record_relation_classification");
  return (block.input.classifications ?? []) as RelationClassification[];
}

export interface ConflictResult {
  relation: RelationClassification["relationship"];
  candidateMemoryId: string;
}

/**
 * Runs after a new memory is written: finds candidates sharing
 * (tenant_id, type, attribute_key) and at least one entity, classifies
 * each, and applies the spec's rules. Returns what happened for each
 * candidate (used by the Batch B verification / reporting).
 */
export async function detectConflicts(
  // deno-lint-ignore no-explicit-any
  sql: any,
  tenantId: string,
  newMemoryId: string,
): Promise<ConflictResult[]> {
  const newMemoryRows = await sql`
    select memory_id, type, attribute_key, title, summary, valid_from
    from public.memories where memory_id = ${newMemoryId} and tenant_id = ${tenantId}
  `;
  if (newMemoryRows.length === 0 || !newMemoryRows[0].attribute_key) return [];
  const newMemory = newMemoryRows[0];

  const candidates: ReconciliationCandidate[] = await sql`
    select distinct m.memory_id, m.title, m.summary, m.valid_from
    from public.memories m
    join public.memory_entities me on me.memory_id = m.memory_id
    where m.tenant_id = ${tenantId}
      and m.type = ${newMemory.type}
      and m.attribute_key = ${newMemory.attribute_key}
      and m.status != 'superseded'
      and m.memory_id != ${newMemoryId}
      and me.entity_id in (select entity_id from public.memory_entities where memory_id = ${newMemoryId})
  `;
  if (candidates.length === 0) return [];

  const classifications = await classifyRelation(
    { title: newMemory.title, summary: newMemory.summary, valid_from: newMemory.valid_from },
    candidates,
  );

  const results: ConflictResult[] = [];
  for (const c of classifications) {
    const candidate = candidates[c.candidate_number - 1];
    if (!candidate) continue;

    if (c.relationship === "same_fact" || c.relationship === "different_concept") {
      results.push({ relation: c.relationship, candidateMemoryId: candidate.memory_id });
      continue;
    }

    if (c.relationship === "update") {
      await sql`
        update public.memories set status = 'superseded', valid_until = ${newMemory.valid_from}, updated_at = now()
        where memory_id = ${candidate.memory_id} and tenant_id = ${tenantId}
      `;
      await sql`update public.memories set supersedes = ${candidate.memory_id} where memory_id = ${newMemoryId} and tenant_id = ${tenantId}`;
      results.push({ relation: "update", candidateMemoryId: candidate.memory_id });
      continue;
    }

    if (c.relationship === "conflict") {
      await sql`update public.memories set status = 'unresolved', updated_at = now() where memory_id = ${newMemoryId} and tenant_id = ${tenantId}`;
      await sql`update public.memories set status = 'unresolved', updated_at = now() where memory_id = ${candidate.memory_id} and tenant_id = ${tenantId}`;
      await sql`
        insert into public.memory_conflicts (tenant_id, memory_id, related_memory_id, relationship, reason, confidence)
        values (${tenantId}, ${newMemoryId}, ${candidate.memory_id}, 'conflict', ${c.reason}, ${c.confidence})
        on conflict (memory_id, related_memory_id) do nothing
      `;
      results.push({ relation: "conflict", candidateMemoryId: candidate.memory_id });
    }
  }
  return results;
}
