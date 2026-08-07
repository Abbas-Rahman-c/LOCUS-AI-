// supabase/functions/capture-source-rules/index.ts
//
// Backs frontend/src/pages/SettingsPage.tsx's Capture Controls > "Channels &
// Source Rules" table with real data: real Slack channels / Notion pages /
// Gmail labels (fetched live from each provider using the tenant's already-
// stored oauth_token_ref, same tokens gmail-manual-sync/notion-poller/
// slack-webhook use), merged with real persisted include/exclude state from
// capture_source_rules (migration 015).
//
// Auth: same pattern as search-history/delete-account - a raw Supabase-
// issued access token, verified via supabase.auth.getUser(token).
//
// Actions (POST body: { action, ... }):
//   list   -> { items: [{ source, item_id, item_name, included }] }
//   toggle -> { source, item_id, item_name, included } -> { included }

import { getServiceClient } from "../_shared/supabase.ts";
import { decryptToken } from "../_shared/tokenCrypto.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function jsonResponse(body: Record<string, unknown>, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

type Source = "slack" | "gmail" | "notion";
type RealItem = { source: Source; item_id: string; item_name: string };

function getNotionPageTitle(page: Record<string, unknown>): string {
  const props = (page.properties as Record<string, unknown> | undefined) ?? {};
  for (const key of Object.keys(props)) {
    const prop = props[key] as { type?: string; title?: { plain_text?: string }[] };
    if (prop?.type === "title" && Array.isArray(prop.title)) {
      const text = prop.title.map((t) => t.plain_text ?? "").join("");
      if (text) return text;
    }
  }
  return "Untitled";
}

async function fetchRealItems(source: Source, accessToken: string): Promise<RealItem[]> {
  if (source === "notion") {
    const resp = await fetch("https://api.notion.com/v1/search", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ filter: { value: "page", property: "object" } }),
    });
    if (!resp.ok) return [];
    const data = await resp.json();
    const pages = (data.results ?? []) as Record<string, unknown>[];
    return pages.map((page) => ({
      source: "notion" as const,
      item_id: String(page.id),
      item_name: getNotionPageTitle(page),
    }));
  }

  if (source === "slack") {
    const resp = await fetch(
      "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200",
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
    if (!resp.ok) return [];
    const data = await resp.json();
    if (!data.ok) return [];
    const channels = (data.channels ?? []) as { id: string; name: string }[];
    return channels.map((c) => ({ source: "slack" as const, item_id: c.id, item_name: `#${c.name}` }));
  }

  // gmail: labels are the closest real analog to a "channel" - a source a
  // user can meaningfully include/exclude, unlike scanning all senders.
  const resp = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/labels", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!resp.ok) return [];
  const data = await resp.json();
  // User-created labels plus the handful of system labels meaningful as an
  // include/exclude source (INBOX/SENT/IMPORTANT/STARRED). Excludes noisy
  // system ones (SPAM, TRASH, DRAFT, CATEGORY_*, CHAT, UNREAD) that aren't
  // a real "channel" a user would toggle.
  const MEANINGFUL_SYSTEM_LABELS = new Set(["INBOX", "SENT", "IMPORTANT", "STARRED"]);
  const labels = (data.labels ?? []) as { id: string; name: string; type?: string }[];
  return labels
    .filter((l) => l.type === "user" || MEANINGFUL_SYSTEM_LABELS.has(l.id))
    .map((l) => ({ source: "gmail" as const, item_id: l.id, item_name: l.name }));
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  const authorization = req.headers.get("Authorization");
  const token = authorization?.replace(/^Bearer\s+/i, "");
  if (!token) {
    return jsonResponse({ error: "Authentication required" }, 401);
  }

  const supabase = getServiceClient();
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser(token);

  if (userError || !user) {
    return jsonResponse({ error: "Invalid or expired session" }, 401);
  }

  const { data: membership } = await supabase
    .from("memberships")
    .select("tenant_id")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle();

  if (!membership) {
    return jsonResponse({ error: "No tenant membership found" }, 403);
  }
  const tenantId = membership.tenant_id as string;

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    body = {};
  }
  const action = String(body.action ?? "");

  if (action === "list") {
    const { data: sources } = await supabase
      .from("source_connections")
      .select("source, oauth_token_ref")
      .eq("tenant_id", tenantId)
      .eq("status", "active");

    // A tenant can have more than one active connection for the same
    // source (e.g. two Gmail accounts) - dedupe by (source, item_id) so the
    // same channel/page/label fetched from multiple connections doesn't
    // show up multiple times.
    const itemsByKey = new Map<string, RealItem>();
    for (const row of sources ?? []) {
      const source = row.source as Source;
      const accessToken = await decryptToken(row.oauth_token_ref as string | null);
      if (!accessToken) continue;
      try {
        for (const item of await fetchRealItems(source, accessToken)) {
          itemsByKey.set(`${item.source}:${item.item_id}`, item);
        }
      } catch (err) {
        console.error(`Failed to fetch real items for ${source}:`, err);
      }
    }
    const realItems = Array.from(itemsByKey.values());

    const { data: rules, error: rulesError } = await supabase
      .from("capture_source_rules")
      .select("source, item_id, included")
      .eq("tenant_id", tenantId);

    if (rulesError) {
      console.error("Failed to load capture_source_rules:", rulesError);
      return jsonResponse({ error: "Unable to load capture source rules" }, 500);
    }

    const ruleMap = new Map<string, boolean>();
    for (const rule of rules ?? []) {
      ruleMap.set(`${rule.source}:${rule.item_id}`, rule.included as boolean);
    }

    const items = realItems.map((item) => ({
      ...item,
      included: ruleMap.get(`${item.source}:${item.item_id}`) ?? true,
    }));

    return jsonResponse({ items }, 200);
  }

  if (action === "toggle") {
    const source = String(body.source ?? "");
    const itemId = String(body.item_id ?? "");
    const itemName = String(body.item_name ?? "");
    const included = Boolean(body.included);

    if (!source || !itemId) {
      return jsonResponse({ error: "source and item_id are required" }, 400);
    }

    const { error } = await supabase.from("capture_source_rules").upsert(
      {
        tenant_id: tenantId,
        source,
        item_id: itemId,
        item_name: itemName,
        included,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "tenant_id,source,item_id" },
    );

    if (error) {
      console.error("Failed to update capture_source_rules:", error);
      return jsonResponse({ error: "Unable to update capture rule" }, 500);
    }
    return jsonResponse({ included }, 200);
  }

  return jsonResponse({ error: `Unknown action: ${action}` }, 400);
});
