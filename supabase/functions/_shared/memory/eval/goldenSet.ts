// supabase/functions/_shared/memory/eval/goldenSet.ts
//
// Spec Section 12's golden evaluation set: "30-50 hand-built cases... used
// to score extraction precision, current-state accuracy, and
// conflict-detection precision before this is considered done." 35 cases
// total across the three dimensions, hand-written (not sampled from real
// data) so expected answers are known ground truth, not a guess.
//
// Also doubles as the deterministic, extraction-independent test for
// Loci patterns 3/5/7 (why_changed, customer_commitments,
// evidence_for_answer) - the real starter_events fixture set doesn't
// naturally produce a Rationale-type memory or a Customer entity, since
// extraction's own type classification isn't guaranteed to hit every type
// on any given run (same reasoning as handleDebugTestReconciliation's
// synthetic worked example, applied here to the query-pattern layer).

import type { CanonicalMemoryObject, EntityRef, MemoryType } from "../types.ts";

// ── Category 1: extraction precision (20 cases, real Claude calls) ──────

export interface ExtractionCase {
  id: string;
  source: string;
  actorDisplayName: string;
  rawContent: string;
  occurredAt: string;
  expectedOutcome: "KEEP" | "DISCARD";
  expectedType: MemoryType | null; // null when expectedOutcome is DISCARD
  // Optional entity-role checks (mention_text matched case-insensitively,
  // substring). expectedSubjectMentions: must appear with role="subject".
  // expectedReferencedOrAbsent: if present at all, must be role="referenced"
  // - never "subject" - but it's fine if the model drops it entirely (see
  // extraction.ts's prompt: vague/collective/redundant-pointer mentions
  // should often not be extracted as an entity at all).
  expectedSubjectMentions?: string[];
  expectedReferencedOrAbsent?: string[];
}

export const EXTRACTION_CASES: ExtractionCase[] = [
  { id: "ex-01", source: "slack", actorDisplayName: "Dana Kim", rawContent: "Decided: we're moving off Heroku to Fly.io for hosting, effective next sprint.", occurredAt: "2026-07-01T10:00:00Z", expectedOutcome: "KEEP", expectedType: "Decision" },
  { id: "ex-02", source: "gmail", actorDisplayName: "Sam Ortiz", rawContent: "Subject: Re: Hosting migration\nActually, let's push the Fly.io migration to next month - we found a compatibility issue with our background workers.", occurredAt: "2026-07-05T09:00:00Z", expectedOutcome: "KEEP", expectedType: "Change" },
  { id: "ex-03", source: "slack", actorDisplayName: "Dana Kim", rawContent: "I'll have the Fly.io migration plan doc ready by Friday.", occurredAt: "2026-07-02T14:00:00Z", expectedOutcome: "KEEP", expectedType: "Commitment" },
  { id: "ex-04", source: "notion", actorDisplayName: "Priya Sharma", rawContent: "Context: our current infra budget assumes Heroku pricing through Q4 - this will need revisiting once we're on Fly.io.", occurredAt: "2026-07-01T11:00:00Z", expectedOutcome: "KEEP", expectedType: "Context" },
  { id: "ex-05", source: "slack", actorDisplayName: "Dana Kim", rawContent: "We're going with Fly.io over Render because Fly.io has better multi-region support and our EU customers need low latency, which Render's single-region free tier couldn't give us.", occurredAt: "2026-07-01T10:05:00Z", expectedOutcome: "KEEP", expectedType: "Rationale" },
  { id: "ex-06", source: "gmail", actorDisplayName: "Sam Ortiz", rawContent: "Subject: Migration blocked\nWe can't proceed with the Fly.io migration until DevOps grants us production deploy access - currently blocked on an IT ticket.", occurredAt: "2026-07-03T08:00:00Z", expectedOutcome: "KEEP", expectedType: "Blocker" },
  { id: "ex-07", source: "slack", actorDisplayName: "Dana Kim", rawContent: "Migration is done - we're fully on Fly.io now, Heroku account closed.", occurredAt: "2026-07-20T16:00:00Z", expectedOutcome: "KEEP", expectedType: "Outcome" },
  { id: "ex-08", source: "notion", actorDisplayName: "Priya Sharma", rawContent: "Requirement: any new hosting provider must support zero-downtime deploys - this is non-negotiable given our uptime SLA.", occurredAt: "2026-06-28T09:00:00Z", expectedOutcome: "KEEP", expectedType: "Requirement" },
  { id: "ex-09", source: "gmail", actorDisplayName: "Jordan Lee", rawContent: "Subject: Feedback from Acme Corp\nAcme's engineering lead mentioned they're frustrated with our current API rate limits and it's affecting their integration timeline.", occurredAt: "2026-07-04T13:00:00Z", expectedOutcome: "KEEP", expectedType: "CustomerSignal" },
  { id: "ex-10", source: "slack", actorDisplayName: "Dana Kim", rawContent: "lol did anyone see the game last night", occurredAt: "2026-07-01T20:00:00Z", expectedOutcome: "DISCARD", expectedType: null },
  { id: "ex-11", source: "gmail", actorDisplayName: "noreply@github.com", rawContent: "Subject: [GitHub] Weekly digest\nHere's your weekly summary of activity across your repositories.", occurredAt: "2026-07-01T00:00:00Z", expectedOutcome: "DISCARD", expectedType: null },
  { id: "ex-12", source: "slack", actorDisplayName: "Sam Ortiz", rawContent: "thanks!", occurredAt: "2026-07-02T15:00:00Z", expectedOutcome: "DISCARD", expectedType: null },
  { id: "ex-13", source: "slack", actorDisplayName: "Dana Kim", rawContent: "Final call: switching the default payment processor from Braintree to Stripe for all new accounts starting August 1st.", occurredAt: "2026-07-10T11:00:00Z", expectedOutcome: "KEEP", expectedType: "Decision" },
  { id: "ex-14", source: "gmail", actorDisplayName: "Priya Sharma", rawContent: "Subject: Stripe rollout update\nWe're now targeting August 15th instead of August 1st for the Stripe switch - need more time for reconciliation testing.", occurredAt: "2026-07-18T10:00:00Z", expectedOutcome: "KEEP", expectedType: "Change" },
  { id: "ex-15", source: "slack", actorDisplayName: "Sam Ortiz", rawContent: "I'll own the Stripe reconciliation test plan, done by July 25th.", occurredAt: "2026-07-11T09:00:00Z", expectedOutcome: "KEEP", expectedType: "Commitment" },
  { id: "ex-16", source: "notion", actorDisplayName: "Jordan Lee", rawContent: "Context: current Braintree contract has an early-termination fee if we leave before December - factored into the Stripe switch decision.", occurredAt: "2026-07-09T14:00:00Z", expectedOutcome: "KEEP", expectedType: "Context" },
  { id: "ex-17", source: "gmail", actorDisplayName: "Sam Ortiz", rawContent: "Subject: Stripe blocked\nWe can't finish reconciliation testing until Finance shares last quarter's Braintree settlement report - waiting on that.", occurredAt: "2026-07-15T11:00:00Z", expectedOutcome: "KEEP", expectedType: "Blocker" },
  { id: "ex-18", source: "slack", actorDisplayName: "Sam Ortiz", rawContent: "Reconciliation test plan finished and approved - Stripe switch is unblocked.", occurredAt: "2026-07-25T17:00:00Z", expectedOutcome: "KEEP", expectedType: "Outcome" },
  { id: "ex-19", source: "notion", actorDisplayName: "Priya Sharma", rawContent: "Requirement: the payment processor switch must not interrupt any in-flight subscription billing cycle.", occurredAt: "2026-07-08T10:00:00Z", expectedOutcome: "KEEP", expectedType: "Requirement" },
  { id: "ex-20", source: "gmail", actorDisplayName: "Jordan Lee", rawContent: "Subject: Re: Beta feedback\nBrightline Inc's PM said the new dashboard export feature is exactly what they needed and it's already saving their team time.", occurredAt: "2026-07-12T16:00:00Z", expectedOutcome: "KEEP", expectedType: "CustomerSignal" },
  // Real case, verbatim from production data (LOCUS-AI-APP tenant, ticket
  // BE-19) that surfaced the mention-vs-subject bug: extraction was minting
  // a standalone Project entity for every named thing in the sentence,
  // including "Task 22" (a bare pointer to a different ticket, already
  // captured via "MCP Server" in the same clause) and "Phase 2 AI pipeline"
  // (a vague plural comparison - "the ... tasks" - not one named thing).
  // Real people/teams named in passing (Sudhira, the data science team)
  // must still come through as subjects - the fix is narrower than "ignore
  // anything not literally the ticket title."
  {
    id: "ex-21",
    source: "notion",
    actorDisplayName: "Rajith",
    rawContent: "Task Name: Hybrid RAG Retrieval Engine\nNotes: Reassigned to the data science team, same pattern as the Phase 2 AI pipeline tasks. Query embedding, vector similarity search, and keyword search all built by Rajith's team, merged into main, and verified working end to end via the /search endpoint (real query, real citations, real decision returned). Sudhira freed up for MCP Server work instead (Task 22).",
    occurredAt: "2026-08-02T09:30:08Z",
    expectedOutcome: "KEEP",
    expectedType: "Outcome",
    expectedSubjectMentions: ["Hybrid RAG Retrieval Engine", "data science team", "Sudhira"],
    expectedReferencedOrAbsent: ["MCP Server", "Task 22", "Phase 2 AI pipeline"],
  },
  // Real case, verbatim reconstruction of the exact field-per-line text
  // extractNotionPageText() actually produces for a Notion tracker row
  // (LOCUS-AI-APP tenant, ticket BE-14) - not hand-written prose like
  // ex-21. Tests the OTHER sub-pattern the audit found: a structured
  // `Sprint: Phase 2` field line (plus `Dependencies: Phase 1 Ingestion
  // complete`, another phase reference) rather than a phase mentioned
  // inside a sentence. ex-21's worked example only covers comparison/
  // pointer mentions in prose - this checks the fix generalizes to a
  // schedule-label field on its own line, which is a different shape.
  {
    id: "ex-22",
    source: "notion",
    actorDisplayName: "Rajith",
    rawContent: "Schema Validation\nEpic: AI/ML\nRole: Developer\nNotes: Strict schema validation on extraction output. Built by Rajith's AI/data science team, not the originally assigned owner.\nSprint: Phase 2\nStatus: Completed\nPriority: P1 High\nWorkstream: AI/RAG\nDependencies: Phase 1 Ingestion complete",
    occurredAt: "2026-08-02T09:30:07Z",
    expectedOutcome: "KEEP",
    expectedType: "Outcome",
    expectedSubjectMentions: ["Schema Validation", "data science team"],
    expectedReferencedOrAbsent: ["Phase 2", "Phase 1", "AI/RAG"],
  },
];

// ── Category 2: current-state / temporal accuracy (8 cases, pure functions) ──

function mem(partial: Partial<CanonicalMemoryObject> & { memory_id: string; entities: EntityRef[] }): CanonicalMemoryObject {
  return {
    organization_id: "eval-tenant",
    type: "Decision",
    title: partial.memory_id,
    summary: partial.memory_id,
    payload: {},
    occurred_at: partial.valid_from as string,
    valid_from: partial.valid_from as string,
    valid_until: null,
    observed_at: partial.valid_from as string,
    source_events: [],
    citations: [],
    confidence: 1,
    freshness: "fresh",
    authority: null,
    status: "current",
    supersedes: null,
    contradicted_by: null,
    permissions: { inherited_from: [], visible_to: [] },
    embedding: [],
    searchable_text: "",
    ...partial,
  } as CanonicalMemoryObject;
}

const PROJECT_X: EntityRef = { entity_id: "eval-entity-project-x", entity_type: "Project", canonical_name: "Project X" };

// A real 3-hop supersession chain: v1 (proposed Jan) -> v2 (superseded it,
// Feb) -> v3 (superseded v2, Mar) -> v4, still current, Apr.
export const TEMPORAL_CHAIN: CanonicalMemoryObject[] = [
  mem({ memory_id: "chain-v1", entities: [PROJECT_X], valid_from: "2026-01-01T00:00:00Z", valid_until: "2026-02-01T00:00:00Z", status: "superseded", supersedes: null, payload: { attribute_key: "launch_date" }, title: "Launch Jan 1", summary: "v1" }),
  mem({ memory_id: "chain-v2", entities: [PROJECT_X], valid_from: "2026-02-01T00:00:00Z", valid_until: "2026-03-01T00:00:00Z", status: "superseded", supersedes: "chain-v1", payload: { attribute_key: "launch_date" }, title: "Launch Feb 1", summary: "v2" }),
  mem({ memory_id: "chain-v3", entities: [PROJECT_X], valid_from: "2026-03-01T00:00:00Z", valid_until: "2026-04-01T00:00:00Z", status: "superseded", supersedes: "chain-v2", payload: { attribute_key: "launch_date" }, title: "Launch Mar 1", summary: "v3" }),
  mem({ memory_id: "chain-v4", entities: [PROJECT_X], valid_from: "2026-04-01T00:00:00Z", valid_until: null, status: "current", supersedes: "chain-v3", payload: { attribute_key: "launch_date" }, title: "Launch Apr 1", summary: "v4 - current" }),
];

export interface TemporalCase {
  id: string;
  description: string;
  fn: "getCurrentState" | "getStateAsOf";
  targetDate?: string; // for getStateAsOf
  expectedMemoryId: string | undefined;
}

export const TEMPORAL_CASES: TemporalCase[] = [
  { id: "temp-01", description: "getCurrentState returns the latest (v4), not an earlier superseded version", fn: "getCurrentState", expectedMemoryId: "chain-v4" },
  { id: "temp-02", description: "getStateAsOf(Jan 15) reconstructs v1 - before any supersession", fn: "getStateAsOf", targetDate: "2026-01-15T00:00:00Z", expectedMemoryId: "chain-v1" },
  { id: "temp-03", description: "getStateAsOf(Feb 15) reconstructs v2 - after the first supersession, before the second", fn: "getStateAsOf", targetDate: "2026-02-15T00:00:00Z", expectedMemoryId: "chain-v2" },
  { id: "temp-04", description: "getStateAsOf(Mar 15) reconstructs v3 - after the second supersession, before the third", fn: "getStateAsOf", targetDate: "2026-03-15T00:00:00Z", expectedMemoryId: "chain-v3" },
  { id: "temp-05", description: "getStateAsOf(May 1) reconstructs v4 - after the whole chain, matches current", fn: "getStateAsOf", targetDate: "2026-05-01T00:00:00Z", expectedMemoryId: "chain-v4" },
  { id: "temp-06", description: "getStateAsOf(Dec 2025) finds nothing - before the chain even starts", fn: "getStateAsOf", targetDate: "2025-12-01T00:00:00Z", expectedMemoryId: undefined },
  { id: "temp-07", description: "getCurrentState with a different attribute_key on the same entity finds nothing (different attribute, not the chain)", fn: "getCurrentState", expectedMemoryId: undefined },
  { id: "temp-08", description: "getCurrentState never returns a superseded memory even if it's chronologically last among a filtered subset", fn: "getCurrentState", expectedMemoryId: "chain-v4" },
];

// ── Category 3: conflict-detection precision/recall (7 cases, real Claude calls) ──
// Includes the spec's own Section 6 worked example verbatim.
//
// Labeling rule for update vs conflict (added after the first eval run:
// all 3 "failures" that round turned out to be inconsistent hand-labeling,
// not model error - conf-06 and conf-07 below were corrected, not the
// pipeline). Apply this test when hand-labeling a new case:
//
//   UPDATE  - the new memory's own text carries a deliberate-change signal
//             relative to the candidate: an explicit reason clause ("per
//             the new contract", "because X"), an explicit correction
//             marker ("actually", "we're pushing it back", "now"), OR a
//             direct state transition on the same tracked attribute (a
//             blocker resolving, a commitment being fulfilled) - even
//             without contradiction language. This matches the spec's own
//             worked example: an explicit correction is an update.
//   CONFLICT - two claims about the same specific attribute, asserted with
//             no indication either one supersedes the other - genuine,
//             simultaneous disagreement, not sequential change. Neither
//             side reads as a deliberate correction of the other.
//
// The mistake in the first draft of this set was testing for contradiction
// language ("do these two claims disagree") instead of testing for
// supersession language ("does either claim announce itself as the newer,
// deliberate one") - the two are different questions, and the spec's own
// rubric asks the second one, not the first.

export interface ConflictCase {
  id: string;
  newMemory: { title: string; summary: string; valid_from: string };
  candidate: { title: string; summary: string; valid_from: string };
  expectedRelationship: "same_fact" | "update" | "conflict" | "different_concept";
}

export const CONFLICT_CASES: ConflictCase[] = [
  {
    id: "conf-01",
    newMemory: { title: "Public launch pushed to Sept 15", summary: "We're pushing it back - the public launch is now September 15th, not September 1st.", valid_from: "2026-08-10T00:00:00Z" },
    candidate: { title: "Public launch Sept 1", summary: "The public launch is September 1st.", valid_from: "2026-08-01T00:00:00Z" },
    expectedRelationship: "update",
  },
  {
    id: "conf-02",
    newMemory: { title: "Beta starts Sept 10", summary: "The beta program starts September 10th.", valid_from: "2026-08-05T00:00:00Z" },
    candidate: { title: "Public launch Sept 1", summary: "The public launch is September 1st.", valid_from: "2026-08-01T00:00:00Z" },
    expectedRelationship: "different_concept",
  },
  {
    id: "conf-03",
    newMemory: { title: "Public launch Sept 15, second claim", summary: "The public launch is definitely September 15th.", valid_from: "2026-08-08T00:00:00Z" },
    candidate: { title: "Public launch Sept 1, first claim", summary: "The public launch is September 1st.", valid_from: "2026-08-01T00:00:00Z" },
    expectedRelationship: "conflict",
  },
  {
    id: "conf-04",
    newMemory: { title: "Q3 revenue target restated", summary: "Q3 revenue target is $2M, as previously agreed.", valid_from: "2026-07-15T00:00:00Z" },
    candidate: { title: "Q3 revenue target set", summary: "The team agreed Q3 revenue target is $2M.", valid_from: "2026-07-01T00:00:00Z" },
    expectedRelationship: "same_fact",
  },
  {
    id: "conf-05",
    newMemory: { title: "Backend lead reassigned", summary: "Marcus Chen is now the backend team lead, replacing Sam Ortiz who moved to platform.", valid_from: "2026-06-15T00:00:00Z" },
    candidate: { title: "Backend lead named", summary: "Sam Ortiz is the backend team lead.", valid_from: "2026-05-01T00:00:00Z" },
    expectedRelationship: "update",
  },
  {
    // Corrected: originally labeled 'conflict', but "per the new contract"
    // is exactly the explicit-reason signal the rule above calls for -
    // this is a deliberate, announced change, not two simultaneous,
    // unexplained claims. The model's original 'update' answer was right;
    // the ground truth was wrong.
    id: "conf-06",
    newMemory: { title: "Data residency: EU only", summary: "Customer data must be stored in EU region only per the new contract.", valid_from: "2026-06-01T00:00:00Z" },
    candidate: { title: "Data residency: US and EU", summary: "Customer data can be stored in either US or EU region, customer's choice.", valid_from: "2026-05-20T00:00:00Z" },
    expectedRelationship: "update",
  },
  {
    // Corrected: originally labeled 'different_concept', intending "these
    // are unrelated facts." They're not - both describe the SAME
    // underlying blocker (the onboarding-flow blank screen), just at two
    // points in its lifecycle. A blocker resolving into a fixed state is
    // the state-transition case the rule above explicitly calls 'update',
    // not a different concept. The model's original 'update' answer was
    // right; the ground truth was wrong.
    id: "conf-07",
    newMemory: { title: "Onboarding flow fixed", summary: "The onboarding blank-screen bug is fixed and deployed to staging.", valid_from: "2026-08-19T00:00:00Z" },
    candidate: { title: "Onboarding flow blocked", summary: "The onboarding flow blocks new signups at the workspace-invite step with a blank screen.", valid_from: "2026-08-05T00:00:00Z" },
    expectedRelationship: "update",
  },
  {
    // New case, added to keep real conflict-category coverage from
    // shrinking to just conf-03 now that conf-06 moved to 'update' - two
    // flatly stated, equal-confidence claims with no reason clause and no
    // correction language on either side. Genuine, unresolved disagreement.
    id: "conf-08",
    newMemory: { title: "Q4 marketing budget set at $150K", summary: "Q4 marketing budget is $150K.", valid_from: "2026-09-01T00:00:00Z" },
    candidate: { title: "Q4 marketing budget set at $200K", summary: "Q4 marketing budget is $200K.", valid_from: "2026-08-28T00:00:00Z" },
    expectedRelationship: "conflict",
  },
];

// ── Category 4: Loci query patterns 3/5/7 (deterministic, no extraction) ──
// The starter_events fixture set doesn't naturally produce a Rationale
// memory, a Customer entity, or a stable "prior answer" state - these
// synthetic cases decouple pattern verification from extraction's own
// per-call, unpredictable type classification (same reasoning as the
// TEMPORAL_CHAIN cases above).

const ACME: EntityRef = { entity_id: "eval-entity-acme", entity_type: "Customer", canonical_name: "Acme Corp" };
const FLYIO: EntityRef = { entity_id: "eval-entity-flyio", entity_type: "Project", canonical_name: "Fly.io migration" };

export const LOCI_PATTERN_MEMORIES: CanonicalMemoryObject[] = [
  mem({ memory_id: "loci-decision-1", type: "Decision", entities: [FLYIO], valid_from: "2026-07-01T10:00:00Z", title: "Move to Fly.io", summary: "Decided to move hosting from Heroku to Fly.io.", payload: { attribute_key: "hosting_provider" } }),
  mem({ memory_id: "loci-rationale-1", type: "Rationale", entities: [FLYIO], valid_from: "2026-07-01T10:05:00Z", title: "Why Fly.io over Render", summary: "Fly.io has better multi-region support, needed for EU customer latency.", payload: { attribute_key: "hosting_provider_rationale" } }),
  mem({ memory_id: "loci-commitment-acme-1", type: "Commitment", entities: [ACME], status: "current", valid_from: "2026-07-04T13:00:00Z", title: "Raise Acme's API rate limit", summary: "Committed to raising Acme Corp's API rate limit by end of month.", payload: { attribute_key: "acme_rate_limit", due_date: "2026-07-31" } }),
  mem({ memory_id: "loci-commitment-acme-2-superseded", type: "Commitment", entities: [ACME], status: "superseded", valid_from: "2026-06-01T00:00:00Z", title: "Old Acme commitment", summary: "An earlier, now-superseded commitment to Acme Corp.", payload: { attribute_key: "acme_old_commitment" } }),
];

export interface LociPatternCase {
  id: string;
  pattern: "why_changed" | "customer_commitments" | "evidence_for_answer";
  entityId: string;
  expectSuccess: boolean;
  expectedMemoryIdIncluded: string;
}

export const LOCI_PATTERN_CASES: LociPatternCase[] = [
  { id: "loci-pat-03", pattern: "why_changed", entityId: FLYIO.entity_id, expectSuccess: true, expectedMemoryIdIncluded: "loci-rationale-1" },
  { id: "loci-pat-05", pattern: "customer_commitments", entityId: ACME.entity_id, expectSuccess: true, expectedMemoryIdIncluded: "loci-commitment-acme-1" },
  { id: "loci-pat-07", pattern: "evidence_for_answer", entityId: FLYIO.entity_id, expectSuccess: true, expectedMemoryIdIncluded: "loci-decision-1" },
];
