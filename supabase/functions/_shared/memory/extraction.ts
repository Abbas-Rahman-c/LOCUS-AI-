// supabase/functions/_shared/memory/extraction.ts
//
// Merged triage+extraction for the Memory Intelligence layer's 9-type
// taxonomy (spec Section 3) - one Claude call per event, same "pay for the
// raw text once" shape as ai-worker/index.ts's TRIAGE_EXTRACTION_TOOL, just
// extended from 3 record types to 9 and to the temporal/payload fields the
// new model needs (valid_from, attribute_key, entity mentions).
//
// Anthropic tool schemas can't express "these fields are required only when
// type=Commitment" - every payload field is optional in the schema, and
// validatePayloadForType() below checks the type-specific required set
// immediately after the tool_use block is parsed, same "trust but
// re-verify" style ai-worker's resolveActorId already uses.

import { redactFinancialInfo } from "../financialRedaction.ts";
import type { MemoryType } from "./types.ts";

const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const EXTRACT_MODEL = Deno.env.get("ANTHROPIC_EXTRACT_MODEL") ?? "claude-haiku-4-5-20251001";
const CLAUDE_MAX_RETRIES = 3;

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

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function backoffMs(attempt: number): number {
  const base = 500 * Math.pow(2, attempt);
  const jitter = base * 0.25 * (Math.random() * 2 - 1);
  return Math.round(base + jitter);
}

// Same forced-tool-use call shape as ai-worker's callClaude - kept as its
// own copy here rather than a shared export, matching this codebase's
// existing pattern of small per-function duplication over a shared _shared
// helper for things this size.
async function callClaude(
  system: string,
  userMessage: string,
  tool: Record<string, unknown>,
  toolName: string,
): Promise<Record<string, unknown>> {
  let lastErr: Error | null = null;
  for (let attempt = 0; attempt <= CLAUDE_MAX_RETRIES; attempt++) {
    let resp: Response;
    try {
      resp = await fetchWithTimeout("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          model: EXTRACT_MODEL,
          max_tokens: 768,
          temperature: 0,
          system: [{ type: "text", text: system, cache_control: { type: "ephemeral" } }],
          messages: [{ role: "user", content: userMessage }],
          tools: [tool],
          tool_choice: { type: "tool", name: toolName },
        }),
      }, 30_000);
    } catch (err) {
      lastErr = err instanceof Error ? err : new Error(String(err));
      if (attempt === CLAUDE_MAX_RETRIES) throw lastErr;
      await sleep(backoffMs(attempt));
      continue;
    }

    if (resp.ok) {
      const data = await resp.json();
      const block = (data.content ?? []).find((b: { type?: string }) => b.type === "tool_use");
      if (!block) throw new Error(`Claude did not return a tool_use block for ${toolName}`);
      return block.input as Record<string, unknown>;
    }

    const bodyText = await resp.text();
    const retryable = resp.status === 429 || resp.status >= 500;
    lastErr = new Error(`Anthropic API error ${resp.status}: ${bodyText}`);
    if (!retryable || attempt === CLAUDE_MAX_RETRIES) throw lastErr;
    const retryAfterHeader = resp.headers.get("retry-after");
    const retryAfterMs = retryAfterHeader ? Number(retryAfterHeader) * 1000 : null;
    await sleep(retryAfterMs && Number.isFinite(retryAfterMs) ? retryAfterMs : backoffMs(attempt));
  }
  throw lastErr ?? new Error(`Anthropic API call failed for ${toolName}`);
}

const MEMORY_TYPES: MemoryType[] = [
  "Context", "Change", "Commitment", "Decision", "Rationale",
  "Blocker", "Outcome", "Requirement", "CustomerSignal",
];

const EXTRACTION_SYSTEM_PROMPT = `You are the memory-extraction stage of Locus AI's Memory Intelligence layer. You read ONE workplace event (Slack/Gmail/Notion) and decide whether it should become a durable memory, and if so, extract it into one of nine types.

Types, and when to use each:
- Context: background information or an assumption someone is operating under (not yet a decision or requirement).
- Change: something that changed from one state to another (a date moved, a plan shifted).
- Commitment: someone committed to do something by a due date.
- Decision: a choice was made or proposed among options.
- Rationale: the stated reasoning behind a Change or Decision.
- Blocker: something is obstructing progress.
- Outcome: a Commitment or Blocker was resolved.
- Requirement: a stated need or constraint the work must satisfy.
- CustomerSignal: feedback, sentiment, or a request from a named customer.

Classify first:
- KEEP: clearly one of the nine types, explicit in the text.
- UNCERTAIN: plausibly one of the nine types but the text is vague or incomplete.
- DISCARD: social chatter, FYI, logistics, automated notification, or unrelated content. Leave every extraction field null on DISCARD.

If KEEP or UNCERTAIN, extract exactly one memory:
- attribute_key identifies WHAT this memory is about, stable across updates to the same fact - e.g. "project-x-launch-date", "acme-corp-onboarding-owner". Two memories about the same underlying fact (even if the value changed) MUST share the same attribute_key - this is what lets the system detect that one supersedes the other. Two memories about genuinely different facts (e.g. a beta-launch date vs. a public-launch date) MUST get different attribute_keys, even if worded similarly.
- valid_from is when this became the believed-true state - usually the event's occurred_at, but if the text describes something that became true earlier or will become true later, use that date instead.
- entities: every Person, Team, Project, Customer, Product, Topic, or System explicitly named or clearly referenced. Give the exact mention text as it appears (a name, an email, a project name) - never invent an id, never resolve it yourself.
- role, per entity: "subject" if this memory is actually about that entity - it did something, something happened to it, it's what changed/was decided/was blocked. "referenced" if it's only named to explain or locate the real subject - a comparison ("matches the work he did on X"), a pointer to a different ticket ("Task 22"), a schedule label ("Phase 5", "Phase 2"), or a plural/collective description of similar-but-unnamed other work ("the Phase 2 AI pipeline tasks"). A Person or Team is "subject" whenever they're a real participant in the described event (did the work, owns the result, was reassigned) even if the sentence is really about something else - people and teams are always worth tracking. Project/System/Topic/Product/Customer entities get "referenced" specifically when the mention is a pointer/comparison/label rather than something this memory is itself describing.
  Worked example: text reads "Reassigned to the data science team, same pattern as the Phase 2 AI pipeline tasks... Sudhira freed up for MCP Server work instead (Task 22)." about a ticket titled "Hybrid RAG Retrieval Engine". Correct extraction: {mention_text: "Hybrid RAG Retrieval Engine", entity_type_guess: "Project", role: "subject"} - this ticket is what the memory is about. {mention_text: "data science team", entity_type_guess: "Team", role: "subject"} - real team taking ownership. {mention_text: "Sudhira", entity_type_guess: "Person", role: "subject"} - real person being reassigned. {mention_text: "MCP Server", entity_type_guess: "System", role: "referenced"} - named only as where Sudhira is going, not what this memory describes. "Phase 2 AI pipeline" and "Task 22" should NOT appear as entities at all here - the first is a vague plural comparison ("tasks", not one named thing), the second is a bare pointer to another ticket already captured via "MCP Server".
- payload fields: fill only the ones that apply to the chosen type (see the tool schema); leave the rest null.

Never invent a fact not stated in the text. Never fill entities with something not actually mentioned.`;

const EXTRACTION_TOOL = {
  name: "record_memory_extraction",
  description: "Triage one event and, unless DISCARD, extract one memory of the given type.",
  input_schema: {
    type: "object",
    properties: {
      decision: { type: "string", enum: ["KEEP", "UNCERTAIN", "DISCARD"] },
      confidence: { type: "number", minimum: 0, maximum: 1 },
      type: { type: ["string", "null"], enum: [...MEMORY_TYPES, null] },
      title: { type: ["string", "null"], description: "One short line. Null on DISCARD." },
      summary: { type: ["string", "null"], description: "1-3 sentences. Null on DISCARD." },
      valid_from: { type: ["string", "null"], description: "ISO 8601. Null on DISCARD." },
      attribute_key: { type: ["string", "null"] },
      payload: {
        type: "object",
        description: "Only the fields relevant to `type` need be non-null; leave the rest null.",
        properties: {
          due_date: { type: ["string", "null"] },
          owner_entity_mention: { type: ["string", "null"] },
          resolved_by_memory_mention: { type: ["string", "null"], description: "Free-text description of the resolving event, if any - not an id." },
          decision_status: { type: ["string", "null"], enum: ["proposed", "decided", null] },
          alternatives_considered: { type: "array", items: { type: "string" } },
          from_value: { type: ["string", "null"] },
          to_value: { type: ["string", "null"] },
          statement: { type: ["string", "null"] },
          reasoning: { type: ["string", "null"] },
          blocking_what: { type: ["string", "null"] },
          resolves_memory_mention: { type: ["string", "null"] },
          customer_entity_mention: { type: ["string", "null"] },
          sentiment: { type: ["string", "null"], enum: ["positive", "neutral", "negative", null] },
        },
        additionalProperties: false,
      },
      entities: {
        type: "array",
        items: {
          type: "object",
          properties: {
            mention_text: { type: "string", minLength: 1 },
            entity_type_guess: {
              type: "string",
              enum: ["Person", "Team", "Project", "Customer", "Product", "Topic", "System"],
            },
            role: {
              type: "string",
              enum: ["subject", "referenced"],
              description: "'subject' if this memory is actually about this entity; 'referenced' if it's only named in passing to explain or locate the real subject (a comparison, a pointer to different work, a schedule label).",
            },
          },
          required: ["mention_text", "entity_type_guess", "role"],
          additionalProperties: false,
        },
      },
    },
    required: ["decision", "confidence", "type", "title", "summary", "valid_from", "attribute_key", "payload", "entities"],
    additionalProperties: false,
  },
};

export interface EntityMention {
  mention_text: string;
  entity_type_guess: string;
  role: "subject" | "referenced";
}

export interface ExtractionResult {
  decision: "KEEP" | "UNCERTAIN" | "DISCARD";
  confidence: number;
  type: MemoryType | null;
  title: string | null;
  summary: string | null;
  valid_from: string | null;
  attribute_key: string | null;
  payload: Record<string, unknown>;
  entities: EntityMention[];
}

// Per-type required payload fields, checked after the call returns - see
// this file's header comment for why this can't live in the tool schema
// itself.
const REQUIRED_PAYLOAD_FIELDS: Partial<Record<MemoryType, string[]>> = {
  Commitment: ["due_date"],
  Decision: ["decision_status"],
  Context: ["statement"],
  Requirement: ["statement"],
  Rationale: ["reasoning"],
  Blocker: ["blocking_what"],
  CustomerSignal: ["customer_entity_mention"],
};

export function validatePayloadForType(type: MemoryType, payload: Record<string, unknown>): string[] {
  const required = REQUIRED_PAYLOAD_FIELDS[type] ?? [];
  return required.filter((field) => payload[field] === null || payload[field] === undefined || payload[field] === "");
}

export async function extractMemory(event: {
  source: string;
  actorDisplayName: string;
  threadRef: string | null;
  permissionScope: string[];
  rawContent: string;
  occurredAt: string;
}): Promise<ExtractionResult> {
  const redactedContent = redactFinancialInfo(event.rawContent);
  const userMessage = `source: ${event.source}\nactor: ${event.actorDisplayName}\nthread_ref: ${event.threadRef ?? "(none)"}\npermission_scope: ${JSON.stringify(event.permissionScope)}\noccurred_at: ${event.occurredAt}\ncontent:\n${redactedContent}`;

  const raw = await callClaude(EXTRACTION_SYSTEM_PROMPT, userMessage, EXTRACTION_TOOL, "record_memory_extraction");

  const payload = (raw.payload ?? {}) as Record<string, unknown>;
  // Defense in depth, same reasoning as ai-worker's post-extraction
  // redaction pass: scrub the model's own free-text output fields too, not
  // just what we sent it.
  for (const key of ["statement", "reasoning", "blocking_what"]) {
    if (typeof payload[key] === "string") payload[key] = redactFinancialInfo(payload[key] as string);
  }

  return {
    decision: raw.decision as "KEEP" | "UNCERTAIN" | "DISCARD",
    confidence: Number(raw.confidence ?? 0),
    type: (raw.type as MemoryType | null) ?? null,
    title: typeof raw.title === "string" ? redactFinancialInfo(raw.title) : null,
    summary: typeof raw.summary === "string" ? redactFinancialInfo(raw.summary) : null,
    valid_from: (raw.valid_from as string | null) ?? null,
    attribute_key: (raw.attribute_key as string | null) ?? null,
    payload,
    entities: (raw.entities as EntityMention[] | undefined) ?? [],
  };
}
