// supabase/functions/_shared/memory/historicalReplay.ts
//
// Read-only, one-time pull of real raw_events, reshaped into the spec's
// NormalizedEvent contract, so the fixture set includes real content
// alongside hand-written cases (plan Batch 1, refinement 1). Writes
// NOTHING back to raw_events or any other live table - the only output is
// an in-memory NormalizedEvent[] the caller feeds into extraction, same as
// any hand-written fixture. Never touches decisions/ai-worker/the live
// ingestion queue.

import { withAdmin } from "../db.ts";
import { cleanDisplayText } from "../htmlText.ts";
import { byteaToUint8Array, decryptRawContent } from "./crypto.ts";

export interface NormalizedEvent {
  tenant_id: string;
  source: string;
  source_id: string;
  actor: { id: string; display_name: string };
  thread_ref: string | null;
  permission_scope: string[];
  raw_content: string;
  occurred_at: string;
}

// deno-lint-ignore no-explicit-any
function notionPropertyText(prop: any): string | null {
  if (!prop || typeof prop !== "object") return null;
  switch (prop.type) {
    case "title":
    case "rich_text": {
      const parts = (prop[prop.type] ?? []).map((t: { plain_text?: string }) => t.plain_text).filter(Boolean);
      return parts.length > 0 ? parts.join("") : null;
    }
    case "select":
      return prop.select?.name ?? null;
    case "status":
      return prop.status?.name ?? null;
    case "date":
      return prop.date?.start ?? null;
    default:
      return null;
  }
}

// deno-lint-ignore no-explicit-any
function extractNotionPageText(page: any): string {
  const properties = page.properties ?? {};
  // deno-lint-ignore no-explicit-any
  const titleEntry = Object.entries(properties).find(([, p]: [string, any]) => p?.type === "title");
  const title = titleEntry ? notionPropertyText(titleEntry[1]) : null;
  const lines: string[] = [];
  if (title) lines.push(title);
  for (const [name, prop] of Object.entries(properties)) {
    if (titleEntry && name === titleEntry[0]) continue;
    const value = notionPropertyText(prop);
    if (value) lines.push(`${name}: ${value}`);
  }
  return lines.length > 0 ? lines.join("\n") : (page.url ?? "Notion page");
}

// Same field-extraction rules as api/index.ts's extractEventText - Gmail
// gets its subject prefixed, Notion reads page properties, everything else
// falls back to the first populated text-shaped field.
function extractEventText(rawContent: unknown, source: string): string {
  if (!rawContent || typeof rawContent !== "object") return cleanDisplayText(String(rawContent ?? ""));
  const content = rawContent as Record<string, unknown>;
  if (source === "gmail") {
    const subject = typeof content.subject === "string" ? content.subject : "";
    const body = typeof content.body === "string" ? cleanDisplayText(content.body) : "";
    return subject ? `Subject: ${subject}\n${body}` : body;
  }
  if (source === "notion" && "properties" in content) {
    return cleanDisplayText(extractNotionPageText(content));
  }
  for (const field of ["text", "body", "content", "message", "description", "snippet"]) {
    const val = content[field];
    if (typeof val === "string" && val) return cleanDisplayText(val);
  }
  return cleanDisplayText(JSON.stringify(content));
}

/**
 * Pulls up to `perSourceLimit` of the most recent raw_events per source for
 * one tenant, decrypts them, and reshapes into NormalizedEvent. Read-only:
 * a single SELECT, no UPDATE/DELETE/INSERT against raw_events or any other
 * live table anywhere in this function.
 */
export async function replayHistoricalEvents(
  tenantId: string,
  perSourceLimit = 15,
): Promise<NormalizedEvent[]> {
  return await withAdmin(async (sql) => {
    const rows = await sql`
      select re.id, re.tenant_id, re.source, re.source_id, re.thread_ref,
             re.permission_scope, re.raw_content, re.received_at,
             a.id as actor_uuid, a.display_name, a.email
      from public.raw_events re
      left join public.actors a on a.id = re.actor_id
      where re.tenant_id = ${tenantId}
        and re.source in ('slack', 'gmail', 'notion')
      order by re.source, re.received_at desc
    `;

    // Cap per source client-side (simpler than a window function here,
    // and this only ever runs against a bounded, one-time sample).
    const perSourceCounts: Record<string, number> = {};
    const events: NormalizedEvent[] = [];

    for (const row of rows) {
      const source = row.source as string;
      perSourceCounts[source] = (perSourceCounts[source] ?? 0) + 1;
      if (perSourceCounts[source] > perSourceLimit) continue;

      let plainText: string;
      try {
        const encrypted = byteaToUint8Array(row.raw_content);
        const decrypted = await decryptRawContent(encrypted);
        let parsed: unknown = decrypted;
        try {
          parsed = JSON.parse(decrypted);
        } catch {
          // Some rows may already be plain text rather than a JSON envelope.
        }
        plainText = extractEventText(parsed, source);
      } catch (err) {
        console.error(`historicalReplay: failed to decrypt raw_events.id=${row.id}:`, err);
        continue; // skip unreadable rows rather than fail the whole replay
      }

      if (!plainText || plainText === "(no readable message content captured)") continue;

      events.push({
        tenant_id: tenantId,
        source,
        source_id: row.source_id as string,
        actor: {
          id: (row.actor_uuid as string | null) ?? "",
          display_name: (row.display_name as string | null) ?? (row.email as string | null) ?? "unknown",
        },
        thread_ref: (row.thread_ref as string | null) ?? null,
        permission_scope: (row.permission_scope as string[] | null) ?? [],
        raw_content: plainText,
        occurred_at: new Date(row.received_at as string).toISOString(),
      });
    }

    return events;
  });
}
