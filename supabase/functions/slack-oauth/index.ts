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

import { withTenant } from "../_shared/db.ts";
import {
  authorizeErrorResponse,
  parseTenantState,
  popupCallbackResponse,
  resolveTenantFromAuthorize,
} from "../_shared/oauth_tenant.ts";

const CLIENT_ID = Deno.env.get("SLACK_CLIENT_ID");
const CLIENT_SECRET = Deno.env.get("SLACK_CLIENT_SECRET");
const REDIRECT_URI = Deno.env.get("SLACK_REDIRECT_URI");

const SOURCE = "slack" as const;

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);

  if (url.pathname.endsWith("/authorize")) {
    try {
      const tenantId = await resolveTenantFromAuthorize(url);

      const slackAuthUrl = new URL("https://slack.com/oauth/v2/authorize");
      slackAuthUrl.searchParams.set("client_id", CLIENT_ID ?? "");
      slackAuthUrl.searchParams.set(
        "scope",
        "channels:history,groups:history,im:history,mpim:history,chat:write",
      );
      slackAuthUrl.searchParams.set("redirect_uri", REDIRECT_URI ?? "");
      slackAuthUrl.searchParams.set("state", tenantId);

      return Response.redirect(slackAuthUrl.toString(), 302);
    } catch (err) {
      return authorizeErrorResponse(SOURCE, err);
    }
  }

  if (url.pathname.endsWith("/callback")) {
    let tenantId: string;
    try {
      tenantId = parseTenantState(url.searchParams.get("state"));
    } catch (err) {
      return authorizeErrorResponse(SOURCE, err);
    }

    const code = url.searchParams.get("code");
    if (!code) {
      return popupCallbackResponse(SOURCE, {
        success: false,
        error: "Missing authorization code",
        status: 400,
      });
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
      return popupCallbackResponse(SOURCE, {
        success: false,
        error: `Slack OAuth failed: ${tokenData.error ?? "unknown error"}`,
        status: 400,
      });
    }

    try {
      await withTenant(tenantId, async (sql) => {
        await sql`
          insert into public.source_connections (
            tenant_id, source, external_workspace_id, oauth_token_ref,
            ingestion_mode, status, cursor_state
          ) values (
            ${tenantId}::uuid,
            'slack',
            ${tokenData.team?.id ?? null},
            ${tokenData.access_token},
            'realtime',
            'active',
            ${sql.json({ bot_user_id: tokenData.bot_user_id ?? null })}::jsonb
          )
          on conflict (tenant_id, source, external_workspace_id)
          do update set
            oauth_token_ref = excluded.oauth_token_ref,
            status = 'active',
            cursor_state = excluded.cursor_state,
            ingestion_mode = excluded.ingestion_mode
        `;
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return popupCallbackResponse(SOURCE, {
        success: false,
        error: `Failed to store token: ${message}`,
        status: 500,
      });
    }

    return popupCallbackResponse(SOURCE, { success: true });
  }

  return new Response("Not found", { status: 404 });
});
