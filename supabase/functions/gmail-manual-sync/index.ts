import { getServiceClient } from "../_shared/supabase.ts";
import { enqueueEvent, IngestionEnvelope } from "../_shared/queue.ts";

console.log("Gmail manual sync started!");

Deno.serve(async (req) => {
  const supabase = getServiceClient();

  // 1. Fetch active Gmail connections
  const { data: sources, error: sourcesError } = await supabase
    .from("source_connections")
    .select("*")
    .eq("source", "gmail")
    .eq("status", "active");

  if (sourcesError) {
    console.error("Failed to fetch sources:", sourcesError);
    return new Response(JSON.stringify({ error: sourcesError }), { status: 500 });
  }

  const results = [];

  for (const source of sources) {
    try {
      console.log(`Syncing Gmail: ${source.external_workspace_id}`);

      const accessToken = source.oauth_token_ref;
      if (!accessToken) {
        console.error(`No access token for source ${source.id}`);
        continue;
      }

      // 2. List recent messages
      const listResp = await fetch(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=10",
        { headers: { Authorization: `Bearer ${accessToken}` } }
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
        // 3. Fetch full message details
        const msgResp = await fetch(
          `https://gmail.googleapis.com/gmail/v1/users/me/messages/${msgMeta.id}?format=full`,
          { headers: { Authorization: `Bearer ${accessToken}` } }
        );
        if (!msgResp.ok) {
          console.error(`Failed to fetch message ${msgMeta.id}:`, await msgResp.text());
          continue;
        }
        const rawMsg = await msgResp.json();

        // 4. Normalize (same envelope shape as Slack/Notion)
        const headers = rawMsg.payload?.headers || [];
        const getHeader = (name: string) =>
          headers.find((h: any) => h.name?.toLowerCase() === name.toLowerCase())?.value || "";

        let body = "";
        const payload = rawMsg.payload || {};
        if (payload.body?.data) {
          body = atob(payload.body.data.replace(/-/g, "+").replace(/_/g, "/"));
        } else if (payload.parts) {
          const textPart = payload.parts.find(
            (p: any) => p.mimeType === "text/plain" && p.body?.data
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

        // 5. Enqueue
        await enqueueEvent(envelope);
        syncedCount++;
      }

      // 6. Update last_synced_at
      await supabase
        .from("source_connections")
        .update({ last_synced_at: new Date().toISOString() })
        .eq("id", source.id);

      results.push({ source_id: source.id, messages_synced: syncedCount });
    } catch (err) {
      console.error(`Error syncing source ${source.id}:`, err);
    }
  }

  return new Response(JSON.stringify({ message: "Sync completed", results }), {
    headers: { "Content-Type": "application/json" },
  });
});