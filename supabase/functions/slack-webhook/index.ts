// supabase/functions/slack-webhook/index.ts
//
// Ported from the working Python implementation (backend/src/modules/
// integrations/slack/webhook/{handler,verifier}.py, merged in PR #3).
// This is a starting draft — please review the HMAC logic especially
// closely before this goes anywhere near production traffic.
//
// TODO (Rebira): confirm SLACK_SIGNING_SECRET is set in Supabase project
// secrets (`supabase secrets set SLACK_SIGNING_SECRET=...`), not just a
// local .env — Edge Functions read from project secrets in production.

import { enqueueEvent } from "../_shared/queue.ts";
import { withAdmin } from "../_shared/db.ts";

const SIGNING_SECRET = Deno.env.get("SLACK_SIGNING_SECRET");
const MAX_TIMESTAMP_SKEW_SECONDS = 60 * 5; // 5 minutes, matches Slack's own recommendation

async function verifySlackSignature(
  req: Request,
  rawBody: string
): Promise<boolean> {
  if (!SIGNING_SECRET) {
    throw new Error("SLACK_SIGNING_SECRET is not configured.");
  }

  const timestamp = req.headers.get("x-slack-request-timestamp");
  const signature = req.headers.get("x-slack-signature");

  if (!timestamp || !signature) return false;

  // Reject old requests outright — stops replay attacks even if a
  // signature were somehow captured and resent later.
  const nowSeconds = Math.floor(Date.now() / 1000);
  if (Math.abs(nowSeconds - Number(timestamp)) > MAX_TIMESTAMP_SKEW_SECONDS) {
    return false;
  }

  const baseString = `v0:${timestamp}:${rawBody}`;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(SIGNING_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const macBuffer = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(baseString)
  );

  const computedSignature =
    "v0=" +
    Array.from(new Uint8Array(macBuffer))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

  // Timing-safe comparison — do NOT replace with computedSignature === signature.
  return timingSafeEqual(computedSignature, signature);
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

Deno.serve(async (req: Request) => {
  const rawBody = await req.text();

  // Slack sends a one-time verification challenge when the webhook URL
  // is first configured — must echo it back before Slack accepts the URL.
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }

  if (payload.type === "url_verification") {
    return new Response(JSON.stringify({ challenge: payload.challenge }), {
      headers: { "Content-Type": "application/json" },
    });
  }

  const isValid = await verifySlackSignature(req, rawBody);
  if (!isValid) {
    return new Response("Invalid signature", { status: 401 });
  }

  const event = payload.event as Record<string, unknown> | undefined;
  if (!event || event.type !== "message") {
    // Not a message event (could be a different event type, a bot message
    // echo, etc.) — acknowledge and do nothing, don't error.
    return new Response("OK", { status: 200 });
  }

  // Look up the real tenant via the source_connections row OAuth created,
  // matching on the Slack team ID that comes with every event payload.
  const teamId = String(payload.team_id ?? "");
  const connection = await withAdmin(async (sql) => {
    const rows = await sql`
      select tenant_id
      from public.source_connections
      where source = 'slack'
        and external_workspace_id = ${teamId}
      limit 1
    `;
    return rows[0] ?? null;
  });

  if (!connection) {
    // No matching connection — can't attribute this event to a tenant.
    // Acknowledge so Slack doesn't retry, but don't enqueue.
    return new Response("OK (no matching connection)", { status: 200 });
  }

  const tenantId = connection.tenant_id;

  await enqueueEvent({
    tenant_id: tenantId,
    source: "slack",
    source_id: String(event.ts ?? payload.event_id ?? crypto.randomUUID()),
    actor: String(event.user ?? "unknown"),
    thread_ref: String(event.thread_ts ?? event.channel ?? ""),
    permission_scope: String(event.channel ?? ""),
    raw_content: String(event.text ?? ""),
    received_at: new Date().toISOString(),
  });

  return new Response("OK", { status: 200 });
});