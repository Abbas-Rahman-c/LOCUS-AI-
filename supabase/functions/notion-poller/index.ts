import { withAdmin, withTenant } from "../_shared/db.ts";
import { enqueueEvent, IngestionEnvelope } from "../_shared/queue.ts";

console.log("Notion poller started!");

Deno.serve(async (_req) => {
  const sources = await withAdmin(async (sql) => {
    return await sql`
      select *
      from public.source_connections
      where source = 'notion'
        and status = 'active'
        and ingestion_mode = 'polling'
    `;
  });

  const results = [];

  for (const source of sources) {
    try {
      console.log(`Polling workspace: ${source.external_workspace_id}`);

      const accessToken = source.oauth_token_ref;
      if (!accessToken) {
        console.error(`No access token for source ${source.id}`);
        continue;
      }

      const lastSyncedAt = source.last_synced_at || new Date(0).toISOString();
      const response = await fetch("https://api.notion.com/v1/search", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Notion-Version": "2022-06-28",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          sort: {
            direction: "ascending",
            timestamp: "last_edited_time",
          },
          filter: {
            value: "page",
            property: "object",
          },
        }),
      });

      if (!response.ok) {
        console.error(
          `Notion API error for ${source.id}:`,
          await response.text(),
        );
        continue;
      }

      const data = await response.json();
      const pages = data.results.filter(
        (page: { last_edited_time: string }) =>
          new Date(page.last_edited_time) > new Date(lastSyncedAt),
      );

      console.log(`Found ${pages.length} changed pages for ${source.id}`);

      for (const page of pages) {
        const envelope: IngestionEnvelope = {
          tenant_id: source.tenant_id,
          source: "notion",
          source_id: source.id,
          actor: page.last_edited_by?.id || "unknown",
          thread_ref: page.id,
          permission_scope: source.external_workspace_id,
          raw_content: JSON.stringify(page),
          received_at: new Date().toISOString(),
        };
        await enqueueEvent(envelope);
      }

      if (pages.length > 0) {
        const latestTime = pages[pages.length - 1].last_edited_time;
        await withTenant(String(source.tenant_id), async (sql) => {
          await sql`
            update public.source_connections
            set last_synced_at = ${latestTime}
            where id = ${source.id}
          `;
        });
      }

      results.push({ source_id: source.id, changed_pages: pages.length });
    } catch (err) {
      console.error(`Error polling source ${source.id}:`, err);
    }
  }

  return new Response(JSON.stringify({ message: "Poll completed", results }), {
    headers: { "Content-Type": "application/json" },
  });
});
