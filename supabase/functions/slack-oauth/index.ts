// supabase/functions/slack-oauth/index.ts
//
// CORRECTED: was writing to a guessed "sources" table with wrong column
// names. Real table (from Lam's migrations, matching the DS lead's schema)
// is "source_connections" — see backend/src/database/migrations/003.
//
// TODO (Rebira): oauth_token_ref is meant to be a *reference* to a Supabase
// Vault secret, not the raw token. This version stores the raw token
// directly for now, to unblock testing tonight — flagged clearly so it
// doesn't get forgotten before any real (non-test) credentials touch this.
// Proper fix: create a small Postgres function that wraps vault.create_secret,
// call it via RPC here, store the returned secret id instead.

import { getServiceClient } from "../_shared/supabase.ts";

const CLIENT_ID = Deno.env.get("SLACK_CLIENT_ID");
const CLIENT_SECRET = Deno.env.get("SLACK_CLIENT_SECRET");
const REDIRECT_URI = Deno.env.get("SLACK_REDIRECT_URI");

// TODO (Rebira): replace with real tenant resolution once Phase 4 Auth
// exists. For now, testing against Lam's real tenant row (auto-created
// by the auth trigger in migration 005) since it's the only one that
// currently exists in public.tenants.
const TEST_TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658";

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);

  if (url.pathname.endsWith("/authorize")) {
    const slackAuthUrl = new URL("https://slack.com/oauth/v2/authorize");
    slackAuthUrl.searchParams.set("client_id", CLIENT_ID ?? "");
    slackAuthUrl.searchParams.set(
      "scope",
      "channels:history,groups:history,im:history,mpim:history,chat:write"
    );
    slackAuthUrl.searchParams.set("redirect_uri", REDIRECT_URI ?? "");

    return Response.redirect(slackAuthUrl.toString(), 302);
  }

  if (url.pathname.endsWith("/callback")) {
    const code = url.searchParams.get("code");
    if (!code) {
      return new Response("Missing authorization code", { status: 400 });
    }

    const tokenResponse = await fetch("https://slack.com/api/oauth.v2.access", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: CLIENT_ID ?? "",
        client_secret: CLIENT_SECRET ?? "",
        code,
        redirect_uri: REDIRECT_URI ?? "",
      }),
    });

    const tokenData = await tokenResponse.json();

    if (!tokenData.ok) {
      return new Response(
        `Slack OAuth failed: ${tokenData.error ?? "unknown error"}`,
        { status: 400 }
      );
    }

    const supabase = getServiceClient();

    // NOTE: table is source_connections, not "sources".
    // oauth_token_ref holds the raw token for now — see TODO above.
    const { error } = await supabase.from("source_connections").upsert(
      {
        tenant_id: TEST_TENANT_ID,
        source: "slack",
        external_workspace_id: tokenData.team?.id,
        oauth_token_ref: tokenData.access_token, // TODO: move to Vault
        ingestion_mode: "realtime",
        status: "active",
        cursor_state: { bot_user_id: tokenData.bot_user_id },
      },
      { onConflict: "tenant_id,source,external_workspace_id" }
    );

    if (error) {
      return new Response(`Failed to store token: ${error.message}`, {
        status: 500,
      });
    }

    return new Response("Slack workspace connected successfully.", {
      status: 200,
    });
  }

  return new Response("Not found", { status: 404 });
});