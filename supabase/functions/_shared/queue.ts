// supabase/functions/_shared/queue.ts
//
// NOTE FOR REBIRA: Same deal as supabase.ts — this mirrors Sudhira's
// queue.ts from PR #4. Once that PR merges, use the real shared file
// instead of this copy. This is what INGESTION_CONTRACT.md requires:
// every connector enqueues through this one RPC, never Redis, never a
// standalone "ingestEvent()" function.

import { getServiceClient } from "./supabase.ts";

export interface IngestionEnvelope {
  tenant_id: string;
  source: "slack" | "gmail" | "notion";
  source_id: string;
  actor: string;
  thread_ref: string;
  permission_scope: string;
  raw_content: string;
  received_at: string; // ISO timestamp
}

export async function enqueueEvent(envelope: IngestionEnvelope) {
  const supabase = getServiceClient();

  const { error } = await supabase.rpc("enqueue_ingestion_event", {
    envelope,
  });

  if (error) {
    // Don't swallow this — a failed enqueue means the event is lost.
    // Caller should log this loudly and consider retry/dead-letter handling.
    throw new Error(`Failed to enqueue event: ${error.message}`);
  }
}
