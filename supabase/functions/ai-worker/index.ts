// supabase/functions/ai-worker/index.ts
//
// Deno port of the Python ingestion + embedding workers (backend/src/queues/
// workers/event_worker.py, embedding_worker.py, and the AI pipeline modules
// they call). Railway's worker service kept failing under resource
// starvation (see commit history around 2026-08-02) with the account nearly
// out of credits, and Vercel/Supabase Edge Functions can't run a
// continuously-looping process, so this runs the same pipeline as a short,
// bounded burst triggered by pg_cron every minute instead of an infinite
// while loop. Same pgmq read -> process -> delete-on-success contract, same
// tenant isolation (withTenant sets app.current_tenant_id, matching
// database.tenant_connection.tenant_conn on the Python side), same
// dedup/retry semantics (pipeline_status column, see migration 017 and
// modules.ingestion.dedup.ledger's docstring for why bare row-existence is
// never treated as "already processed").
//
// One invocation processes up to BATCH_SIZE ingestion messages and
// BATCH_SIZE embedding jobs, concurrently within each stage, then returns.
// No infinite loop - the cron interval is the poll loop.

import { withAdmin, withTenant } from "../_shared/db.ts";

const corsHeaders = { "Access-Control-Allow-Origin": "*" };

// ── Config ──────────────────────────────────────────────────────────────

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const TRIAGE_MODEL = Deno.env.get("ANTHROPIC_TRIAGE_MODEL") ?? "claude-haiku-4-5-20251001";
const EXTRACT_MODEL = Deno.env.get("ANTHROPIC_EXTRACT_MODEL") ?? "claude-haiku-4-5-20251001";
const VOYAGE_API_KEY = Deno.env.get("VOYAGE_API_KEY") ?? "";
const VOYAGE_MODEL = Deno.env.get("VOYAGE_EMBED_MODEL") ?? "voyage-4-large";
const VOYAGE_OUTPUT_DIMENSION = 1024;

const INGESTION_BATCH = 40;
const EMBEDDING_BATCH = 40;
const CONCURRENCY = 8;
const VISIBILITY_TIMEOUT_SECONDS = 60;

// ── Encryption (matches modules.security.encryption exactly) ─────────────
// AES-256-GCM, key = SHA-256(secret), blob = "LOCUS1" + 12-byte nonce +
// ciphertext(+16-byte GCM tag, which Web Crypto appends the same way
// Python's `cryptography` package does) - byte-for-byte compatible so rows
// written by this function decrypt fine in the Python backend and vice versa.

const MAGIC = new TextEncoder().encode("LOCUS1"); // 6 bytes
const NONCE_LEN = 12;

async function getAesKey(): Promise<CryptoKey> {
  const secret = Deno.env.get("RAW_EVENTS_ENCRYPTION_KEY") || Deno.env.get("APP_SECRET_KEY");
  if (!secret) {
    throw new Error("RAW_EVENTS_ENCRYPTION_KEY or APP_SECRET_KEY is not set");
  }
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret));
  return crypto.subtle.importKey("raw", hash, "AES-GCM", false, ["encrypt", "decrypt"]);
}

async function encryptRawContent(plaintext: Uint8Array): Promise<Uint8Array> {
  const key = await getAesKey();
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_LEN));
  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, plaintext),
  );
  const out = new Uint8Array(MAGIC.length + NONCE_LEN + ciphertext.length);
  out.set(MAGIC, 0);
  out.set(nonce, MAGIC.length);
  out.set(ciphertext, MAGIC.length + NONCE_LEN);
  return out;
}

// ── fetch() with a hard timeout ───────────────────────────────────────────
// Plain fetch() never times out on its own - if Anthropic or Voyage ever
// stalls mid-request, an un-timed-out call hangs for the life of the
// invocation. Confirmed live: a handful of messages sat retrying for over
// 30 minutes with pgmq's visibility timeout (60s) repeatedly expiring mid-
// hang, letting overlapping invocations pile up on the same messages
// forever without any one of them ever finishing cleanly. The Python
// worker this replaced always set an explicit request timeout (15s triage,
// 30s extraction via the Anthropic SDK's `timeout` param) - this restores
// that same guarantee so a stalled call fails fast and leaves the message
// for pgmq's own retry instead of hanging indefinitely.
async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(`Request to ${url} timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// ── Anthropic (forced tool-use, matches modules.ai.triage/extraction) ────

async function callClaude(
  system: string,
  userMessage: string,
  tool: Record<string, unknown>,
  toolName: string,
  maxTokens: number,
  model: string,
  timeoutMs: number,
): Promise<Record<string, unknown>> {
  const resp = await fetchWithTimeout("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      temperature: 0,
      system,
      messages: [{ role: "user", content: userMessage }],
      tools: [tool],
      tool_choice: { type: "tool", name: toolName },
    }),
  }, timeoutMs);
  if (!resp.ok) {
    throw new Error(`Anthropic API error ${resp.status}: ${await resp.text()}`);
  }
  const data = await resp.json();
  const block = (data.content ?? []).find((b: { type?: string }) => b.type === "tool_use");
  if (!block) throw new Error(`Claude did not return a tool_use block for ${toolName}`);
  return block.input as Record<string, unknown>;
}

const TRIAGE_SYSTEM_PROMPT = `You are the triage stage of Locus AI, a decision-intelligence system that extracts durable decisions, action items, and blockers from day-to-day workplace communication (Slack, Gmail, Notion).

Your only job is to classify ONE event as KEEP, UNCERTAIN, or DISCARD, using only the text of that event below. Do not infer facts, participants, prior messages, or outcomes that are not stated in the event itself - you have no access to surrounding conversation or any other context.

Decision rules:

KEEP - the event contains at least one of:
  - a clear decision that was made
  - an action item with an identifiable owner or commitment
  - a blocker that is preventing progress
  - a confirmed change (e.g. to a plan, schedule, scope, or system)
  - an ownership assignment or deadline
  - an operational commitment ("we will...", "I'll have this done by...")

UNCERTAIN - the event might matter but is incomplete on its own:
  - a tentative proposal that has not been confirmed
  - something explicitly awaiting approval or sign-off
  - language that is ambiguous about whether a decision was actually reached
  - a statement whose relevance depends on missing context you don't have
  When you cannot confidently tell whether an event is KEEP or DISCARD, choose UNCERTAIN. Never guess DISCARD just because you are unsure.

DISCARD - the event is clearly NOT decision-relevant:
  - a greeting, thank-you, or other social chatter
  - an emoji reaction or acknowledgement with no new content
  - a newsletter, digest, or marketing content
  - a reminder or automated/bot notification
  - spam
  - content unrelated to any decision, action item, or blocker

Do not classify by keyword-matching alone. Call the record_triage_result tool exactly once with your decision, a confidence score between 0 and 1, and the single reason_code that best explains your decision.`;

const TRIAGE_TOOL = {
  name: "record_triage_result",
  description: "Record the triage decision for one event.",
  input_schema: {
    type: "object",
    properties: {
      decision: { type: "string", enum: ["KEEP", "UNCERTAIN", "DISCARD"] },
      confidence: { type: "number", minimum: 0, maximum: 1 },
      reason_code: {
        type: "string",
        enum: [
          "EXPLICIT_DECISION", "ACTION_ASSIGNED", "BLOCKER_IDENTIFIED", "CONFIRMED_CHANGE",
          "TENTATIVE_PROPOSAL", "AWAITING_APPROVAL", "INSUFFICIENT_CONTEXT",
          "SOCIAL_CHATTER", "AUTOMATED_NOTIFICATION", "UNRELATED_CONTENT",
        ],
      },
    },
    required: ["decision", "confidence", "reason_code"],
    additionalProperties: false,
  },
};

const EXTRACTION_SYSTEM_PROMPT = `You are the extraction stage of Locus AI, a decision-intelligence system that turns workplace communication (Slack, Gmail, Notion) into a durable record of decisions, action items, and blockers.

You will be given ONE event that has already been judged worth extracting. Using only the text of that event, extract exactly one record: a decision, an action item, or a blocker.

Ground rules - extract only what is explicitly present:
  - decision_statement: state the decision, action, or blocker in the event's own terms. Do not add detail, context, or consequences that are not stated.
  - status: "decided" only if the event states the decision/action is final or confirmed. "proposed" if it is tentative, suggested, or awaiting approval. "superseded" only if the event explicitly says a prior decision was replaced or reversed.
  - rationale: the reason given, in the event's own terms. If no reason is stated, return null. Never invent a plausible-sounding rationale.
  - alternatives_considered: other options explicitly mentioned as considered or rejected. Empty list if none mentioned.
  - actors: people explicitly named in connection with this record. role "decided_by" (at most one) if the event explicitly states this person made the decision/owns the item/is responsible for the blocker. role "mentioned" otherwise. Empty list if no actor is named. Never invent or guess an owner.
  - confidence: 0-1, based only on how explicit and unambiguous the text is.

Call the record_extraction_result tool exactly once with the extracted record.`;

const EXTRACTION_TOOL = {
  name: "record_extraction_result",
  description: "Record the single decision, action item, or blocker extracted from one event.",
  input_schema: {
    type: "object",
    properties: {
      record_type: { type: "string", enum: ["decision", "action_item", "blocker"] },
      status: { type: "string", enum: ["proposed", "decided", "superseded"] },
      decision_statement: { type: "string", minLength: 1 },
      rationale: { type: ["string", "null"] },
      alternatives_considered: { type: "array", items: { type: "string" } },
      actors: {
        type: "array",
        items: {
          type: "object",
          properties: {
            source_actor_id: { type: "string", minLength: 1 },
            role: { type: "string", enum: ["decided_by", "mentioned"] },
          },
          required: ["source_actor_id", "role"],
          additionalProperties: false,
        },
      },
      confidence: { type: "number", minimum: 0, maximum: 1 },
    },
    required: ["record_type", "status", "decision_statement", "alternatives_considered", "actors", "confidence"],
    additionalProperties: false,
  },
};

function buildEventUserMessage(event: {
  source: string; actor: string; thread_ref?: string | null;
  permission_scope: string[]; raw_content: unknown;
}): string {
  const threadRef = event.thread_ref || "(none)";
  return `source: ${event.source}\nactor: ${event.actor}\nthread_ref: ${threadRef}\npermission_scope: ${JSON.stringify(event.permission_scope)}\ncontent:\n${JSON.stringify(event.raw_content)}`;
}

// ── Voyage embeddings (matches modules.ai.embeddings.provider.embed_document) ──

async function embedDocument(text: string): Promise<number[]> {
  const resp = await fetchWithTimeout("https://api.voyageai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${VOYAGE_API_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      input: [text],
      model: VOYAGE_MODEL,
      input_type: "document",
      output_dimension: VOYAGE_OUTPUT_DIMENSION,
      truncation: true,
    }),
  }, 30_000);
  if (!resp.ok) {
    throw new Error(`Voyage API error ${resp.status}: ${await resp.text()}`);
  }
  const data = await resp.json();
  const embedding = data.data?.[0]?.embedding;
  if (!Array.isArray(embedding) || embedding.length !== VOYAGE_OUTPUT_DIMENSION) {
    throw new Error(`Voyage returned an unexpected embedding shape`);
  }
  return embedding;
}

// ── Actor resolution (matches modules.decisions.pipeline_persistence) ────

const ACTOR_IDENTIFIER_COLUMN: Record<string, string> = {
  gmail: "email",
  slack: "slack_user_id",
  notion: "notion_user_id",
};

// deno-lint-ignore no-explicit-any
async function resolveActorId(
  sql: any, tenantId: string, source: string, sourceActorId: string, displayName?: string,
): Promise<string> {
  const column = ACTOR_IDENTIFIER_COLUMN[source];
  if (!column) throw new Error(`No actor identifier column for source=${source}`);

  if (column === "email") {
    // COALESCE keeps an existing real name rather than ever overwriting it
    // with null on a later message from the same sender that happens not
    // to carry a display name (e.g. a reply-only header, or a different
    // connector for the same address).
    const rows = await sql`
      INSERT INTO actors (tenant_id, email, display_name, kind)
      VALUES (${tenantId}, ${sourceActorId}, ${displayName ?? null}, 'internal')
      ON CONFLICT (tenant_id, email) DO UPDATE SET
        email = EXCLUDED.email,
        display_name = COALESCE(EXCLUDED.display_name, actors.display_name)
      RETURNING id
    `;
    return rows[0].id;
  }

  const existing = column === "slack_user_id"
    ? await sql`SELECT id FROM actors WHERE tenant_id = ${tenantId} AND slack_user_id = ${sourceActorId}`
    : await sql`SELECT id FROM actors WHERE tenant_id = ${tenantId} AND notion_user_id = ${sourceActorId}`;
  if (existing.length > 0) return existing[0].id;

  const created = column === "slack_user_id"
    ? await sql`INSERT INTO actors (tenant_id, slack_user_id, kind) VALUES (${tenantId}, ${sourceActorId}, 'internal') RETURNING id`
    : await sql`INSERT INTO actors (tenant_id, notion_user_id, kind) VALUES (${tenantId}, ${sourceActorId}, 'internal') RETURNING id`;
  return created[0].id;
}

// ── pgmq helpers (raw SQL, mirrors queues.pgmq.client) ────────────────────

type PgmqMsg = { msg_id: number; message: Record<string, unknown>; read_ct: number };

async function pgmqRead(queue: string, batch: number): Promise<PgmqMsg[]> {
  return await withAdmin(async (sql) => {
    const rows = await sql`SELECT * FROM pgmq.read(${queue}, ${VISIBILITY_TIMEOUT_SECONDS}, ${batch})`;
    return rows.map((r: { msg_id: number; message: Record<string, unknown>; read_ct: number }) => ({
      msg_id: r.msg_id, message: r.message, read_ct: r.read_ct,
    }));
  });
}

async function pgmqDelete(queue: string, msgId: number): Promise<void> {
  await withAdmin(async (sql) => {
    await sql`SELECT pgmq.delete(${queue}, ${msgId}::bigint)`;
  });
}

async function pgmqSend(queue: string, message: Record<string, unknown>): Promise<void> {
  await withAdmin(async (sql) => {
    await sql`SELECT pgmq.send(${queue}, ${sql.json(message)}::jsonb)`;
  });
}

// ── Ingestion pipeline (mirrors event_worker._handle_message) ────────────

// Signals a failure that will NEVER succeed on retry (e.g. the tenant
// disconnected this source after the message was already queued) - distinct
// from a transient failure (Claude API hiccup, DB blip), which should stay
// in the queue for pgmq's normal visibility-timeout retry. Without this
// distinction a message like this retries forever: confirmed live, a single
// stale message from a tenant that disconnected Gmail was read and failed
// over 1000 times across ~19 hours, standing between every other queued
// message and ever being processed (Deno reads in msg_id order).
class NonRetryableIngestionError extends Error {}

async function handleIngestionMessage(msg: PgmqMsg): Promise<string> {
  try {
    return await handleIngestionMessageInner(msg);
  } catch (err) {
    if (err instanceof NonRetryableIngestionError) {
      await pgmqDelete("ingestion", msg.msg_id);
      return "abandoned_no_active_connection";
    }
    throw err;
  }
}

async function handleIngestionMessageInner(msg: PgmqMsg): Promise<string> {
  const payload = msg.message as {
    tenant_id: string; source: string; source_id: string; actor: string;
    thread_ref?: string | null; permission_scope: string[]; raw_content: unknown;
    source_permalink?: string | null; received_at: string; actor_display_name?: string;
  };
  const tenantId = payload.tenant_id;

  // is_duplicate(): only a row already marked pipeline_status='done' counts
  // as truly seen - a 'pending' row means a prior attempt crashed mid-flight
  // and deserves a real retry (see migration 017's docstring).
  const isDuplicate = await withTenant(tenantId, async (sql) => {
    const rows = await sql`
      SELECT 1 FROM public.raw_events
      WHERE tenant_id = ${tenantId} AND source = ${payload.source} AND source_id = ${payload.source_id}
        AND pipeline_status = 'done'
    `;
    return rows.length > 0;
  });
  if (isDuplicate) {
    await pgmqDelete("ingestion", msg.msg_id);
    return "duplicate_skipped";
  }

  // store_raw_event(): insert, or on conflict, return the existing id if
  // it's still pending (retry), only a truly-done row is a real duplicate.
  const plaintext = new TextEncoder().encode(JSON.stringify(payload));
  const encrypted = await encryptRawContent(plaintext);
  const metadata = JSON.stringify({ ingested_via: "ai-worker-deno", encrypted: true });

  const rawEventId = await withTenant(tenantId, async (sql) => {
    const connRows = await sql`
      SELECT id FROM public.source_connections
      WHERE tenant_id = ${tenantId} AND source = ${payload.source} AND status = 'active'
      ORDER BY created_at ASC LIMIT 1
    `;
    if (connRows.length === 0) {
      // Non-retryable: this tenant no longer has an active connection for
      // this source (they disconnected it after this message was already
      // queued). It will never become active again on its own, so retrying
      // is pure waste - the caller deletes the message instead of leaving
      // it to retry forever.
      throw new NonRetryableIngestionError(
        `No active source_connections row for tenant=${tenantId} source=${payload.source}`,
      );
    }
    const connectionId = connRows[0].id;

    const inserted = await sql`
      INSERT INTO public.raw_events (
        tenant_id, connection_id, source, source_id, thread_ref,
        permission_scope, raw_content, metadata, triage_result, received_at
      ) VALUES (
        ${tenantId}, ${connectionId}, ${payload.source}, ${payload.source_id},
        ${payload.thread_ref ?? null}, ${payload.permission_scope ?? []},
        ${encrypted}, ${metadata}::jsonb, 'pending', ${payload.received_at}
      )
      ON CONFLICT (tenant_id, source, source_id) DO NOTHING
      RETURNING id
    `;
    if (inserted.length > 0) return inserted[0].id as string;

    const existing = await sql`
      SELECT id, pipeline_status FROM public.raw_events
      WHERE tenant_id = ${tenantId} AND source = ${payload.source} AND source_id = ${payload.source_id}
    `;
    if (existing.length > 0 && existing[0].pipeline_status === "pending") {
      return existing[0].id as string;
    }
    return null;
  });

  if (rawEventId === null) {
    await pgmqDelete("ingestion", msg.msg_id);
    return "duplicate_on_insert";
  }

  // Attaches a real display name to the sender's actors row whenever the
  // connector could get one for free (Gmail's From header), regardless of
  // whether this specific message ends up KEEP or DISCARD, or whether the
  // sender is ever named as a decision participant - "participants only
  // ever show a raw email" was a direct, reported gap, this is what fixes
  // it at the source instead of guessing a name later.
  if (payload.actor_display_name && ACTOR_IDENTIFIER_COLUMN[payload.source]) {
    try {
      await withTenant(tenantId, async (sql) => {
        await resolveActorId(sql, tenantId, payload.source, payload.actor, payload.actor_display_name);
      });
    } catch (err) {
      console.error(`Failed to attach display name for ${payload.actor}:`, err);
    }
  }

  // Triage
  const userMsg = buildEventUserMessage(payload as never);
  const triage = await callClaude(TRIAGE_SYSTEM_PROMPT, userMsg, TRIAGE_TOOL, "record_triage_result", 128, TRIAGE_MODEL, 15_000);

  if (triage.decision === "DISCARD") {
    await withTenant(tenantId, async (sql) => {
      await sql`UPDATE public.raw_events SET pipeline_status = 'done' WHERE id = ${rawEventId}`;
    });
    await pgmqDelete("ingestion", msg.msg_id);
    return "discarded";
  }

  // Extraction
  const extraction = await callClaude(
    EXTRACTION_SYSTEM_PROMPT, userMsg, EXTRACTION_TOOL, "record_extraction_result", 512, EXTRACT_MODEL, 30_000,
  ) as {
    record_type: string; status: string; decision_statement: string; rationale: string | null;
    alternatives_considered: string[]; actors: { source_actor_id: string; role: string }[]; confidence: number;
  };

  // Persist (decision + source + actors), mark done, enqueue embedding
  const decisionId = await withTenant(tenantId, async (sql) => {
    const existingDecision = await sql`
      SELECT id FROM public.decisions WHERE tenant_id = ${tenantId} AND origin_raw_event_id = ${rawEventId}
    `;
    if (existingDecision.length > 0) return existingDecision[0].id as string;

    const decisionRows = await sql`
      INSERT INTO public.decisions (
        tenant_id, record_type, decision_statement, rationale, alternatives_considered,
        status, scope, confidence, permission_scope, origin_raw_event_id
      ) VALUES (
        ${tenantId}, ${extraction.record_type}, ${extraction.decision_statement}, ${extraction.rationale},
        ${extraction.alternatives_considered ?? []}, ${extraction.status}, 'team',
        ${extraction.confidence}, ${payload.permission_scope ?? []}, ${rawEventId}
      ) RETURNING id
    `;
    const newDecisionId = decisionRows[0].id as string;

    if (payload.source_permalink) {
      await sql`
        INSERT INTO public.decision_sources (tenant_id, decision_id, raw_event_id, permalink)
        VALUES (${tenantId}, ${newDecisionId}, ${rawEventId}, ${payload.source_permalink})
        ON CONFLICT (decision_id, permalink) DO NOTHING
      `;
    }

    for (const actorRef of extraction.actors ?? []) {
      try {
        const actorId = await resolveActorId(sql, tenantId, payload.source, actorRef.source_actor_id);
        await sql`
          INSERT INTO public.decision_actors (tenant_id, decision_id, actor_id, role)
          VALUES (${tenantId}, ${newDecisionId}, ${actorId}, ${actorRef.role})
          ON CONFLICT (decision_id, actor_id, role) DO NOTHING
        `;
      } catch {
        // Unsupported actor source or resolution failure - skip this actor,
        // never fail the whole decision over one bad reference.
      }
    }

    await sql`UPDATE public.raw_events SET pipeline_status = 'done' WHERE id = ${rawEventId}`;
    return newDecisionId;
  });

  await pgmqSend("embedding_queue", { tenant_id: tenantId, decision_id: decisionId });
  await pgmqDelete("ingestion", msg.msg_id);
  return "persisted";
}

// ── Embedding pipeline (mirrors embedding_worker._handle_message) ────────

function buildSearchableText(statement: string, rationale: string | null, alternatives: string[]): string {
  const lines = [`Decision: ${statement}`];
  if (rationale) lines.push(`Rationale: ${rationale}`);
  if (alternatives.length > 0) lines.push(`Alternatives considered: ${alternatives.join(", ")}`);
  return lines.join("\n");
}

// ── Decision conflict detection (differentiator: nothing else in this
// market automatically reasons about whether a new decision contradicts
// or duplicates an existing one - competitors either index content for
// search [Glean] or rely on a human manually verifying/flagging staleness
// [Guru]. This runs on every newly embedded decision, for free, using the
// same vector search /search already relies on. ─────────────────────────

const CONFLICT_CANDIDATE_LIMIT = 3;
// Cosine similarity floor before a candidate is even worth an LLM call -
// below this, two decisions just aren't about the same thing closely
// enough to plausibly conflict, and asking Claude would be pure noise
// (and pure cost) for an unrelated pair.
const CONFLICT_SIMILARITY_FLOOR = 0.72;
const CONFLICT_CONFIDENCE_FLOOR = 0.6;

const CONFLICT_TOOL = {
  name: "record_conflict_analysis",
  description: "Classify how a new decision relates to each existing candidate decision.",
  input_schema: {
    type: "object",
    properties: {
      classifications: {
        type: "array",
        items: {
          type: "object",
          properties: {
            candidate_number: { type: "integer" },
            relationship: { type: "string", enum: ["contradicts", "duplicates", "unrelated"] },
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

const CONFLICT_SYSTEM_PROMPT = `You compare one new decision against a short list of existing decisions from the same team's records, and classify how each candidate relates to the new one.

- "contradicts": the two decisions state genuinely incompatible conclusions about the same specific question (not merely related topics - e.g. "use Postgres" vs "use MongoDB" for the same system is a contradiction; "use Postgres for the context layer" and "use Redis for caching" is not, those are different questions).
- "duplicates": the two decisions state essentially the same conclusion about the same question, redundantly.
- "unrelated": anything else, including decisions that are topically similar but don't actually make competing or repeated claims. Default to this when genuinely unsure - a false "contradicts" flag is worse than a missed one.

Call record_conflict_analysis exactly once with one classification per candidate, in the order given.`;

type ConflictCandidate = { id: string; decision_statement: string; rationale: string | null };

async function detectConflicts(
  tenantId: string,
  decisionId: string,
  statement: string,
  rationale: string | null,
  embedding: number[],
): Promise<void> {
  try {
    const vectorLiteral = "[" + embedding.join(",") + "]";
    const candidates: ConflictCandidate[] = await withTenant(tenantId, async (sql) => {
      const rows = await sql`
        SELECT d.id, d.decision_statement, d.rationale,
               1 - (de.embedding <=> ${vectorLiteral}::vector) AS similarity
        FROM public.decision_embeddings de
        JOIN public.decisions d ON d.id = de.decision_id AND d.tenant_id = de.tenant_id
        WHERE de.tenant_id = ${tenantId} AND de.decision_id != ${decisionId}
          AND 1 - (de.embedding <=> ${vectorLiteral}::vector) >= ${CONFLICT_SIMILARITY_FLOOR}
        ORDER BY de.embedding <=> ${vectorLiteral}::vector ASC
        LIMIT ${CONFLICT_CANDIDATE_LIMIT}
      `;
      return rows.map((r: { id: string; decision_statement: string; rationale: string | null }) => ({
        id: r.id, decision_statement: r.decision_statement, rationale: r.rationale,
      }));
    });

    if (candidates.length === 0) return;

    const userMessage = [
      `New decision:\n${statement}${rationale ? `\nReason: ${rationale}` : ""}`,
      "",
      "Existing candidates:",
      ...candidates.map((c, i) => `${i + 1}. ${c.decision_statement}${c.rationale ? ` (reason: ${c.rationale})` : ""}`),
    ].join("\n");

    const result = await callClaude(
      CONFLICT_SYSTEM_PROMPT, userMessage, CONFLICT_TOOL, "record_conflict_analysis", 512, EXTRACT_MODEL, 20_000,
    ) as { classifications: { candidate_number: number; relationship: string; reason: string; confidence: number }[] };

    const flagged = (result.classifications ?? []).filter(
      (c) => (c.relationship === "contradicts" || c.relationship === "duplicates") && c.confidence >= CONFLICT_CONFIDENCE_FLOOR,
    );
    if (flagged.length === 0) return;

    await withTenant(tenantId, async (sql) => {
      for (const c of flagged) {
        const candidate = candidates[c.candidate_number - 1];
        if (!candidate) continue;
        await sql`
          INSERT INTO public.decision_conflicts (tenant_id, decision_id, related_decision_id, relationship, reason, confidence)
          VALUES (${tenantId}, ${decisionId}, ${candidate.id}, ${c.relationship}, ${c.reason}, ${c.confidence})
          ON CONFLICT (decision_id, related_decision_id) DO UPDATE SET
            relationship = EXCLUDED.relationship, reason = EXCLUDED.reason, confidence = EXCLUDED.confidence
        `;
      }
    });
  } catch (err) {
    // Fails open, same rule as everywhere else this session: conflict
    // detection is a quality enrichment, never a reason to fail the
    // embedding job that already succeeded.
    console.error(`detectConflicts failed for decision ${decisionId}:`, err);
  }
}

async function handleEmbeddingMessage(msg: PgmqMsg): Promise<string> {
  const job = msg.message as { tenant_id: string; decision_id: string };

  const row = await withTenant(job.tenant_id, async (sql) => {
    const rows = await sql`
      SELECT decision_statement, rationale, alternatives_considered
      FROM public.decisions WHERE id = ${job.decision_id} AND tenant_id = ${job.tenant_id}
    `;
    return rows[0] ?? null;
  });

  if (row === null) {
    // Non-retryable (decision was deleted after the job was enqueued) -
    // matches the Python worker leaving it for now rather than inventing
    // archive/DLQ infrastructure; delete here since there is nothing to retry.
    await pgmqDelete("embedding_queue", msg.msg_id);
    return "decision_not_found";
  }

  const text = buildSearchableText(row.decision_statement, row.rationale, row.alternatives_considered ?? []);
  const embedding = await embedDocument(text);
  const vectorLiteral = "[" + embedding.join(",") + "]";

  await withTenant(job.tenant_id, async (sql) => {
    await sql`
      INSERT INTO public.decision_embeddings (decision_id, tenant_id, embedding, embedding_model, embedded_at)
      VALUES (${job.decision_id}, ${job.tenant_id}, ${vectorLiteral}::vector, ${VOYAGE_MODEL}, now())
      ON CONFLICT (decision_id) DO UPDATE SET
        embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model, embedded_at = EXCLUDED.embedded_at
    `;
  });

  await detectConflicts(job.tenant_id, job.decision_id, row.decision_statement, row.rationale, embedding);

  await pgmqDelete("embedding_queue", msg.msg_id);
  return "embedded";
}

// ── Bounded concurrency runner ─────────────────────────────────────────

async function runBounded<T>(items: T[], concurrency: number, fn: (item: T) => Promise<string>) {
  const results: { status: string; error?: string }[] = [];
  let i = 0;
  async function worker() {
    while (i < items.length) {
      const item = items[i++];
      try {
        results.push({ status: await fn(item) });
      } catch (err) {
        results.push({ status: "error", error: err instanceof Error ? err.message : String(err) });
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, worker));
  return results;
}

// ── Entrypoint ─────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  // pgmq.read() sets each row's visibility timeout as a side effect of the
  // SQL call itself - if anything after that point throws (a parsing bug,
  // a network drop), the messages are already locked for VISIBILITY_TIMEOUT_
  // SECONDS with nothing to show for it, and an uncaught rejection here can
  // otherwise surface to the caller as an opaque empty-looking response
  // instead of a real error. Wrapping the whole handler guarantees the
  // caller always sees what actually happened.
  try {
    const ingestionMsgs = await pgmqRead("ingestion", INGESTION_BATCH);
    const ingestionResults = await runBounded(ingestionMsgs, CONCURRENCY, handleIngestionMessage);

    const embeddingMsgs = await pgmqRead("embedding_queue", EMBEDDING_BATCH);
    const embeddingResults = await runBounded(embeddingMsgs, CONCURRENCY, handleEmbeddingMessage);

    const summarize = (results: { status: string; error?: string }[]) => {
      const counts: Record<string, number> = {};
      for (const r of results) counts[r.status] = (counts[r.status] ?? 0) + 1;
      const errors = results.filter((r) => r.status === "error").slice(0, 5).map((r) => r.error);
      return { counts, errors };
    };

    const ingestionSummary = summarize(ingestionResults);
    const embeddingSummary = summarize(embeddingResults);

    return new Response(
      JSON.stringify({
        ingestion: { read: ingestionMsgs.length, ...ingestionSummary.counts, sample_errors: ingestionSummary.errors },
        embedding: { read: embeddingMsgs.length, ...embeddingSummary.counts, sample_errors: embeddingSummary.errors },
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err) {
    const message = err instanceof Error ? (err.stack ?? err.message) : String(err);
    console.error("ai-worker top-level failure:", message);
    return new Response(
      JSON.stringify({ error: message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
