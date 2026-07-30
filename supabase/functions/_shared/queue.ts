// supabase/functions/_shared/queue.ts
//
// Every connector enqueues through this one path (INGESTION_CONTRACT.md).
// Uses DATABASE_URL / admin SQL so pgmq.send works without service_role
// table access on public.* tenant tables.

import { withAdmin } from "./db.ts";

export interface IngestionEnvelope {
  tenant_id: string;
  source: "slack" | "gmail" | "notion";
  source_id: string;
  actor: string;
  thread_ref: string;
  // Matches the Python EventEnvelope model (backend/src/modules/ingestion/
  // envelope/schemas.py) that actually consumes these messages: a list of
  // permission identifiers, and the raw payload as an object, not a string.
  permission_scope: string[];
  raw_content: Record<string, unknown>;
  received_at: string; // ISO timestamp
}

export async function enqueueEvent(envelope: IngestionEnvelope) {
  try {
    await withAdmin(async (sql) => {
      // sql.json() wants postgres.js's own JSONValue type, which a plain
      // named interface never structurally satisfies (missing index
      // signature) regardless of field types — pre-existing gap, unrelated
      // to the envelope's actual field shapes. Cast, not a runtime change.
      await sql`select pgmq.send('ingestion', ${sql.json(envelope as any)}::jsonb)`;
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(`Failed to enqueue event: ${message}`);
  }
}
