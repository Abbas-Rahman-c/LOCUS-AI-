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

// ── Judgment tier ────────────────────────────────────────────────────────
//
// A real Claude call, same pattern as reconcile.ts's classifyRelation -
// not a lower similarity number. Sits between "similarity says probably"
// and "queue it, a human has to look": when embedding similarity alone
// can't confidently resolve a mention (same-type score in the ambiguous
// [CANDIDATE_FLOOR, AUTO_MATCH_FLOOR) band, or ANY cross-type match), this
// gives the model the actual mention context and the candidate's own
// identity and asks it to judge, the way a person would - not "how close
// are these two vectors" but "are these actually the same real thing."
// Explicitly does NOT touch AUTO_MATCH_FLOOR/CANDIDATE_FLOOR - a genuinely
// uncertain judgment still falls through to the existing queue tier
// unchanged. This is a second, independent signal, not a lower bar.

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const JUDGE_MODEL = Deno.env.get("ANTHROPIC_EXTRACT_MODEL") ?? "claude-haiku-4-5-20251001";

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

const JUDGE_SYSTEM_PROMPT = `You decide whether a newly-mentioned entity is the SAME real-world thing as an existing entity already on record, using actual context - not just how similar the names look.

You'll see: the new mention's exact text, the type it was guessed as, the sentence/memory it came from, and the existing candidate's canonical name, type, and known aliases.

Judge same_entity true only when you have real grounds - the same person under a nickname or last-name-only reference, the same system/project referred to two different ways, a name that's an obvious typo or reformatting of the other. Judge same_entity false when the names merely resemble each other but context gives no real reason to think they're the same thing - two different people who happen to share a first name, a project name that happens to match a system name by coincidence, or when you simply don't have enough information either way.

confidence "high" means you'd stake real correctness on this call - a wrong high-confidence answer permanently merges or permanently keeps separate two things that shouldn't be. confidence "medium" or "low" means you have a lean but real doubt remains - always pair those with same_entity based on your best guess, but the caller only acts automatically on "high"; anything else is treated as genuinely unresolved and left for a human.

Worked examples:
- Mention "Sudhira" (Person) in "Sudhira freed up for MCP Server work" vs candidate "Sudhira Chegu" (Person, no aliases) -> same_entity: true, confidence: high. First-name-only reference to someone whose full name is already on record is a completely ordinary way to refer to the same person.
- Mention "MCP Server" (Project) in "reassigned to X, Y freed up for MCP Server work" vs candidate "MCP Server" (System, canonical name identical) -> same_entity: true, confidence: high. Identical name, and the sentence is plainly talking about the same system being built, just guessed as a different entity type.
- Mention "Task 22" (Project) vs candidate "Team Pulse Digest + MCP Server" (Project) -> same_entity: false, confidence: low. There's no textual or contextual link connecting "Task 22" to that specific ticket beyond a guess - genuinely unresolved, not a confident no.`;

const JUDGE_TOOL = {
  name: "record_entity_judgment",
  description: "Judge whether a newly-mentioned entity is the same real-world thing as an existing candidate entity.",
  input_schema: {
    type: "object",
    properties: {
      same_entity: { type: "boolean" },
      confidence: { type: "string", enum: ["high", "medium", "low"] },
      reason: { type: "string" },
    },
    required: ["same_entity", "confidence", "reason"],
    additionalProperties: false,
  },
};

export interface EntityJudgment {
  sameEntity: boolean;
  confidence: "high" | "medium" | "low";
  reason: string;
}

export async function judgeEntityMatch(
  mentionText: string,
  entityTypeGuess: string,
  mentionContext: string,
  candidate: { canonicalName: string; entityType: string; aliases: string[] },
): Promise<EntityJudgment> {
  const userMessage = `New mention: "${mentionText}" (guessed type: ${entityTypeGuess})
Context it appeared in: ${mentionContext}

Existing candidate: "${candidate.canonicalName}" (type: ${candidate.entityType})${candidate.aliases.length > 0 ? `, known aliases: ${candidate.aliases.join(", ")}` : ""}`;

  const resp = await fetchWithTimeout("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({
      model: JUDGE_MODEL,
      max_tokens: 512,
      temperature: 0,
      system: [{ type: "text", text: JUDGE_SYSTEM_PROMPT, cache_control: { type: "ephemeral" } }],
      messages: [{ role: "user", content: userMessage }],
      tools: [JUDGE_TOOL],
      tool_choice: { type: "tool", name: "record_entity_judgment" },
    }),
  }, 30_000);

  if (!resp.ok) throw new Error(`Anthropic API error ${resp.status}: ${await resp.text()}`);
  const data = await resp.json();
  const block = (data.content ?? []).find((b: { type?: string }) => b.type === "tool_use");
  if (!block) throw new Error("Claude did not return a tool_use block for record_entity_judgment");
  const input = block.input as { same_entity: boolean; confidence: "high" | "medium" | "low"; reason: string };
  return { sameEntity: input.same_entity, confidence: input.confidence, reason: input.reason };
}

export interface EntityResolutionResult {
  entityId: string | null;
  queued: boolean;
  reason: "exact_match" | "auto_match" | "judged_match" | "judged_new" | "queued_with_candidate" | "queued_no_candidate";
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

interface MatchCandidate {
  entityId: string;
  entityType: string;
  canonicalName: string;
  aliases: string[];
  similarity: number;
  crossType: boolean;
}

/**
 * Shared tiered-match lookup: exact (case-insensitive, name or alias) then
 * embedding similarity, against LIVE current entities - used both by
 * resolveEntityMention (extraction time) and confirmNewEntity's re-check
 * (confirm time, see that function's own comment for why re-checking here
 * matters). `includeCrossType` also searches entities of every OTHER type
 * once the same-type search comes up empty/low-confidence - a same-text
 * mention extracted with an inconsistent type guess (e.g. "MCP Server" as
 * System once and Project another time) would otherwise never be found,
 * since the old exact-match query was scoped by entity_type with no
 * fallback at all.
 */
async function findBestMatch(
  // deno-lint-ignore no-explicit-any
  sql: any,
  tenantId: string,
  text: string,
  entityType: string,
  includeCrossType: boolean,
  // "query" for a raw mention searching against stored entity documents
  // (resolveEntityMention's real-time use), "document" when BOTH sides
  // are entity names (confirmNewEntity's re-check) - Voyage's query/
  // document split is asymmetric by design, and comparing an entity name
  // against another entity name with the query encoding under-scored a
  // real, confirmed 0.985 doc-vs-doc similarity so far it missed
  // AUTO_MATCH_FLOOR entirely. Found live, not assumed.
  inputType: "query" | "document" = "query",
): Promise<{ exact: MatchCandidate | null; best: MatchCandidate | null; crossTypeExact: MatchCandidate | null; crossTypeBest: MatchCandidate | null }> {
  const trimmed = text.trim();

  const exactRows = await sql`
    select entity_id, entity_type, canonical_name, aliases from public.entities
    where tenant_id = ${tenantId} and entity_type = ${entityType} and status = 'current'
      and (lower(canonical_name) = lower(${trimmed}) or lower(${trimmed}) = any(select lower(a) from unnest(aliases) as a))
    limit 1
  `;
  const exact: MatchCandidate | null = exactRows[0]
    ? { entityId: exactRows[0].entity_id, entityType: exactRows[0].entity_type, canonicalName: exactRows[0].canonical_name, aliases: exactRows[0].aliases ?? [], similarity: 1, crossType: false }
    : null;

  const embedding = await embedText(trimmed, inputType);
  const sameTypeRows = await sql`
    select e.entity_id, e.entity_type, e.canonical_name, e.aliases, 1 - (ee.embedding <=> ${JSON.stringify(embedding)}::vector) as similarity
    from public.entity_embeddings ee
    join public.entities e on e.entity_id = ee.entity_id
    where ee.tenant_id = ${tenantId} and e.entity_type = ${entityType} and e.status = 'current'
    order by ee.embedding <=> ${JSON.stringify(embedding)}::vector
    limit 1
  `;
  const best: MatchCandidate | null = sameTypeRows[0]
    ? { entityId: sameTypeRows[0].entity_id, entityType: sameTypeRows[0].entity_type, canonicalName: sameTypeRows[0].canonical_name, aliases: sameTypeRows[0].aliases ?? [], similarity: Number(sameTypeRows[0].similarity), crossType: false }
    : null;

  let crossTypeExact: MatchCandidate | null = null;
  let crossTypeBest: MatchCandidate | null = null;
  if (includeCrossType) {
    // The literal-same-text-different-type case ("MCP Server" as System
    // once, Project another time) is a stronger signal than any
    // similarity score - worth its own exact check across types, not
    // just folded into the similarity pass below. Still never
    // auto-merged purely on score (a cross-type match by score alone is
    // always flagged for review), just reported with similarity=1 so it's
    // not lost to a lower-scoring similarity hit - the judgment tier can
    // still auto-resolve it with real reasoning, see resolveEntityMention.
    const crossExactRows = await sql`
      select entity_id, entity_type, canonical_name, aliases from public.entities
      where tenant_id = ${tenantId} and entity_type != ${entityType} and status = 'current'
        and (lower(canonical_name) = lower(${trimmed}) or lower(${trimmed}) = any(select lower(a) from unnest(aliases) as a))
      limit 1
    `;
    crossTypeExact = crossExactRows[0]
      ? { entityId: crossExactRows[0].entity_id, entityType: crossExactRows[0].entity_type, canonicalName: crossExactRows[0].canonical_name, aliases: crossExactRows[0].aliases ?? [], similarity: 1, crossType: true }
      : null;

    const crossRows = await sql`
      select e.entity_id, e.entity_type, e.canonical_name, e.aliases, 1 - (ee.embedding <=> ${JSON.stringify(embedding)}::vector) as similarity
      from public.entity_embeddings ee
      join public.entities e on e.entity_id = ee.entity_id
      where ee.tenant_id = ${tenantId} and e.entity_type != ${entityType} and e.status = 'current'
      order by ee.embedding <=> ${JSON.stringify(embedding)}::vector
      limit 1
    `;
    crossTypeBest = crossRows[0]
      ? { entityId: crossRows[0].entity_id, entityType: crossRows[0].entity_type, canonicalName: crossRows[0].canonical_name, aliases: crossRows[0].aliases ?? [], similarity: Number(crossRows[0].similarity), crossType: true }
      : null;
  }

  return { exact, best, crossTypeExact, crossTypeBest };
}

export async function resolveEntityMention(
  // deno-lint-ignore no-explicit-any
  sql: any,
  tenantId: string,
  mentionText: string,
  entityTypeGuess: string,
  memoryId?: string,
  // The memory's own title+summary (or equivalent) - what the judgment
  // tier actually reasons over. Without it, the judgment tier is skipped
  // entirely and behavior is unchanged from before it existed (falls
  // straight through to the queue tier) - a judgment call with no real
  // context to judge from would just be a coin flip wearing a costume.
  mentionContext?: string,
): Promise<EntityResolutionResult> {
  const trimmed = mentionText.trim();
  const { exact, best, crossTypeExact, crossTypeBest } = await findBestMatch(sql, tenantId, trimmed, entityTypeGuess, true);

  if (exact) {
    return { entityId: exact.entityId, queued: false, reason: "exact_match", unresolvedId: null };
  }
  if (best && best.similarity >= AUTO_MATCH_FLOOR) {
    return { entityId: best.entityId, queued: false, reason: "auto_match", unresolvedId: null };
  }

  // Judgment tier: only engages when there's an actual candidate worth
  // judging AND real context to judge it with. A confident "same" resolves
  // immediately - even cross-type, since this is a reasoned call, not a
  // score crossing a line. A confident "different" means we now have
  // stronger grounds to create this as genuinely new than a bare "nothing
  // scored high enough" ever gave us, so it's created outright rather than
  // routed to the queue to be rubber-stamped. Anything less than
  // confident falls straight through to the existing queue tier,
  // unchanged - AUTO_MATCH_FLOOR/CANDIDATE_FLOOR are never touched by this.
  const judgeCandidate = (best && best.similarity >= CANDIDATE_FLOOR)
    ? best
    : crossTypeExact ?? (crossTypeBest && crossTypeBest.similarity >= CANDIDATE_FLOOR ? crossTypeBest : null);

  if (judgeCandidate && mentionContext) {
    const judgment = await judgeEntityMatch(trimmed, entityTypeGuess, mentionContext, {
      canonicalName: judgeCandidate.canonicalName,
      entityType: judgeCandidate.entityType,
      aliases: judgeCandidate.aliases,
    });

    if (judgment.confidence === "high" && judgment.sameEntity) {
      return { entityId: judgeCandidate.entityId, queued: false, reason: "judged_match", unresolvedId: null };
    }
    if (judgment.confidence === "high" && !judgment.sameEntity) {
      const entityId = await createEntity(sql, tenantId, entityTypeGuess, trimmed);
      return { entityId, queued: false, reason: "judged_new", unresolvedId: null };
    }
    // else: genuinely uncertain - falls through to the queue tier below,
    // same as if no judgment had been possible at all.
  }

  // Tier 3: not confident enough - queue for human review, never auto-create.
  const candidateEntityId = best && best.similarity >= CANDIDATE_FLOOR ? best.entityId : null;
  const candidateScore = best ? best.similarity : null;
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

// deno-lint-ignore no-explicit-any
async function createEntity(sql: any, tenantId: string, entityType: string, canonicalName: string): Promise<string> {
  const inserted = await sql`
    insert into public.entities (tenant_id, entity_type, canonical_name)
    values (${tenantId}, ${entityType}, ${canonicalName})
    on conflict (tenant_id, entity_type, canonical_name) do update set canonical_name = excluded.canonical_name
    returning entity_id
  `;
  const entityId = inserted[0].entity_id as string;
  const embedding = await embedText(canonicalName, "document");
  await sql`
    insert into public.entity_embeddings (entity_id, tenant_id, embedding)
    values (${entityId}, ${tenantId}, ${JSON.stringify(embedding)})
    on conflict (entity_id) do update set embedding = excluded.embedding
  `;
  return entityId;
}

/**
 * For entity mentions extraction marked role="referenced" on a
 * Project/System/Topic/Product/Customer type - a name mentioned only as a
 * comparison, a pointer to other work, or a schedule label, not something
 * this memory is actually about. These should link to an already-existing
 * entity when one clearly matches, but must never create a new one and
 * must never enter the human review queue - queuing a passing mention
 * would just move the "phantom project" problem from entities into the
 * review queue instead of fixing it. Checks both same-type and cross-type
 * (a referenced mention isn't asserting a type, just pointing at
 * something), and only links on a confident match - same AUTO_MATCH_FLOOR
 * bar as resolveEntityMention's own auto-match tier, no separate constant.
 * Person/Team mentions never call this - see extraction.ts's prompt for
 * why those stay on the full resolveEntityMention path regardless of role.
 */
export async function resolveReferencedMention(
  // deno-lint-ignore no-explicit-any
  sql: any,
  tenantId: string,
  mentionText: string,
  entityTypeGuess: string,
): Promise<string | null> {
  const trimmed = mentionText.trim();
  const { exact, best, crossTypeExact, crossTypeBest } = await findBestMatch(sql, tenantId, trimmed, entityTypeGuess, true, "query");

  if (exact) return exact.entityId;
  if (crossTypeExact) return crossTypeExact.entityId;
  if (best && best.similarity >= AUTO_MATCH_FLOOR) return best.entityId;
  if (crossTypeBest && crossTypeBest.similarity >= AUTO_MATCH_FLOOR) return crossTypeBest.entityId;
  return null;
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

export interface ConfirmNewEntityResult {
  entityId: string;
  // True when this confirm auto-attached to an entity that already
  // existed at confirm time (found by the live re-check below) instead of
  // creating a new one.
  attachedExisting: boolean;
  // Set when a same-type-but-not-confident-enough, or any cross-type,
  // match was found - a new unresolved_entities row was queued for a
  // human to review the possible merge (source_entity_id set). Never
  // auto-merged - confidence isn't high enough, or the match crosses
  // entity_type, and cross-type matches are never auto-merged regardless
  // of score.
  flaggedForMergeReview: string | null; // the new unresolved_entities.id, if any
}

/**
 * Called by the review queue UI's "confirm as new entity" action.
 *
 * Real bug found live: this used to only check for an EXACT
 * (tenant_id, entity_type, canonical_name) conflict before inserting -
 * never re-ran the same similarity check resolveEntityMention uses.
 * Bulk-confirming many queued mentions in one sitting (each originally
 * queued independently, when nothing existed yet to match against) created
 * real duplicate entities with zero flag, because nothing ever re-checked
 * against entities OTHER mentions in the same batch had just created.
 * This now re-runs the full tiered check against LIVE current entities
 * immediately before finalizing:
 *   - same-type exact match, or same-type similarity >= AUTO_MATCH_FLOOR:
 *     attach to the existing entity instead of creating a duplicate -
 *     mirrors resolveEntityMention's own auto-match behavior.
 *   - same-type similarity in [CANDIDATE_FLOOR, AUTO_MATCH_FLOOR), or ANY
 *     cross-type match >= CANDIDATE_FLOOR: still create the entity (the
 *     human already clicked confirm), but ALSO queue a new
 *     unresolved_entities row (source_entity_id = the new entity) so the
 *     possible merge gets a real human decision later - never silently
 *     ignored, never auto-merged across types regardless of score.
 */
// deno-lint-ignore no-explicit-any
export async function confirmNewEntity(sql: any, tenantId: string, unresolvedId: string): Promise<ConfirmNewEntityResult> {
  const rows = await sql`select * from public.unresolved_entities where id = ${unresolvedId} and tenant_id = ${tenantId} and status = 'pending'`;
  if (rows.length === 0) throw new Error("Unresolved entity not found or already resolved");
  const row = rows[0];

  const { exact, best, crossTypeExact, crossTypeBest } = await findBestMatch(sql, tenantId, row.mention_text, row.entity_type_guess, true, "document");

  if (exact || (best && best.similarity >= AUTO_MATCH_FLOOR)) {
    const match = (exact ?? best) as MatchCandidate;
    if (row.memory_id) {
      await sql`
        insert into public.memory_entities (memory_id, entity_id, tenant_id)
        values (${row.memory_id}, ${match.entityId}, ${tenantId})
        on conflict do nothing
      `;
    }
    await sql`update public.unresolved_entities set status = 'confirmed_new', resolved_entity_id = ${match.entityId}, resolved_at = now() where id = ${unresolvedId}`;
    return { entityId: match.entityId, attachedExisting: true, flaggedForMergeReview: null };
  }

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

  let flaggedForMergeReview: string | null = null;
  const flagCandidate = (best && best.similarity >= CANDIDATE_FLOOR)
    ? best
    : crossTypeExact ?? (crossTypeBest && crossTypeBest.similarity >= CANDIDATE_FLOOR ? crossTypeBest : null);
  if (flagCandidate) {
    const flagRow = await sql`
      insert into public.unresolved_entities (tenant_id, mention_text, entity_type_guess, source_entity_id, candidate_entity_id, candidate_score, status)
      values (${tenantId}, ${row.mention_text}, ${row.entity_type_guess}, ${entityId}, ${flagCandidate.entityId}, ${flagCandidate.similarity}, 'pending')
      returning id
    `;
    flaggedForMergeReview = flagRow[0].id as string;
  }

  return { entityId, attachedExisting: false, flaggedForMergeReview };
}

/**
 * Called by the review queue UI's "merge into <candidate>" action. Handles
 * both shapes unresolved_entities can now represent:
 *   - a genuine raw mention (source_entity_id null) - original behavior,
 *     adds an alias to the target and links the one memory_id the mention
 *     came from.
 *   - an already-CONFIRMED entity flagged for merge review
 *     (source_entity_id set) - re-points every memory_entities row that
 *     referenced the losing entity to the target, and marks the losing
 *     entity superseded rather than deleting it (same convention memories
 *     already use - a merge decision should stay reconstructable, not
 *     erase which entity a memory was originally linked to).
 */
// deno-lint-ignore no-explicit-any
export async function mergeIntoExistingEntity(sql: any, tenantId: string, unresolvedId: string, targetEntityId: string): Promise<void> {
  const rows = await sql`select * from public.unresolved_entities where id = ${unresolvedId} and tenant_id = ${tenantId} and status = 'pending'`;
  if (rows.length === 0) throw new Error("Unresolved entity not found or already resolved");
  const row = rows[0];

  await sql`
    update public.entities set aliases = array(select distinct unnest(aliases || array[${row.mention_text}]))
    where entity_id = ${targetEntityId} and tenant_id = ${tenantId}
  `;

  if (row.source_entity_id) {
    const losingEntityId = row.source_entity_id as string;
    // Re-point every memory this entity was linked to, then drop the
    // now-redundant rows left over from any memory that already linked to
    // both (insert-then-delete, not update, to cleanly respect the
    // (memory_id, entity_id) primary key without a conflict).
    await sql`
      insert into public.memory_entities (memory_id, entity_id, tenant_id)
      select memory_id, ${targetEntityId}, ${tenantId} from public.memory_entities
      where entity_id = ${losingEntityId} and tenant_id = ${tenantId}
      on conflict do nothing
    `;
    await sql`delete from public.memory_entities where entity_id = ${losingEntityId} and tenant_id = ${tenantId}`;
    await sql`
      update public.entities set status = 'superseded', superseded_by = ${targetEntityId}
      where entity_id = ${losingEntityId} and tenant_id = ${tenantId}
    `;
  } else if (row.memory_id) {
    await sql`
      insert into public.memory_entities (memory_id, entity_id, tenant_id)
      values (${row.memory_id}, ${targetEntityId}, ${tenantId})
      on conflict do nothing
    `;
  }

  await sql`update public.unresolved_entities set status = 'merged', resolved_entity_id = ${targetEntityId}, resolved_at = now() where id = ${unresolvedId}`;
}
