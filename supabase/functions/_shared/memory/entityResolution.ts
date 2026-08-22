// supabase/functions/_shared/memory/entityResolution.ts
//
// BATCH 2: the real 3-tier algorithm (spec Section 4). Replaces Batch 1's
// interim exact-match-or-create - this version NEVER auto-creates. Exact
// match -> attach. Embedding similarity above AUTO_MATCH_FLOOR -> attach
// (confident enough to skip review). Between CANDIDATE_FLOOR and
// AUTO_MATCH_FLOOR -> queued with a candidate pre-filled ("merge into X?").
// Below CANDIDATE_FLOOR, or no existing entities of that type at all ->
// queued with no candidate ("confirm as new?"). A mention that gets queued
// contributes nothing to memory_entities until a human resolves it - the
// memory itself still gets written, just with fewer linked entities until
// then.
//
// Thresholds are calibrated defaults, not spec-given numbers - spec only
// says "above a confidence threshold".

import { embedText } from "./embeddings.ts";

export const AUTO_MATCH_FLOOR = 0.90;
export const CANDIDATE_FLOOR = 0.75;

export interface EntityResolutionResult {
  entityId: string | null;
  queued: boolean;
  reason: "exact_match" | "auto_match" | "queued_with_candidate" | "queued_no_candidate";
  // Set only when queued=true - the real unresolved_entities.id, so a
  // caller that doesn't have a memoryId yet (the memory hasn't been
  // written) can backfill memory_id onto this specific row once it does.
  // Without this, a queued mention's memory_id stays permanently null even
  // after a human confirms it - confirmNewEntity's auto-link step
  // (`if (row.memory_id) ...`) silently never fires. Found live: every
  // fixture-load call passes no memoryId at all (chicken-and-egg - entity
  // resolution runs before writeMemory), so every queued mention from
  // fixture loading had lost its link back to the memory that named it.
  unresolvedId: string | null;
}

export async function resolveEntityMention(
  // deno-lint-ignore no-explicit-any
  sql: any,
  tenantId: string,
  mentionText: string,
  entityTypeGuess: string,
  memoryId?: string,
): Promise<EntityResolutionResult> {
  const trimmed = mentionText.trim();

  // Tier 1: exact match (case-insensitive) on canonical_name or an alias.
  const exact = await sql`
    select entity_id from public.entities
    where tenant_id = ${tenantId}
      and entity_type = ${entityTypeGuess}
      and (lower(canonical_name) = lower(${trimmed}) or lower(${trimmed}) = any(select lower(a) from unnest(aliases) as a))
    limit 1
  `;
  if (exact.length > 0) {
    return { entityId: exact[0].entity_id as string, queued: false, reason: "exact_match", unresolvedId: null };
  }

  // Tier 2: embedding similarity against existing entities of the same type.
  const embedding = await embedText(trimmed, "query");
  const similar = await sql`
    select e.entity_id, 1 - (ee.embedding <=> ${JSON.stringify(embedding)}::vector) as similarity
    from public.entity_embeddings ee
    join public.entities e on e.entity_id = ee.entity_id
    where ee.tenant_id = ${tenantId} and e.entity_type = ${entityTypeGuess}
    order by ee.embedding <=> ${JSON.stringify(embedding)}::vector
    limit 1
  `;

  const best = similar[0];
  if (best && Number(best.similarity) >= AUTO_MATCH_FLOOR) {
    return { entityId: best.entity_id as string, queued: false, reason: "auto_match", unresolvedId: null };
  }

  // Tier 3: not confident enough - queue for human review, never auto-create.
  const candidateEntityId = best && Number(best.similarity) >= CANDIDATE_FLOOR ? (best.entity_id as string) : null;
  const candidateScore = best ? Number(best.similarity) : null;
  const inserted = await sql`
    insert into public.unresolved_entities (tenant_id, mention_text, entity_type_guess, memory_id, candidate_entity_id, candidate_score, status)
    values (${tenantId}, ${trimmed}, ${entityTypeGuess}, ${memoryId ?? null}, ${candidateEntityId}, ${candidateScore}, 'pending')
    returning id
  `;
  return {
    entityId: null,
    queued: true,
    reason: candidateEntityId ? "queued_with_candidate" : "queued_no_candidate",
    unresolvedId: inserted[0].id as string,
  };
}

/** Backfills memory_id onto rows queued before the memory existed (the
 * normal fixture-load ordering: entity resolution runs, then writeMemory).
 * Safe to call with an empty array. */
export async function linkQueuedMentionsToMemory(
  // deno-lint-ignore no-explicit-any
  sql: any,
  unresolvedIds: string[],
  memoryId: string,
): Promise<void> {
  if (unresolvedIds.length === 0) return;
  await sql`
    update public.unresolved_entities set memory_id = ${memoryId}
    where id = any(${unresolvedIds}) and memory_id is null
  `;
}

/** Called by the review queue UI's "confirm as new entity" action. */
// deno-lint-ignore no-explicit-any
export async function confirmNewEntity(sql: any, tenantId: string, unresolvedId: string): Promise<string> {
  const rows = await sql`select * from public.unresolved_entities where id = ${unresolvedId} and tenant_id = ${tenantId} and status = 'pending'`;
  if (rows.length === 0) throw new Error("Unresolved entity not found or already resolved");
  const row = rows[0];

  const inserted = await sql`
    insert into public.entities (tenant_id, entity_type, canonical_name)
    values (${tenantId}, ${row.entity_type_guess}, ${row.mention_text})
    on conflict (tenant_id, entity_type, canonical_name) do update set canonical_name = excluded.canonical_name
    returning entity_id
  `;
  const entityId = inserted[0].entity_id as string;

  const embedding = await embedText(row.mention_text, "document");
  await sql`
    insert into public.entity_embeddings (entity_id, tenant_id, embedding)
    values (${entityId}, ${tenantId}, ${JSON.stringify(embedding)})
    on conflict (entity_id) do update set embedding = excluded.embedding
  `;

  if (row.memory_id) {
    await sql`
      insert into public.memory_entities (memory_id, entity_id, tenant_id)
      values (${row.memory_id}, ${entityId}, ${tenantId})
      on conflict do nothing
    `;
  }

  await sql`update public.unresolved_entities set status = 'confirmed_new', resolved_entity_id = ${entityId}, resolved_at = now() where id = ${unresolvedId}`;
  return entityId;
}

/** Called by the review queue UI's "merge into <candidate>" action. */
// deno-lint-ignore no-explicit-any
export async function mergeIntoExistingEntity(sql: any, tenantId: string, unresolvedId: string, targetEntityId: string): Promise<void> {
  const rows = await sql`select * from public.unresolved_entities where id = ${unresolvedId} and tenant_id = ${tenantId} and status = 'pending'`;
  if (rows.length === 0) throw new Error("Unresolved entity not found or already resolved");
  const row = rows[0];

  await sql`
    update public.entities set aliases = array(select distinct unnest(aliases || array[${row.mention_text}]))
    where entity_id = ${targetEntityId} and tenant_id = ${tenantId}
  `;
  if (row.memory_id) {
    await sql`
      insert into public.memory_entities (memory_id, entity_id, tenant_id)
      values (${row.memory_id}, ${targetEntityId}, ${tenantId})
      on conflict do nothing
    `;
  }
  await sql`update public.unresolved_entities set status = 'merged', resolved_entity_id = ${targetEntityId}, resolved_at = now() where id = ${unresolvedId}`;
}
