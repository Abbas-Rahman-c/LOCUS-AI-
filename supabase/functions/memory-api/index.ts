// supabase/functions/memory-api/index.ts
//
// Owns every endpoint for the new Memory Intelligence layer (plan:
// C:\Users\L Lawliet\.claude\plans\steady-whistling-hearth.md). Kept
// separate from the live, revenue-critical api/index.ts so nothing here
// can regress today's /search, /digest, or /api/v1/decisions.
//
// BATCH 1: just POST /fixtures/load - loads hand-written or real-replayed
// NormalizedEvents, runs them through extraction + a Batch-1-interim
// entity resolution + the write path, no reconciliation yet (Batch 2).

import { withAdmin, withTenant } from "../_shared/db.ts";
import { extractMemory, validatePayloadForType } from "../_shared/memory/extraction.ts";
import { replayHistoricalEvents, type NormalizedEvent } from "../_shared/memory/historicalReplay.ts";
import { STARTER_EVENTS } from "../_shared/memory/fixtures/starterEvents.ts";
import { resolveEntityMention, confirmNewEntity, mergeIntoExistingEntity, linkQueuedMentionsToMemory } from "../_shared/memory/entityResolution.ts";
import { writeMemory, detectConflicts, classifyRelation, ZeroSourceEventsError } from "../_shared/memory/reconcile.ts";
import { embedText } from "../_shared/memory/embeddings.ts";
import type { MemoryType } from "../_shared/memory/types.ts";
import { requireServiceRole } from "../_shared/requireServiceRole.ts";
import { isMemoryAccessible, isMemoryAccessibleBatch } from "../_shared/memory/permissions.ts";
import { loadMemoriesForTenant } from "../_shared/memory/loadMemories.ts";
import { getCurrentTenant, resolvePermissionScopes } from "../_shared/tenantAuth.ts";
import { runGoldenEval } from "../_shared/memory/eval/evalRunner.ts";
import { getAttentionItems, resolveMemory, actionForCategory, MemoryNotAccessibleError, type ResolutionAction } from "../_shared/memory/attentionStrip.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "content-type": "application/json" } });
}

// Real gate, found missing during Checkpoint A follow-up: every route in
// this function previously relied only on Supabase's default per-function
// JWT verification, which the PUBLIC anon key satisfies - meaning
// /fixtures/load (writes fabricated "memories" into any real tenant) and
// /debug/delete-memories (deletes any tenant's real data) were reachable
// by anyone holding the project's anon key, which ships in the frontend
// bundle and is visible to any browser. This isn't a hypothetical: it was
// the actual deployed state until this check was added. Requires the JWT's
// role claim to be service_role - the key that never ships to any
// frontend - not just "any successfully verified JWT". Every route below
// goes through this, no exceptions, including the debug/verification ones.
// requireServiceRole now lives in ../_shared/requireServiceRole.ts (also
// used by slack-membership-sync) - moved so a second admin-only function
// doesn't grow its own hand-copied, silently-drifting version.

async function loadFixtureSet(fixtureSet: string, tenantId: string, perSourceLimit: number): Promise<NormalizedEvent[]> {
  if (fixtureSet === "starter_events") {
    return STARTER_EVENTS.map((e) => ({ ...e, tenant_id: tenantId }));
  }
  if (fixtureSet === "real_replay") {
    return await replayHistoricalEvents(tenantId, perSourceLimit);
  }
  throw new Error(`Unknown fixture_set: ${fixtureSet}`);
}

interface LoadResult {
  event_source_id: string;
  event_source: string;
  outcome: "memory_created" | "discarded" | "rejected_zero_sources" | "invalid_payload" | "error";
  memory_id?: string;
  memory_type?: string;
  detail?: string;
  queued_entity_mentions?: number;
  reconciliation?: { relation: string; candidate_memory_id: string }[];
}

async function handleFixturesLoad(req: Request): Promise<Response> {
  let body: { fixture_set?: string; tenant_id?: string; per_source_limit?: number };
  try {
    body = await req.json();
  } catch {
    return json({ detail: "Invalid JSON body" }, 400);
  }
  if (!body.tenant_id) return json({ detail: "tenant_id is required" }, 400);
  if (!body.fixture_set) return json({ detail: "fixture_set is required" }, 400);

  const tenantId = body.tenant_id;
  // Kept small by default - each event costs one sequential Claude call
  // plus embeddings, and this endpoint runs inside one edge function
  // invocation's wall-clock limit, not a background job.
  const perSourceLimit = body.per_source_limit ?? 5;
  let events: NormalizedEvent[];
  try {
    events = await loadFixtureSet(body.fixture_set, tenantId, perSourceLimit);
  } catch (err) {
    return json({ detail: err instanceof Error ? err.message : String(err) }, 400);
  }

  const results: LoadResult[] = [];

  for (const event of events) {
    try {
      await withTenant(tenantId, async (sql) => {
        // Dedup on (tenant_id, source, source_id), same key raw_events uses.
        const fixtureRows = await sql`
          insert into public.memory_fixture_events (
            tenant_id, source, source_id, actor_display_name, thread_ref,
            permission_scope, raw_content, occurred_at
          ) values (
            ${tenantId}, ${event.source}, ${event.source_id}, ${event.actor.display_name},
            ${event.thread_ref}, ${event.permission_scope}, ${event.raw_content}, ${event.occurred_at}
          )
          on conflict (tenant_id, source, source_id) do update set raw_content = excluded.raw_content
          returning id
        `;
        const fixtureEventId = fixtureRows[0].id as string;

        // Bug found and fixed during Checkpoint A follow-up: two replay
        // calls with different per_source_limit values can both return the
        // same underlying raw_events row. The insert above upserts the
        // fixture_event row either way (correct - one row per source
        // event), but without this guard, re-processing that same row
        // re-ran extraction and wrote a SECOND memory for content already
        // captured - confirmed live, two identical "App deployment
        // problems resolved" memories from one Slack message. Skip
        // extraction entirely once a fixture event already has a memory.
        const alreadyProcessed = await sql`
          select 1 from public.memory_source_events where fixture_event_id = ${fixtureEventId} limit 1
        `;
        if (alreadyProcessed.length > 0) {
          results.push({ event_source_id: event.source_id, event_source: event.source, outcome: "discarded", detail: "already processed in a prior run" });
          return;
        }

        const extraction = await extractMemory({
          source: event.source,
          actorDisplayName: event.actor.display_name,
          threadRef: event.thread_ref,
          permissionScope: event.permission_scope,
          rawContent: event.raw_content,
          occurredAt: event.occurred_at,
        });

        if (extraction.decision === "DISCARD" || !extraction.type) {
          results.push({ event_source_id: event.source_id, event_source: event.source, outcome: "discarded" });
          return;
        }

        const missing = validatePayloadForType(extraction.type, extraction.payload);
        if (missing.length > 0) {
          results.push({
            event_source_id: event.source_id, event_source: event.source,
            outcome: "invalid_payload", detail: `missing payload fields for ${extraction.type}: ${missing.join(", ")}`,
          });
          return;
        }

        // Batch 2 real entity resolution: exact match -> embedding
        // similarity -> queue for review, never silently auto-create.
        const entityIds: string[] = [];
        const queuedUnresolvedIds: string[] = [];
        for (const mention of extraction.entities) {
          const resolved = await resolveEntityMention(sql, tenantId, mention.mention_text, mention.entity_type_guess);
          if (resolved.entityId) entityIds.push(resolved.entityId);
          else if (resolved.unresolvedId) queuedUnresolvedIds.push(resolved.unresolvedId);
        }

        const searchableText = `${extraction.type}: ${extraction.title}\n${extraction.summary}`;

        try {
          const memoryId = await writeMemory(sql, {
            tenantId,
            type: extraction.type,
            title: extraction.title ?? "",
            summary: extraction.summary ?? "",
            payload: { ...extraction.payload, attribute_key: extraction.attribute_key },
            entityIds,
            occurredAt: event.occurred_at,
            validFrom: extraction.valid_from ?? event.occurred_at,
            confidence: extraction.confidence,
            searchableText,
            sourceEventIds: [fixtureEventId],
            citations: [{ fixtureEventId, excerptRef: "full-content" }],
          });

          const embedding = await embedText(searchableText, "document");
          await sql`
            insert into public.memory_embeddings (memory_id, tenant_id, embedding, embedding_model)
            values (${memoryId}, ${tenantId}, ${JSON.stringify(embedding)}, 'voyage-4-large')
            on conflict (memory_id) do update set embedding = excluded.embedding
          `;

          // Now that memoryId actually exists, backfill it onto whichever
          // mentions above got queued for review instead of auto-matched -
          // see linkQueuedMentionsToMemory's own comment for why this can't
          // happen at resolution time.
          await linkQueuedMentionsToMemory(sql, queuedUnresolvedIds, memoryId);

          const conflictResults = extraction.attribute_key ? await detectConflicts(sql, tenantId, memoryId) : [];

          results.push({
            event_source_id: event.source_id, event_source: event.source,
            outcome: "memory_created", memory_id: memoryId, memory_type: extraction.type as MemoryType,
            queued_entity_mentions: queuedUnresolvedIds.length,
            reconciliation: conflictResults.map((r) => ({ relation: r.relation, candidate_memory_id: r.candidateMemoryId })),
          });
        } catch (err) {
          if (err instanceof ZeroSourceEventsError) {
            results.push({ event_source_id: event.source_id, event_source: event.source, outcome: "rejected_zero_sources" });
          } else {
            throw err;
          }
        }
      });
    } catch (err) {
      console.error(`fixtures/load: failed on ${event.source}:${event.source_id}:`, err);
      results.push({
        event_source_id: event.source_id, event_source: event.source,
        outcome: "error", detail: err instanceof Error ? err.message : String(err),
      });
    }
  }

  const summary = results.reduce((acc, r) => {
    acc[r.outcome] = (acc[r.outcome] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return json({ tenant_id: tenantId, fixture_set: body.fixture_set, total_events: events.length, summary, results });
}

// Small debug helper - which tenants actually have raw_events to replay,
// so Checkpoint A verification can pick a real one without needing raw SQL
// access. Read-only, admin pool, no mutation.
async function handleDebugTenants(): Promise<Response> {
  const rows = await withAdmin(async (sql) => {
    return await sql`
      select t.id as tenant_id, t.name, count(re.id)::int as raw_event_count,
             count(re.id) filter (where re.source = 'slack')::int as slack_count,
             count(re.id) filter (where re.source = 'gmail')::int as gmail_count,
             count(re.id) filter (where re.source = 'notion')::int as notion_count
      from public.tenants t
      left join public.raw_events re on re.tenant_id = t.id
      group by t.id, t.name
      order by count(re.id) desc
      limit 20
    `;
  });
  return json({ tenants: rows });
}

// Read-only summary of what's actually been written for a tenant -
// verification helper for Checkpoint A/B, not a permanent product endpoint.
async function handleDebugMemories(tenantId: string): Promise<Response> {
  const rows = await withTenant(tenantId, async (sql) => {
    return await sql`
      select m.type, count(*)::int as n,
             array_agg(distinct mfe.source) as sources
      from public.memories m
      join public.memory_source_events mse on mse.memory_id = m.memory_id
      join public.memory_fixture_events mfe on mfe.id = mse.fixture_event_id
      where m.tenant_id = ${tenantId}
      group by m.type
      order by n desc
    `;
  });
  const sample = await withTenant(tenantId, async (sql) => {
    return await sql`
      select memory_id, type, title, summary, status, valid_from, confidence
      from public.memories where tenant_id = ${tenantId}
      order by created_at desc limit 10
    `;
  });
  const duplicateCheck = await withTenant(tenantId, async (sql) => {
    return await sql`
      select mfe.id as fixture_event_id, mfe.source, mfe.source_id,
             count(distinct mse.memory_id)::int as memory_count,
             array_agg(distinct mse.memory_id) as memory_ids
      from public.memory_fixture_events mfe
      join public.memory_source_events mse on mse.fixture_event_id = mfe.id
      where mfe.tenant_id = ${tenantId}
      group by mfe.id, mfe.source, mfe.source_id
      having count(distinct mse.memory_id) > 1
    `;
  });

  return json({ tenant_id: tenantId, counts_by_type: rows, recent_sample: sample, duplicate_memories_per_event: duplicateCheck });
}

// One-off cleanup utility for the duplicate memories the pre-fix bug
// created (see the "already processed" guard above) - deletes by explicit
// id list only, cascades through memory_entities/memory_source_events/
// memory_citations/memory_embeddings via their FKs. Not a general delete
// endpoint - intentionally narrow.
async function handleDebugDeleteMemories(req: Request): Promise<Response> {
  const body = await req.json() as { tenant_id?: string; memory_ids?: string[] };
  if (!body.tenant_id || !body.memory_ids?.length) {
    return json({ detail: "tenant_id and memory_ids[] are required" }, 400);
  }
  const deleted = await withTenant(body.tenant_id, async (sql) => {
    return await sql`
      delete from public.memories
      where tenant_id = ${body.tenant_id} and memory_id = any(${body.memory_ids})
      returning memory_id
    `;
  });
  return json({ deleted_count: deleted.length, deleted_ids: deleted.map((r: { memory_id: string }) => r.memory_id) });
}

// Live proof the zero-source-events guard actually fires, not just a code
// read - calls the real writeMemory() with an empty source list and
// reports whether it threw ZeroSourceEventsError, and confirms nothing
// landed in public.memories as a result.
async function handleDebugZeroSourceTest(req: Request): Promise<Response> {
  const body = await req.json() as { tenant_id?: string };
  if (!body.tenant_id) return json({ detail: "tenant_id is required" }, 400);
  const tenantId = body.tenant_id;

  let threw: string | null = null;
  try {
    await withTenant(tenantId, async (sql) => {
      await writeMemory(sql, {
        tenantId,
        type: "Context",
        title: "debug zero-source-events test - should never persist",
        summary: "debug zero-source-events test - should never persist",
        payload: { attribute_key: "debug-zero-source-test" },
        entityIds: [],
        occurredAt: new Date().toISOString(),
        validFrom: new Date().toISOString(),
        confidence: 0.5,
        searchableText: "debug zero-source-events test",
        sourceEventIds: [], // <- the thing being tested
        citations: [],
      });
    });
  } catch (err) {
    threw = err instanceof ZeroSourceEventsError ? "ZeroSourceEventsError" : `unexpected: ${err instanceof Error ? err.message : String(err)}`;
  }

  const leaked = await withTenant(tenantId, async (sql) => {
    return await sql`select memory_id from public.memories where title = 'debug zero-source-events test - should never persist'`;
  });

  return json({ threw, leaked_rows: leaked.length, guard_worked: threw === "ZeroSourceEventsError" && leaked.length === 0 });
}

// ── Entity review queue ───────────────────────────────────────────────

async function handleListUnresolvedEntities(tenantId: string): Promise<Response> {
  const rows = await withTenant(tenantId, async (sql) => {
    return await sql`
      select ue.id, ue.mention_text, ue.entity_type_guess, ue.candidate_score, ue.status,
             e.canonical_name as candidate_name
      from public.unresolved_entities ue
      left join public.entities e on e.entity_id = ue.candidate_entity_id
      where ue.tenant_id = ${tenantId} and ue.status = 'pending'
      order by ue.created_at desc
    `;
  });
  return json({ tenant_id: tenantId, pending: rows });
}

async function handleConfirmNewEntity(req: Request): Promise<Response> {
  const body = await req.json() as { tenant_id?: string; unresolved_id?: string };
  if (!body.tenant_id || !body.unresolved_id) return json({ detail: "tenant_id and unresolved_id are required" }, 400);
  const entityId = await withTenant(body.tenant_id, (sql) => confirmNewEntity(sql, body.tenant_id!, body.unresolved_id!));
  return json({ entity_id: entityId });
}

async function handleMergeEntity(req: Request): Promise<Response> {
  const body = await req.json() as { tenant_id?: string; unresolved_id?: string; target_entity_id?: string };
  if (!body.tenant_id || !body.unresolved_id || !body.target_entity_id) {
    return json({ detail: "tenant_id, unresolved_id, and target_entity_id are required" }, 400);
  }
  await withTenant(body.tenant_id, (sql) => mergeIntoExistingEntity(sql, body.tenant_id!, body.unresolved_id!, body.target_entity_id!));
  return json({ merged: true });
}

// ── Batch 2 audits: reconcile what Batch 1's interim logic already did ──

// Runs the real embedding-similarity check pairwise over every entity a
// tenant already has (all of which, since Batch 2's resolver never
// auto-creates, were necessarily created by Batch 1's interim
// exact-match-or-create). Any pair clearing CANDIDATE_FLOOR gets queued
// into unresolved_entities as a merge candidate - see the plan's stated
// decision: Batch 2 reconciles retroactively, not just going forward.
async function handleAuditBatch1Entities(req: Request): Promise<Response> {
  const body = await req.json() as { tenant_id?: string };
  if (!body.tenant_id) return json({ detail: "tenant_id is required" }, 400);
  const tenantId = body.tenant_id;

  const result = await withTenant(tenantId, async (sql) => {
    // Batch 1's interim resolver (resolveOrCreateEntityExactMatch) never
    // wrote entity_embeddings - only Batch 2's real resolver does. Backfill
    // before comparing, otherwise every Batch-1-created entity would be
    // silently invisible to this audit (confirmed live: the first run of
    // this endpoint reported 0 entities checked against a tenant that
    // demonstrably has entities, purely because of this gap).
    const missingEmbeddings = await sql`
      select e.entity_id, e.canonical_name from public.entities e
      left join public.entity_embeddings ee on ee.entity_id = e.entity_id
      where e.tenant_id = ${tenantId} and ee.entity_id is null
    `;
    let backfilled = 0;
    for (const row of missingEmbeddings) {
      const embedding = await embedText(row.canonical_name, "document");
      await sql`
        insert into public.entity_embeddings (entity_id, tenant_id, embedding)
        values (${row.entity_id}, ${tenantId}, ${JSON.stringify(embedding)})
        on conflict (entity_id) do update set embedding = excluded.embedding
      `;
      backfilled++;
    }

    const entities = await sql`
      select e.entity_id, e.entity_type, e.canonical_name, ee.embedding
      from public.entities e
      join public.entity_embeddings ee on ee.entity_id = e.entity_id
      where e.tenant_id = ${tenantId}
    `;
    const CANDIDATE_FLOOR = 0.75;
    // Cosine similarity computed in memory, not one SQL round trip per
    // pair - O(n^2) DB calls timed out the edge function on the first
    // attempt at real scale. postgres.js returns pgvector columns as
    // strings like "[0.1,0.2,...]"; parse once per entity, not per pair.
    const parsedEmbeddings = entities.map((e: { embedding: string }) =>
      (typeof e.embedding === "string" ? JSON.parse(e.embedding) : e.embedding) as number[]
    );
    function cosineSimilarity(a: number[], b: number[]): number {
      let dot = 0, normA = 0, normB = 0;
      for (let k = 0; k < a.length; k++) { dot += a[k] * b[k]; normA += a[k] * a[k]; normB += b[k] * b[k]; }
      return dot / (Math.sqrt(normA) * Math.sqrt(normB));
    }

    const flagged: { entity_a: string; entity_b: string; similarity: number }[] = [];
    for (let i = 0; i < entities.length; i++) {
      for (let j = i + 1; j < entities.length; j++) {
        if (entities[i].entity_type !== entities[j].entity_type) continue;
        const similarity = cosineSimilarity(parsedEmbeddings[i], parsedEmbeddings[j]);
        if (similarity >= CANDIDATE_FLOOR) {
          flagged.push({ entity_a: entities[i].canonical_name, entity_b: entities[j].canonical_name, similarity });
          // on conflict: this endpoint used to have no dedup guard at all -
          // a second run against the same tenant silently re-inserted every
          // flagged pair again (found live: 39 real pairs had become 78
          // rows). idx_unresolved_entities_audit_dedup makes a re-run a
          // no-op instead of a duplicate.
          await sql`
            insert into public.unresolved_entities (tenant_id, mention_text, entity_type_guess, candidate_entity_id, candidate_score, status)
            values (${tenantId}, ${entities[j].canonical_name}, ${entities[j].entity_type}, ${entities[i].entity_id}, ${similarity}, 'pending')
            on conflict (tenant_id, mention_text, candidate_entity_id) where status = 'pending' and memory_id is null and candidate_entity_id is not null
            do nothing
          `;
        }
      }
    }
    return { total_entities_checked: entities.length, embeddings_backfilled: backfilled, flagged_pairs: flagged };
  });

  return json(result);
}

// Read-only. Every real decisions row where superseded_by is not null was
// set exclusively by ai-worker's duplicate-auto-merge (the Python
// /correct "edited" path that also sets it was never ported to Deno - see
// plan's flagged assumption). Reconstructs each pair and runs the NEW
// classifyRelation over it to see how many historical silent merges look
// like real conflicts under the corrected logic. Writes nothing back to
// decisions.
async function handleAuditHistoricalDuplicates(req: Request): Promise<Response> {
  const body = await req.json() as { tenant_id?: string; limit?: number };
  if (!body.tenant_id) return json({ detail: "tenant_id is required" }, 400);
  const tenantId = body.tenant_id;
  const limit = body.limit ?? 15;

  const pairs = await withAdmin(async (sql) => {
    return await sql`
      select old.id as old_id, old.decision_statement as old_statement, old.rationale as old_rationale, old.created_at as old_created_at,
             new.id as new_id, new.decision_statement as new_statement, new.rationale as new_rationale, new.created_at as new_created_at
      from public.decisions old
      join public.decisions new on new.id = old.superseded_by
      where old.tenant_id = ${tenantId}
      limit ${limit}
    `;
  });

  const audited = [];
  for (const pair of pairs) {
    const classifications = await classifyRelation(
      { title: pair.new_statement, summary: pair.new_rationale ?? "", valid_from: new Date(pair.new_created_at).toISOString() },
      [{ memory_id: pair.old_id, title: pair.old_statement, summary: pair.old_rationale ?? "", valid_from: new Date(pair.old_created_at).toISOString() }],
    );
    audited.push({
      old_decision_id: pair.old_id, new_decision_id: pair.new_id,
      old_statement: pair.old_statement, new_statement: pair.new_statement,
      new_classification: classifications[0]?.relationship ?? "no_classification_returned",
      reason: classifications[0]?.reason ?? null,
    });
  }

  const summary = audited.reduce((acc, a) => {
    acc[a.new_classification] = (acc[a.new_classification] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return json({ tenant_id: tenantId, pairs_examined: audited.length, summary, audited });
}

// Spec Section 12's golden evaluation set, run for real. Exists as an
// endpoint (not just the deno-run CLI script in _shared/memory/eval/) so
// it runs where ANTHROPIC_API_KEY is actually configured - a local shell
// doesn't have it, this deployed function does. No tenant_id needed: every
// case is self-contained (hand-built fixtures or synthetic memories), not
// tied to any real tenant's data.
async function handleRunGoldenEval(): Promise<Response> {
  const report = await runGoldenEval();
  return json(report);
}

// Deterministic test of reconciliation itself, decoupled from extraction's
// own (somewhat unpredictable) type/attribute_key choices - writes three
// synthetic same-type memories directly (bypassing extraction) matching
// the spec's own worked example, and reports what detectConflicts actually
// did to each.
async function handleDebugTestReconciliation(req: Request): Promise<Response> {
  const body = await req.json() as { tenant_id?: string };
  if (!body.tenant_id) return json({ detail: "tenant_id is required" }, 400);
  const tenantId = body.tenant_id;

  const events = await withTenant(tenantId, async (sql) => {
    const ev1 = await sql`
      insert into public.memory_fixture_events (tenant_id, source, source_id, actor_display_name, permission_scope, raw_content, occurred_at)
      values (${tenantId}, 'slack', 'debug-recon-1-' || extract(epoch from now()), 'Test', '{}', 'debug event 1', now()) returning id`;
    const ev2 = await sql`
      insert into public.memory_fixture_events (tenant_id, source, source_id, actor_display_name, permission_scope, raw_content, occurred_at)
      values (${tenantId}, 'slack', 'debug-recon-2-' || extract(epoch from now()), 'Test', '{}', 'debug event 2', now()) returning id`;
    const ev3 = await sql`
      insert into public.memory_fixture_events (tenant_id, source, source_id, actor_display_name, permission_scope, raw_content, occurred_at)
      values (${tenantId}, 'slack', 'debug-recon-3-' || extract(epoch from now()), 'Test', '{}', 'debug event 3', now()) returning id`;
    return { ev1: ev1[0].id, ev2: ev2[0].id, ev3: ev3[0].id };
  });

  const outcomes: Record<string, unknown> = {};

  await withTenant(tenantId, async (sql) => {
    // The spec's own candidate query requires a SHARED entity, not just
    // matching type+attribute_key (spec Section 6: "m.entities.some(e =>
    // newMemory.entities.some(...))") - each scenario needs its own shared
    // entity so detectConflicts can find its candidates at all.
    const projectEntity = await sql`
      insert into public.entities (tenant_id, entity_type, canonical_name) values (${tenantId}, 'Project', 'debug-recon-project-x')
      on conflict (tenant_id, entity_type, canonical_name) do update set canonical_name = excluded.canonical_name returning entity_id`;
    const pricingEntity = await sql`
      insert into public.entities (tenant_id, entity_type, canonical_name) values (${tenantId}, 'Topic', 'debug-recon-pricing')
      on conflict (tenant_id, entity_type, canonical_name) do update set canonical_name = excluded.canonical_name returning entity_id`;
    const projectEntityId = projectEntity[0].entity_id as string;
    const pricingEntityId = pricingEntity[0].entity_id as string;

    // Memory 1: beta start date - DIFFERENT attribute_key (but same entity),
    // should never become a candidate for memory 2/3 (structural
    // different_concept - excluded by attribute_key, not entity).
    const beta = await writeMemory(sql, {
      tenantId, type: "Decision", title: "Beta starts September 10th", summary: "Beta program starts Sep 10",
      payload: { attribute_key: "beta-start-date", decision_status: "decided", alternatives_considered: [] },
      entityIds: [projectEntityId], occurredAt: new Date().toISOString(), validFrom: new Date().toISOString(),
      confidence: 0.9, searchableText: "Decision: Beta starts September 10th",
      sourceEventIds: [events.ev1], citations: [],
    });
    outcomes.beta_memory_id = beta;

    // Memory 2: public launch, first claim.
    const launch1 = await writeMemory(sql, {
      tenantId, type: "Decision", title: "Public launch is September 1st", summary: "Public launch date set to Sep 1",
      payload: { attribute_key: "public-launch-date", decision_status: "decided", alternatives_considered: [] },
      entityIds: [projectEntityId], occurredAt: new Date(Date.now() - 60_000).toISOString(), validFrom: new Date(Date.now() - 60_000).toISOString(),
      confidence: 0.9, searchableText: "Decision: Public launch is September 1st",
      sourceEventIds: [events.ev2], citations: [],
    });
    outcomes.launch1_memory_id = launch1;

    // Memory 3: public launch, explicitly framed as a correction -> should
    // classify as "update" (same fact, natural evolution) against memory 2,
    // and never even be compared against memory 1 (different attribute_key).
    const launch2 = await writeMemory(sql, {
      tenantId, type: "Decision", title: "Public launch pushed back to September 15th",
      summary: "We're pushing the public launch from September 1st to September 15th because QA found a blocking issue that needs another week.",
      payload: { attribute_key: "public-launch-date", decision_status: "decided", alternatives_considered: [] },
      entityIds: [projectEntityId], occurredAt: new Date().toISOString(), validFrom: new Date().toISOString(),
      confidence: 0.9, searchableText: "Decision: Public launch pushed back to September 15th",
      sourceEventIds: [events.ev3], citations: [],
    });
    outcomes.launch2_memory_id = launch2;
    outcomes.launch2_vs_launch1 = await detectConflicts(sql, tenantId, launch2);

    // Memory 4: a genuine conflict - two equally-confident, unreconciled
    // claims about the same attribute, neither framed as correcting the
    // other.
    const conflictA = await writeMemory(sql, {
      tenantId, type: "Decision", title: "The pricing model will be usage-based", summary: "Team decided on usage-based pricing.",
      payload: { attribute_key: "pricing-model", decision_status: "decided", alternatives_considered: [] },
      entityIds: [pricingEntityId], occurredAt: new Date(Date.now() - 30_000).toISOString(), validFrom: new Date(Date.now() - 30_000).toISOString(),
      confidence: 0.85, searchableText: "Decision: pricing model usage-based",
      sourceEventIds: [events.ev1], citations: [],
    });
    const conflictB = await writeMemory(sql, {
      tenantId, type: "Decision", title: "The pricing model will be flat-rate", summary: "Team decided on flat-rate pricing.",
      payload: { attribute_key: "pricing-model", decision_status: "decided", alternatives_considered: [] },
      entityIds: [pricingEntityId], occurredAt: new Date(Date.now() - 30_000).toISOString(), validFrom: new Date(Date.now() - 30_000).toISOString(),
      confidence: 0.85, searchableText: "Decision: pricing model flat-rate",
      sourceEventIds: [events.ev2], citations: [],
    });
    outcomes.conflict_a_id = conflictA;
    outcomes.conflict_b_id = conflictB;
    outcomes.conflict_b_vs_a = await detectConflicts(sql, tenantId, conflictB);

    const finalStates = await sql`
      select memory_id, title, status, supersedes from public.memories
      where memory_id = any(${[beta, launch1, launch2, conflictA, conflictB]})
    `;
    outcomes.final_states = finalStates;
  });

  return json(outcomes);
}

// ── Real-user-facing endpoints (Memory Timeline, evidence drawer) ───────
//
// Everything above this line is admin/debug/fixture-loading and gated on
// requireServiceRole (the key that never ships to a browser). These two
// are the opposite: they're what the actual frontend, logged in as a real
// tenant member, calls - so they authenticate with the SAME app-issued
// tenant JWT api/index.ts's /search and /digest already accept
// (getCurrentTenant, from _shared/tenantAuth.ts), not the service role key.
//
// isMemoryAccessible() is re-run fresh on every call here, never cached
// from write time or from a prior request - the fail-closed default only
// means something if a scope that later gets real source_scope_members
// data starts resolving to "accessible" the moment that data lands,
// without anything needing to be re-written.

async function handleListMemories(req: Request): Promise<Response> {
  const ctx = await getCurrentTenant(req);
  const url = new URL(req.url);
  const entityId = url.searchParams.get("entity_id") ?? undefined;

  const permissionScopes = await resolvePermissionScopes(ctx.userId, ctx.tenantId);
  // One pooled connection for both steps, not two - a fresh connection has
  // its own real setup cost, and the batched permission check doesn't need
  // a separate one now that it's a single query instead of N.
  const { memories, accessFlags } = await withTenant(ctx.tenantId, async (sql) => {
    const memories = await loadMemoriesForTenant(sql, ctx.tenantId, entityId);
    const accessFlags = await isMemoryAccessibleBatch(sql, ctx.tenantId, permissionScopes, memories.map((m) => m.permissions.visible_to));
    return { memories, accessFlags };
  });
  const visible = memories.filter((_, i) => accessFlags[i]);
  const hiddenCount = memories.length - visible.length;

  return json({
    memories: visible,
    hidden_count: hiddenCount,
    // Surfaced so the UI can show the disclosed "some content isn't shown
    // yet" note rather than silently looking like an empty/broken product -
    // per the plan's Checkpoint C requirement, this is never hidden from
    // the user.
    some_content_hidden: hiddenCount > 0,
  });
}

async function handleMemoryEvidence(req: Request, memoryId: string): Promise<Response> {
  const ctx = await getCurrentTenant(req);
  const permissionScopes = await resolvePermissionScopes(ctx.userId, ctx.tenantId);

  const { memory, accessible } = await withTenant(ctx.tenantId, async (sql) => {
    const memories = await loadMemoriesForTenant(sql, ctx.tenantId);
    const memory = memories.find((m) => m.memory_id === memoryId);
    if (!memory) return { memory: null, accessible: false };
    const accessible = await isMemoryAccessible(sql, ctx.tenantId, permissionScopes, memory.permissions.visible_to);
    return { memory, accessible };
  });
  if (!memory) return json({ detail: "Memory not found" }, 404);
  if (!accessible) return json({ detail: "Not accessible" }, 403);

  return json({
    memory_id: memory.memory_id,
    title: memory.title,
    summary: memory.summary,
    source_events: memory.source_events,
    citations: memory.citations,
    confidence: memory.confidence,
    freshness: memory.freshness,
    status: memory.status,
    supersedes: memory.supersedes,
  });
}

async function handleAttention(req: Request): Promise<Response> {
  const ctx = await getCurrentTenant(req);
  const url = new URL(req.url);
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 4), 1), 20);

  const permissionScopes = await resolvePermissionScopes(ctx.userId, ctx.tenantId);
  const accessible = await withTenant(ctx.tenantId, async (sql) => {
    const allMemories = await loadMemoriesForTenant(sql, ctx.tenantId);
    const accessFlags = await isMemoryAccessibleBatch(sql, ctx.tenantId, permissionScopes, allMemories.map((m) => m.permissions.visible_to));
    return allMemories.filter((_, i) => accessFlags[i]);
  });

  const result = getAttentionItems(accessible, limit);
  return json({
    items: result.items.map((item) => ({
      memory_id: item.memory.memory_id,
      title: item.memory.title,
      summary: item.memory.summary,
      type: item.memory.type,
      category: item.category,
      weight: item.weight,
      action: actionForCategory(item.category),
    })),
    total: result.total,
  });
}

async function handleResolveMemory(req: Request, memoryId: string): Promise<Response> {
  const ctx = await getCurrentTenant(req);
  const permissionScopes = await resolvePermissionScopes(ctx.userId, ctx.tenantId);

  let body: { action?: ResolutionAction; note?: string };
  try {
    body = await req.json();
  } catch {
    return json({ detail: "Invalid JSON body" }, 400);
  }
  const validActions: ResolutionAction[] = ["confirm_decision", "check_in_commitment", "recheck_freshness", "dismiss_conflict"];
  if (!body.action || !validActions.includes(body.action)) {
    return json({ detail: `action must be one of ${validActions.join(", ")}` }, 400);
  }

  try {
    const outcome = await withTenant(ctx.tenantId, async (sql) => {
      const memories = await loadMemoriesForTenant(sql, ctx.tenantId);
      const memory = memories.find((m) => m.memory_id === memoryId);
      if (!memory) return "not_found" as const;
      const accessible = await isMemoryAccessible(sql, ctx.tenantId, permissionScopes, memory.permissions.visible_to);
      if (!accessible) return "not_accessible" as const;
      await resolveMemory(sql, ctx.tenantId, memoryId, body.action as ResolutionAction, body.note ?? null, null);
      return "resolved" as const;
    });
    if (outcome === "not_found") return json({ detail: "Memory not found" }, 404);
    if (outcome === "not_accessible") return json({ detail: "Not accessible" }, 403);
  } catch (err) {
    if (err instanceof MemoryNotAccessibleError) return json({ detail: err.message }, 404);
    throw err;
  }

  return json({ memory_id: memoryId, action: body.action, resolved: true });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  const url = new URL(req.url);
  const path = url.pathname;

  const evidenceMatch = path.match(/\/memories\/([0-9a-f-]{36})\/evidence$/i);
  const resolveMatch = path.match(/\/memories\/([0-9a-f-]{36})\/resolve$/i);

  try {
    // Real-user routes: their own JWT check, not the service-role gate.
    if (path.endsWith("/memories") && req.method === "GET") {
      try {
        return await handleListMemories(req);
      } catch (err) {
        return json({ detail: err instanceof Error ? err.message : "Unauthorized" }, 401);
      }
    }
    if (evidenceMatch && req.method === "GET") {
      try {
        return await handleMemoryEvidence(req, evidenceMatch[1]);
      } catch (err) {
        return json({ detail: err instanceof Error ? err.message : "Unauthorized" }, 401);
      }
    }
    if (path.endsWith("/attention") && req.method === "GET") {
      try {
        return await handleAttention(req);
      } catch (err) {
        return json({ detail: err instanceof Error ? err.message : "Unauthorized" }, 401);
      }
    }
    if (resolveMatch && req.method === "POST") {
      try {
        return await handleResolveMemory(req, resolveMatch[1]);
      } catch (err) {
        return json({ detail: err instanceof Error ? err.message : "Unauthorized" }, 401);
      }
    }

    // Everything else is admin/debug/fixture-loading - service-role only.
    const authError = requireServiceRole(req);
    if (authError) return authError;

    if (path.endsWith("/fixtures/load") && req.method === "POST") return await handleFixturesLoad(req);
    if (path.endsWith("/debug/tenants") && req.method === "GET") return await handleDebugTenants();
    if (path.endsWith("/debug/memories") && req.method === "GET") {
      const tenantId = url.searchParams.get("tenant_id");
      if (!tenantId) return json({ detail: "tenant_id query param required" }, 400);
      return await handleDebugMemories(tenantId);
    }
    if (path.endsWith("/debug/delete-memories") && req.method === "POST") return await handleDebugDeleteMemories(req);
    if (path.endsWith("/debug/test-zero-source-guard") && req.method === "POST") return await handleDebugZeroSourceTest(req);
    if (path.endsWith("/debug/entities") && req.method === "GET") {
      const tenantId = url.searchParams.get("tenant_id");
      if (!tenantId) return json({ detail: "tenant_id query param required" }, 400);
      const rows = await withTenant(tenantId, (sql) => sql`select entity_id, entity_type, canonical_name from public.entities where tenant_id = ${tenantId} order by canonical_name`);
      return json({ tenant_id: tenantId, count: rows.length, entities: rows });
    }
    if (path.endsWith("/entities/unresolved") && req.method === "GET") {
      const tenantId = url.searchParams.get("tenant_id");
      if (!tenantId) return json({ detail: "tenant_id query param required" }, 400);
      return await handleListUnresolvedEntities(tenantId);
    }
    if (path.endsWith("/entities/confirm-new") && req.method === "POST") return await handleConfirmNewEntity(req);
    if (path.endsWith("/entities/merge") && req.method === "POST") return await handleMergeEntity(req);
    if (path.endsWith("/audit/batch1-entities") && req.method === "POST") return await handleAuditBatch1Entities(req);
    if (path.endsWith("/audit/historical-duplicates") && req.method === "POST") return await handleAuditHistoricalDuplicates(req);
    if (path.endsWith("/eval/run") && req.method === "POST") return await handleRunGoldenEval();
    if (path.endsWith("/debug/test-reconciliation") && req.method === "POST") return await handleDebugTestReconciliation(req);
    return json({ detail: "Not found" }, 404);
  } catch (err) {
    console.error("memory-api unhandled error:", err);
    return json({ detail: err instanceof Error ? err.message : "Internal error" }, 500);
  }
});
