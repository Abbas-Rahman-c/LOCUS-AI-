// supabase/functions/_shared/memory/lociPatterns.ts
//
// Spec Section 9's seven query patterns, literally. Each answers from the
// memory layer specifically - never a fallback to generic RAG over raw
// source content, per the spec's own instruction ("must handle these query
// patterns against the memory layer specifically"). Answers are templated
// from each memory's own title/summary (already Claude-authored at
// extraction time) rather than a second synthesis call per query - this
// codebase's own cost-conscious convention (see loci-chat's pricing-section
// comment for the same reasoning applied elsewhere).
//
// Every function here takes an already-permission-filtered memory list -
// callers (handleSearch in api/index.ts) are responsible for calling
// isMemoryAccessible() first. Nothing in this file re-checks permissions,
// so never call these with an unfiltered list.

import type { CanonicalMemoryObject, MemoryType } from "./types.ts";
import { getChangesSince, getCurrentState } from "./temporalQueries.ts";
import { loadMemoriesForTenant } from "./loadMemories.ts";
import { isMemoryAccessibleBatch } from "./permissions.ts";

export type LociPattern =
  | "changes_since"
  | "current_and_previous"
  | "why_changed"
  | "invalid_assumptions"
  | "customer_commitments"
  | "catch_me_up"
  | "evidence_for_answer";

export interface LociAnswer {
  pattern: LociPattern;
  answer: string;
  memoriesUsed: CanonicalMemoryObject[];
}

// Builds a short narrative paragraph with inline [N] citation markers,
// matching the existing decisions-path convention ([Decision N]) instead
// of a bare list of matched records. Each call appends one memory to the
// running `used` array and returns the marker text for it - callers stay
// in control of connective wording, this just keeps the numbering
// consistent with memoriesUsed's real, final order (the same array the
// caller returns as memory_citations, so citation numbers always match).
function citeMemory(used: CanonicalMemoryObject[], memory: CanonicalMemoryObject): string {
  used.push(memory);
  return `[${used.length}]`;
}

/** Finds the entity whose canonical_name (or an alias, matched earlier by
 * the caller's SQL lookup) best matches a free-text name pulled out of the
 * user's question by analyzeQuery. Returns null if nothing in the
 * (already entity-filtered) memory list matches - callers fall through to
 * the existing decisions RAG path rather than answering with nothing. */
export function resolveEntityIdByName(
  memories: CanonicalMemoryObject[],
  entityName: string,
): string | null {
  const needle = entityName.trim().toLowerCase();
  if (!needle) return null;
  for (const m of memories) {
    for (const e of m.entities) {
      if (e.canonical_name.toLowerCase() === needle) return e.entity_id;
    }
  }
  // Fall back to a substring match (either direction) - "the launch" vs
  // "Q3 Launch" shouldn't both be dead ends just because they're not an
  // exact string match.
  for (const m of memories) {
    for (const e of m.entities) {
      const name = e.canonical_name.toLowerCase();
      if (name.includes(needle) || needle.includes(name)) return e.entity_id;
    }
  }
  return null;
}

// Pattern 1: "What changed with Project X this week?"
export function answerChangesSince(
  memories: CanonicalMemoryObject[],
  entityId: string,
  sinceIso: string,
): LociAnswer | null {
  const changes = getChangesSince(memories, entityId, sinceIso);
  if (changes.length === 0) return null;
  const used: CanonicalMemoryObject[] = [];
  const sentences = changes.map((c) => {
    if (c.previous) {
      const prevCite = citeMemory(used, c.previous);
      const curCite = citeMemory(used, c.current);
      return `It moved from "${c.previous.summary}" ${prevCite} to "${c.current.summary}" ${curCite}.`;
    }
    return `${c.current.summary} ${citeMemory(used, c.current)}`;
  });
  return { pattern: "changes_since", answer: sentences.join(" "), memoriesUsed: used };
}

// Pattern 2: "What is the current state and what was the previous state?"
// getCurrentState() needs an explicit type - a natural question rarely
// names one, so this checks every type for the entity and returns
// whichever current memory has the most recent valid_from with a real
// supersedes hop to show as "previous" (falls back to just current if none
// of the entity's current memories supersede anything).
export function answerCurrentAndPrevious(
  memories: CanonicalMemoryObject[],
  entityId: string,
  now: Date = new Date(),
): LociAnswer | null {
  const ALL_TYPES: MemoryType[] = [
    "Context", "Change", "Commitment", "Decision", "Rationale", "Blocker", "Outcome", "Requirement", "CustomerSignal",
  ];
  const currentByType = ALL_TYPES
    .map((t) => getCurrentState(memories, entityId, t, undefined, now))
    .filter((m): m is CanonicalMemoryObject => m !== undefined);
  if (currentByType.length === 0) return null;

  const withSupersedes = currentByType.filter((m) => m.supersedes);
  const target = withSupersedes[0] ?? currentByType[0];
  const previous = target.supersedes ? memories.find((m) => m.memory_id === target.supersedes) ?? null : null;

  const used: CanonicalMemoryObject[] = [];
  const answer = previous
    ? `Right now: ${target.summary} ${citeMemory(used, target)} Before that: ${previous.summary} ${citeMemory(used, previous)}`
    : `${target.summary} ${citeMemory(used, target)} No earlier version is on record.`;
  return { pattern: "current_and_previous", answer, memoriesUsed: used };
}

// Pattern 3: "Why did this change?" - Rationale memories sharing the same
// entity, closest in valid_from to the entity's most recent change.
export function answerWhyChanged(memories: CanonicalMemoryObject[], entityId: string): LociAnswer | null {
  const entityMemories = memories.filter((m) => m.entities.some((e) => e.entity_id === entityId));
  const mostRecentChange = entityMemories
    .filter((m) => m.type === "Change" || m.type === "Decision")
    .sort((a, b) => b.valid_from.localeCompare(a.valid_from))[0];

  const rationales = entityMemories.filter((m) => m.type === "Rationale");
  if (rationales.length === 0) return null;

  const anchor = mostRecentChange?.valid_from ?? rationales[0].valid_from;
  const nearest = rationales
    .slice()
    .sort((a, b) => Math.abs(new Date(a.valid_from).getTime() - new Date(anchor).getTime())
      - Math.abs(new Date(b.valid_from).getTime() - new Date(anchor).getTime()));

  const used: CanonicalMemoryObject[] = [];
  // Only cite mostRecentChange if it's actually referenced in the text
  // below - citing something never mentioned in the narrative would be
  // exactly the "citation doesn't match what's said" problem this
  // rewrite exists to avoid.
  const intro = mostRecentChange ? `Regarding "${mostRecentChange.summary}" ${citeMemory(used, mostRecentChange)}: ` : "";
  const reasons = nearest.map((r) => `${r.summary} ${citeMemory(used, r)}`).join(" Also, ");
  return { pattern: "why_changed", answer: `${intro}${reasons}`, memoriesUsed: used };
}

// Pattern 4: "What assumptions are no longer valid?" - superseded OR stale,
// typically Context/Requirement per spec, but the filter itself is
// status/freshness only (spec says "typically", not "only").
export function answerInvalidAssumptions(memories: CanonicalMemoryObject[], entityId?: string): LociAnswer | null {
  const scoped = entityId ? memories.filter((m) => m.entities.some((e) => e.entity_id === entityId)) : memories;
  const invalid = scoped.filter((m) => m.status === "superseded" || m.freshness === "stale");
  if (invalid.length === 0) return null;
  const used: CanonicalMemoryObject[] = [];
  const sentences = invalid.map((m) => {
    const label = m.status === "superseded" ? "no longer current" : "hasn't been re-confirmed in a while";
    return `${m.summary} ${citeMemory(used, m)} - ${label}.`;
  });
  return { pattern: "invalid_assumptions", answer: sentences.join(" "), memoriesUsed: used };
}

// Pattern 5: "What commitments have we made to this customer?"
export function answerCustomerCommitments(memories: CanonicalMemoryObject[], customerEntityId: string): LociAnswer | null {
  const commitments = memories.filter((m) =>
    m.type === "Commitment" &&
    m.status !== "superseded" &&
    m.entities.some((e) => e.entity_id === customerEntityId && e.entity_type === "Customer")
  );
  if (commitments.length === 0) return null;
  const used: CanonicalMemoryObject[] = [];
  const sentences = commitments.map((m) => `${m.summary} ${citeMemory(used, m)}`);
  return { pattern: "customer_commitments", answer: sentences.join(" "), memoriesUsed: used };
}

// Pattern 6: "Catch me up on what matters since [date]" - tenant-wide, not
// entity-scoped (unlike pattern 1) per the spec's own example question.
export function answerCatchMeUp(memories: CanonicalMemoryObject[], sinceIso: string): LociAnswer | null {
  const relevant = memories.filter((m) =>
    m.valid_from > sinceIso && (m.type === "Blocker" || m.type === "Outcome" || m.type === "Decision" || m.supersedes)
  );
  if (relevant.length === 0) return null;
  const sorted = relevant.slice().sort((a, b) => b.valid_from.localeCompare(a.valid_from));
  const used: CanonicalMemoryObject[] = [];
  const sentences = sorted.map((m) => `${m.summary} ${citeMemory(used, m)}`);
  return { pattern: "catch_me_up", answer: sentences.join(" "), memoriesUsed: used };
}

// Pattern 7: "What evidence supports this answer?" - /search is stateless
// (no conversation memory), so there is no literal "this answer" to refer
// back to within one request. The closest sound single-turn reading: show
// the resolved entity's current-state memories with full citations
// attached, which is exactly the evidence a prior current-state answer
// would have used. A true multi-turn "evidence for THAT SPECIFIC answer"
// needs session state /search doesn't have - flagged here, not silently
// pretended away.
export function answerEvidenceForAnswer(memories: CanonicalMemoryObject[], entityId: string, now: Date = new Date()): LociAnswer | null {
  const current = answerCurrentAndPrevious(memories, entityId, now);
  if (!current) return null;
  return { ...current, pattern: "evidence_for_answer" };
}

// ── Dispatcher, called from handleSearch's Loci pre-step ────────────────
//
// Loads every memory the caller can currently see (isMemoryAccessible
// re-checked fresh, same as every other read path - never cached from
// write time), resolves the question's target entity name against them,
// and routes to the matching pattern function. Returns null whenever
// nothing in the memory layer can answer this - handleSearch's contract is
// to fall through to the existing, unmodified decisions RAG path on null,
// never to answer with an empty/apologetic response of its own.

export interface LociQueryInput {
  pattern: LociPattern;
  targetEntityName: string | null;
  sinceDate: string | null; // ISO date, if the question named one
}

export async function answerLociQuery(
  // deno-lint-ignore no-explicit-any
  sql: any,
  tenantId: string,
  permissionScopes: string[],
  input: LociQueryInput,
  now: Date = new Date(),
): Promise<LociAnswer | null> {
  const allMemories = await loadMemoriesForTenant(sql, tenantId);
  const accessFlags = await isMemoryAccessibleBatch(sql, tenantId, permissionScopes, allMemories.map((m) => m.permissions.visible_to));
  const memories = allMemories.filter((_, i) => accessFlags[i]);
  if (memories.length === 0) return null;

  // catch_me_up is tenant-wide by design (spec's own example question)-
  // every other pattern needs a resolved entity first.
  if (input.pattern === "catch_me_up") {
    const sinceIso = input.sinceDate ?? new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
    return answerCatchMeUp(memories, sinceIso);
  }

  const entityId = input.targetEntityName ? resolveEntityIdByName(memories, input.targetEntityName) : null;
  if (!entityId && input.pattern !== "invalid_assumptions") return null;

  switch (input.pattern) {
    case "changes_since": {
      const sinceIso = input.sinceDate ?? new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
      return entityId ? answerChangesSince(memories, entityId, sinceIso) : null;
    }
    case "current_and_previous":
      return entityId ? answerCurrentAndPrevious(memories, entityId, now) : null;
    case "why_changed":
      return entityId ? answerWhyChanged(memories, entityId) : null;
    case "invalid_assumptions":
      return answerInvalidAssumptions(memories, entityId ?? undefined);
    case "customer_commitments":
      return entityId ? answerCustomerCommitments(memories, entityId) : null;
    case "evidence_for_answer":
      return entityId ? answerEvidenceForAnswer(memories, entityId, now) : null;
    default:
      return null;
  }
}
