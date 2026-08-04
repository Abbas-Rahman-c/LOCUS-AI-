import { withAdmin, withTenant } from "../_shared/db.ts";
import { enqueueEvent, IngestionEnvelope } from "../_shared/queue.ts";

console.log("Gmail manual sync started!");

const GMAIL_CLIENT_ID = Deno.env.get("GMAIL_CLIENT_ID");
const GMAIL_CLIENT_SECRET = Deno.env.get("GMAIL_CLIENT_SECRET");

// Plain fetch() never times out on its own - with every active Gmail
// connection processed sequentially in one invocation, a single stalled
// call (token refresh, list, or per-message fetch) blocks every other
// tenant's sync behind it. Same bug, same fix as ai-worker/index.ts.
async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(`Request to ${url} timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Google access tokens expire in ~1 hour; oauth_token_ref goes stale fast.
 * Refreshes it up front using the refresh_token captured at connect time
 * (stored in cursor_state by gmail-oauth's callback), and persists the new
 * access token so later syncs don't need to refresh again until it expires.
 */
// deno-lint-ignore no-explicit-any
async function refreshAccessToken(source: any): Promise<string | null> {
  const refreshToken = (source.cursor_state as Record<string, unknown> | null)?.refresh_token as
    | string
    | undefined;
  if (!refreshToken) {
    console.error(`No refresh_token stored for source ${source.id}; cannot refresh.`);
    return null;
  }

  const resp = await fetchWithTimeout("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: GMAIL_CLIENT_ID ?? "",
      client_secret: GMAIL_CLIENT_SECRET ?? "",
      refresh_token: refreshToken,
      grant_type: "refresh_token",
    }),
  }, 15_000);

  if (!resp.ok) {
    console.error(`Gmail token refresh failed for source ${source.id}:`, await resp.text());
    return null;
  }

  const data = await resp.json();
  const newAccessToken = data.access_token as string | undefined;
  if (!newAccessToken) return null;

  await withTenant(String(source.tenant_id), async (sql) => {
    await sql`
      update public.source_connections
      set oauth_token_ref = ${newAccessToken}
      where id = ${source.id}
    `;
  });

  return newAccessToken;
}

// First-sync backfill window + safety caps, and the per-run cap for every
// sync after that. All overridable via Supabase secrets; defaults match
// what was requested (30-day lookback, bounded message counts so one
// connection with a huge mailbox can't make a single invocation run
// forever). Configurable rather than hardcoded so a demo/staging tenant
// can be tuned without a code change.
const BACKFILL_LOOKBACK_DAYS = Number(Deno.env.get("GMAIL_BACKFILL_LOOKBACK_DAYS") ?? "30");
const BACKFILL_MAX_MESSAGES = Number(Deno.env.get("GMAIL_BACKFILL_MAX_MESSAGES") ?? "200");
const INCREMENTAL_MAX_MESSAGES = Number(Deno.env.get("GMAIL_INCREMENTAL_MAX_MESSAGES") ?? "50");
const LIST_PAGE_SIZE = 100; // Gmail's messages.list allows up to 500; 100 keeps each page fetch quick under fetchWithTimeout.

// Gmail's `after:` search operator wants YYYY/MM/DD (day granularity, no
// time component) - https://support.google.com/mail/answer/7190. Day
// granularity means a run's window can overlap the previous run's by up
// to a day; that's intentional and safe (re-listing an already-ingested
// message just costs one duplicate list entry, which store_raw_event()'s
// ON CONFLICT (tenant_id, source, source_id) DO NOTHING in ai-worker
// already no-ops on) - the alternative, rounding forward, risks silently
// skipping a message instead.
function formatGmailAfterDate(date: Date): string {
  return `${date.getUTCFullYear()}/${date.getUTCMonth() + 1}/${date.getUTCDate()}`;
}

// Paginates messages.list up to maxMessages total, honoring the same
// per-call timeout every other Gmail request in this file uses. Stops
// early once maxMessages is reached or Gmail reports no nextPageToken -
// never fetches more than the caller asked for, regardless of how large
// the actual result set is.
async function listGmailMessageIds(
  accessToken: string,
  query: string,
  maxMessages: number,
): Promise<{ id: string }[]> {
  const ids: { id: string }[] = [];
  let pageToken: string | undefined;

  do {
    const url = new URL("https://gmail.googleapis.com/gmail/v1/users/me/messages");
    url.searchParams.set("maxResults", String(Math.min(LIST_PAGE_SIZE, maxMessages - ids.length)));
    if (query) url.searchParams.set("q", query);
    if (pageToken) url.searchParams.set("pageToken", pageToken);

    const resp = await fetchWithTimeout(
      url.toString(),
      { headers: { Authorization: `Bearer ${accessToken}` } },
      15_000,
    );
    if (!resp.ok) {
      console.error(`Gmail list page failed (query=${query}):`, await resp.text());
      break;
    }
    const data = await resp.json();
    ids.push(...(data.messages ?? []));
    pageToken = data.nextPageToken;
  } while (pageToken && ids.length < maxMessages);

  return ids.slice(0, maxMessages);
}

const SYNC_CONCURRENCY = 5;

// Runs syncOneSource(source) for every source with at most `concurrency` in
// flight at once - one tenant's stalled OAuth/Gmail call (now bounded to
// 15s by fetchWithTimeout, but 15s x up to 12 sequential calls still adds
// up) no longer serializes behind every other tenant's sync.
// deno-lint-ignore no-explicit-any
async function runBounded(sources: any[], concurrency: number, fn: (source: any) => Promise<unknown>) {
  const results: unknown[] = [];
  let i = 0;
  async function worker() {
    while (i < sources.length) {
      const source = sources[i++];
      results.push(await fn(source));
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, sources.length) }, worker));
  return results;
}

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

  // deno-lint-ignore no-explicit-any
  async function syncOneSource(source: any) {
    // Captured before any fetching starts, not after: last_synced_at is set
    // to this value at the end of a successful run, so a message that
    // arrives WHILE this run is in flight is still >= the next run's
    // `after:` bound (a little overlap, dedup-safe) instead of falling into
    // the gap between "when this run listed messages" and "when it finished".
    const syncStartedAt = new Date();
    try {
      console.log(`Syncing Gmail: ${source.external_workspace_id}`);

      const accessToken = await refreshAccessToken(source);
      if (!accessToken) {
        console.error(`Unable to obtain a valid access token for source ${source.id}`);
        return { source_id: source.id, messages_synced: 0, error: "no_access_token" };
      }

      // last_synced_at is set only after a source's FIRST successful sync
      // (see the update at the end of this function) - null here means
      // this connection has never completed a sync, so this run is a
      // first-connection backfill, not an incremental catch-up.
      const isFirstSync = !source.last_synced_at;
      const afterDate = isFirstSync
        ? new Date(syncStartedAt.getTime() - BACKFILL_LOOKBACK_DAYS * 24 * 60 * 60 * 1000)
        : new Date(source.last_synced_at);
      const maxMessages = isFirstSync ? BACKFILL_MAX_MESSAGES : INCREMENTAL_MAX_MESSAGES;
      const query = `after:${formatGmailAfterDate(afterDate)}`;

      console.log(
        `${isFirstSync ? "Backfilling" : "Incrementally syncing"} ${source.external_workspace_id} `
          + `(query="${query}", maxMessages=${maxMessages})`,
      );

      const messages = await listGmailMessageIds(accessToken, query, maxMessages);
      console.log(`Found ${messages.length} messages for ${source.id}`);

      let syncedCount = 0;

      for (const msgMeta of messages) {
        const msgResp = await fetchWithTimeout(
          `https://gmail.googleapis.com/gmail/v1/users/me/messages/${msgMeta.id}?format=full`,
          { headers: { Authorization: `Bearer ${accessToken}` } },
          15_000,
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
          permission_scope: source.external_workspace_id ? [String(source.external_workspace_id)] : [],
          raw_content: {
            subject: getHeader("Subject"),
            body,
            from: fromHeader,
            to: getHeader("To"),
            date: getHeader("Date"),
            snippet: rawMsg.snippet,
          },
          // #all/{id} works regardless of which label the message is
          // filed under (inbox, archived, etc.), unlike #inbox/{id}.
          source_permalink: `https://mail.google.com/mail/u/0/#all/${rawMsg.id}`,
          received_at: new Date().toISOString(),
        };

        await enqueueEvent(envelope);
        syncedCount++;
      }

      await withTenant(String(source.tenant_id), async (sql) => {
        await sql`
          update public.source_connections
          set last_synced_at = ${syncStartedAt.toISOString()}
          where id = ${source.id}
        `;
      });

      return { source_id: source.id, messages_synced: syncedCount, first_sync: isFirstSync };
    } catch (err) {
      console.error(`Error syncing source ${source.id}:`, err);
      return { source_id: source.id, messages_synced: 0, error: err instanceof Error ? err.message : String(err) };
    }
  }

  const results = await runBounded(sources, SYNC_CONCURRENCY, syncOneSource);

  return new Response(JSON.stringify({ message: "Sync completed", results }), {
    headers: { "Content-Type": "application/json" },
  });
});
