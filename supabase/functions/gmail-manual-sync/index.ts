import { withAdmin, withTenant } from "../_shared/db.ts";
import { enqueueEvent, IngestionEnvelope } from "../_shared/queue.ts";

console.log("Gmail manual sync started!");

Deno.serve(async (_req) => {
  // Cross-tenant list of active Gmail connections (admin / bypass)
  const sources = await withAdmin(async (sql) => {
    return await sql`
      select *
      from public.source_connections
      where source = 'gmail'
        and status = 'active'
    `;
  });

  const results = [];

  for (const source of sources) {
    try {
      console.log(`Syncing Gmail: ${source.external_workspace_id}`);

      const accessToken = source.oauth_token_ref;
      if (!accessToken) {
        console.error(`No access token for source ${source.id}`);
        continue;
      }

      const listResp = await fetch(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=10",
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );

      if (!listResp.ok) {
        console.error(`Gmail list error for ${source.id}:`, await listResp.text());
        continue;
      }

      const listData = await listResp.json();
      const messages = listData.messages || [];
      console.log(`Found ${messages.length} recent messages for ${source.id}`);

      let syncedCount = 0;

      for (const msgMeta of messages) {
        const msgResp = await fetch(
          `https://gmail.googleapis.com/gmail/v1/users/me/messages/${msgMeta.id}?format=full`,
          { headers: { Authorization: `Bearer ${accessToken}` } },
        );
        if (!msgResp.ok) {
          console.error(`Failed to fetch message ${msgMeta.id}:`, await msgResp.text());
          continue;
        }
        const rawMsg = await msgResp.json();

        const headers = rawMsg.payload?.headers || [];
        const getHeader = (name: string) =>
          headers.find((h: { name?: string; value?: string }) =>
            h.name?.toLowerCase() === name.toLowerCase()
          )?.value || "";

        let body = "";
        const payload = rawMsg.payload || {};
        if (payload.body?.data) {
          body = atob(payload.body.data.replace(/-/g, "+").replace(/_/g, "/"));
        } else if (payload.parts) {
          const textPart = payload.parts.find(
            (p: { mimeType?: string; body?: { data?: string } }) =>
              p.mimeType === "text/plain" && p.body?.data,
          );
          if (textPart) {
            body = atob(textPart.body.data.replace(/-/g, "+").replace(/_/g, "/"));
          }
        }
        if (!body) body = rawMsg.snippet || "";

        const fromHeader = getHeader("From");
        const actorMatch = fromHeader.match(/<(.+)>/);
        const actor = actorMatch ? actorMatch[1] : fromHeader;

        const envelope: IngestionEnvelope = {
          tenant_id: source.tenant_id,
          source: "gmail",
          source_id: rawMsg.id,
          actor: actor || "unknown",
          thread_ref: rawMsg.threadId,
          permission_scope: source.external_workspace_id,
          raw_content: JSON.stringify({
            subject: getHeader("Subject"),
            body,
            from: fromHeader,
            to: getHeader("To"),
            date: getHeader("Date"),
            snippet: rawMsg.snippet,
          }),
          received_at: new Date().toISOString(),
        };

        await enqueueEvent(envelope);
        syncedCount++;
      }

      await withTenant(String(source.tenant_id), async (sql) => {
        await sql`
          update public.source_connections
          set last_synced_at = ${new Date().toISOString()}
          where id = ${source.id}
        `;
      });

      results.push({ source_id: source.id, messages_synced: syncedCount });
    } catch (err) {
      console.error(`Error syncing source ${source.id}:`, err);
    }
  }

  return new Response(JSON.stringify({ message: "Sync completed", results }), {
    headers: { "Content-Type": "application/json" },
  });
});
