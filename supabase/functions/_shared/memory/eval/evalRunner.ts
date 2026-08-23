// supabase/functions/_shared/memory/eval/evalRunner.ts
//
// The actual scoring logic, factored out of runEval.ts so both the CLI
// entry point (`deno run runEval.ts`, per spec Section 12's "run it")
// and memory-api's POST /eval/run debug endpoint call the same code -
// the endpoint exists because ANTHROPIC_API_KEY is only available as a
// deployed Edge Function secret, not in a local shell, so running this
// for real means running it where the secret actually is.

import { extractMemory } from "../extraction.ts";
import { classifyRelation } from "../reconcile.ts";
import { getCurrentState, getStateAsOf } from "../temporalQueries.ts";
import {
  EXTRACTION_CASES, TEMPORAL_CASES, TEMPORAL_CHAIN, CONFLICT_CASES,
  LOCI_PATTERN_CASES, LOCI_PATTERN_MEMORIES,
} from "./goldenSet.ts";
import { answerWhyChanged, answerCustomerCommitments, answerEvidenceForAnswer } from "../lociPatterns.ts";

export interface CategoryResult {
  total: number;
  correct: number;
  failures: string[];
}

export async function runExtractionCases(): Promise<CategoryResult> {
  let correct = 0;
  const failures: string[] = [];
  for (const c of EXTRACTION_CASES) {
    try {
      const result = await extractMemory({
        source: c.source, actorDisplayName: c.actorDisplayName, threadRef: null,
        permissionScope: [], rawContent: c.rawContent, occurredAt: c.occurredAt,
      });
      const actualOutcome = result.decision === "DISCARD" ? "DISCARD" : "KEEP";
      const typeMatches = c.expectedOutcome === "DISCARD" || result.type === c.expectedType;
      const outcomeMatches = actualOutcome === c.expectedOutcome || (c.expectedOutcome === "KEEP" && actualOutcome !== "DISCARD");

      const findMention = (text: string) =>
        result.entities.find((e) => e.mention_text.toLowerCase().includes(text.toLowerCase()));
      const subjectFailures = (c.expectedSubjectMentions ?? []).filter((text) => {
        const found = findMention(text);
        return !found || found.role !== "subject";
      });
      const referencedFailures = (c.expectedReferencedOrAbsent ?? []).filter((text) => {
        const found = findMention(text);
        return found && found.role !== "referenced"; // present as "subject" is the failure; absent is fine
      });

      if (outcomeMatches && typeMatches && subjectFailures.length === 0 && referencedFailures.length === 0) {
        correct++;
      } else {
        const entityDetail = [
          ...subjectFailures.map((t) => `"${t}" not extracted as subject`),
          ...referencedFailures.map((t) => `"${t}" wrongly extracted as subject`),
        ];
        failures.push(`${c.id}: expected ${c.expectedOutcome}/${c.expectedType}, got ${actualOutcome}/${result.type}${entityDetail.length ? `; ${entityDetail.join(", ")}` : ""}`);
      }
    } catch (err) {
      failures.push(`${c.id}: threw ${err instanceof Error ? err.message : String(err)}`);
    }
  }
  return { total: EXTRACTION_CASES.length, correct, failures };
}

export function runTemporalCases(): CategoryResult {
  let correct = 0;
  const failures: string[] = [];
  for (const c of TEMPORAL_CASES) {
    let actualId: string | undefined;
    if (c.fn === "getCurrentState") {
      const attributeKey = c.id === "temp-07" ? "some_other_attribute" : "launch_date";
      const result = getCurrentState(TEMPORAL_CHAIN, "eval-entity-project-x", "Decision", attributeKey);
      actualId = result?.memory_id;
    } else {
      const results = getStateAsOf(TEMPORAL_CHAIN, "eval-entity-project-x", c.targetDate as string);
      actualId = results[0]?.memory_id;
    }
    if (actualId === c.expectedMemoryId) {
      correct++;
    } else {
      failures.push(`${c.id} (${c.description}): expected ${c.expectedMemoryId}, got ${actualId}`);
    }
  }
  return { total: TEMPORAL_CASES.length, correct, failures };
}

export async function runConflictCases(): Promise<CategoryResult> {
  let correct = 0;
  const failures: string[] = [];
  for (const c of CONFLICT_CASES) {
    try {
      const classifications = await classifyRelation(c.newMemory, [
        { memory_id: "candidate-1", title: c.candidate.title, summary: c.candidate.summary, valid_from: c.candidate.valid_from },
      ]);
      const actual = classifications[0]?.relationship;
      if (actual === c.expectedRelationship) {
        correct++;
      } else {
        failures.push(`${c.id}: expected ${c.expectedRelationship}, got ${actual}`);
      }
    } catch (err) {
      failures.push(`${c.id}: threw ${err instanceof Error ? err.message : String(err)}`);
    }
  }
  return { total: CONFLICT_CASES.length, correct, failures };
}

export function runLociPatternCases(): CategoryResult {
  let correct = 0;
  const failures: string[] = [];
  for (const c of LOCI_PATTERN_CASES) {
    const result = c.pattern === "why_changed"
      ? answerWhyChanged(LOCI_PATTERN_MEMORIES, c.entityId)
      : c.pattern === "customer_commitments"
      ? answerCustomerCommitments(LOCI_PATTERN_MEMORIES, c.entityId)
      : answerEvidenceForAnswer(LOCI_PATTERN_MEMORIES, c.entityId);
    const succeeded = result !== null;
    const includesExpected = result?.memoriesUsed.some((m) => m.memory_id === c.expectedMemoryIdIncluded) ?? false;
    if (succeeded === c.expectSuccess && includesExpected) {
      correct++;
    } else {
      failures.push(`${c.id}: succeeded=${succeeded} (expected ${c.expectSuccess}), includesExpected=${includesExpected}`);
    }
  }
  return { total: LOCI_PATTERN_CASES.length, correct, failures };
}

export interface GoldenEvalReport {
  extraction: CategoryResult;
  temporal: CategoryResult;
  conflict: CategoryResult;
  lociPatterns: CategoryResult;
  overall: { total: number; correct: number; percent: number };
}

export async function runGoldenEval(): Promise<GoldenEvalReport> {
  const extraction = await runExtractionCases();
  const temporal = runTemporalCases();
  const conflict = await runConflictCases();
  const lociPatterns = runLociPatternCases();
  const total = extraction.total + temporal.total + conflict.total + lociPatterns.total;
  const correct = extraction.correct + temporal.correct + conflict.correct + lociPatterns.correct;
  return { extraction, temporal, conflict, lociPatterns, overall: { total, correct, percent: Math.round((correct / total) * 100) } };
}
