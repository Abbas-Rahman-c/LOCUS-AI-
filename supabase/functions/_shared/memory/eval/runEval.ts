// supabase/functions/_shared/memory/eval/runEval.ts
//
// Spec Section 12's golden evaluation set, actually run. Prints a real
// scored report - this is what "before this is considered done" means:
// numbers from an execution, not a description of what the eval would
// probably show.
//
// Run with: deno run --allow-net --allow-env supabase/functions/_shared/memory/eval/runEval.ts
// Needs ANTHROPIC_API_KEY (and optionally ANTHROPIC_EXTRACT_MODEL) in the
// environment - extraction and conflict-detection cases make real Claude
// calls, same as the live pipeline. If running locally without the key,
// use memory-api's POST /eval/run instead, which runs the exact same
// logic where the secret is actually configured.

import { runGoldenEval } from "./evalRunner.ts";

function printCategory(name: string, result: { total: number; correct: number; failures: string[] }) {
  console.log(`\n--- ${name} ---`);
  console.log(`${result.correct}/${result.total} correct (${Math.round((result.correct / result.total) * 100)}%)`);
  result.failures.forEach((f) => console.log(`  FAIL: ${f}`));
}

async function main() {
  console.log("=== Golden Evaluation Set (spec Section 12) ===");
  const report = await runGoldenEval();
  printCategory("Extraction precision", report.extraction);
  printCategory("Current-state / temporal accuracy", report.temporal);
  printCategory("Conflict-detection precision", report.conflict);
  printCategory("Loci query patterns 3/5/7 (deterministic)", report.lociPatterns);
  console.log(`\n=== Overall: ${report.overall.correct}/${report.overall.total} (${report.overall.percent}%) ===`);
}

await main();
