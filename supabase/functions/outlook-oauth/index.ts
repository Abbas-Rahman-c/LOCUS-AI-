// supabase/functions/outlook-oauth/index.ts
//
// Standard per-tenant OAuth against Microsoft's identity platform
// (login.microsoftonline.com), same refresh-token shape as Jira/
// Confluence - Microsoft Graph access tokens expire in ~1h, offline_access
// scope requested so a refresh_token comes back too, stored in
// cursor_state (unencrypted, matching gmail-oauth's own refresh_token
// precedent) alongside nothing else - Microsoft has no cloud_id-style
// extra identifier the way Atlassian does, the access token works
// directly against graph.microsoft.com once you have it.
//
// tenant is "common" (not a specific Azure tenant id) throughout - the
// app registration is configured for "any organizational directory and
// personal Microsoft accounts", so this lets both work/school and
// personal Microsoft accounts connect, matching Step 1's guidance.
//
// external_workspace_id is the connecting user's own mail/userPrincipalName
// - Microsoft Graph delegated access is inherently per-user (there's no
// tenant-wide "workspace" concept the way Slack/Notion have), same real
// shape as Monday's own connection identity.

import { withTenant } from "../_shared/db.ts";
import { ensureSourceConnectionDisplayNameColumn } from "../_shared/sourceConnectionSchema.ts";
import {
  authorizeErrorResponse,
  encodeState,
  parseTenantState,
  popupCallbackResponse,
  resolveRedirectOrigin,
  resolveTenantFromAuthorize,
} from "../_shared/oauth_tenant.ts";
import { encryptToken } from "../_shared/tokenCrypto.ts";
import { enforceRouteRateLimit } from "../_shared/routeRateLimit.ts";

console.log("Outlook OAuth handler started!");

const CLIENT_ID = Deno.env.get("MICROSOFT_CLIENT_ID");
const CLIENT_SECRET = Deno.env.get("MICROSOFT_CLIENT_SECRET");
const REDIRECT_URI = Deno.env.get("MICROSOFT_REDIRECT_URI");
const SCOPE = "offline_access Calendars.Read";

const SOURCE = "outlook_calendar" as const;

// Deploy note: this function must ALWAYS be deployed with --no-verify-jwt.
// See slack-oauth/index.ts's identical comment for why.
Deno.serve(async (req: Request) => {
  const url = new URL(req.url);

  if (url.pathname.endsWith("/authorize")) {
    const redirectOrigin = resolveRedirectOrigin(url);
    try {
      const tenantId = await resolveTenantFromAuthorize(url);
      await enforceRouteRateLimit(tenantId, "outlook-oauth");

      const authorizeUrl = new URL("https://login.microsoftonline.com/common/oauth2/v2.0/authorize");
      authorizeUrl.searchParams.set("client_id", CLIENT_ID ?? "");
      authorizeUrl.searchParams.set("response_type", "code");
      authorizeUrl.searchParams.set("redirect_uri", REDIRECT_URI ?? "");
      authorizeUrl.searchParams.set("response_mode", "query");
      authorizeUrl.searchParams.set("scope", SCOPE);
      authorizeUrl.searchParams.set("state", encodeState(tenantId, redirectOrigin));

      return Response.redirect(authorizeUrl.toString(), 302);
    } catch (err) {
      return authorizeErrorResponse(SOURCE, err, redirectOrigin);
    }
  }

  if (url.pathname.endsWith("/callback")) {
    let tenantId: string;
    let redirectOrigin: string;
    try {
      ({ tenantId, redirectOrigin } = parseTenantState(url.searchParams.get("state")));
    } catch (err) {
      return authorizeErrorResponse(SOURCE, err, resolveRedirectOrigin(url));
    }

    const code = url.searchParams.get("code");
    if (!code) {
      return popupCallbackResponse(SOURCE, {
        success: false,
        error: "Missing authorization code",
        status: 400,
      }, redirectOrigin);
    }

    try {
      const tokenResponse = await fetch("https://login.microsoftonline.com/common/oauth2/v2.0/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          client_id: CLIENT_ID ?? "",
          client_secret: CLIENT_SECRET ?? "",
          code,
          redirect_uri: REDIRECT_URI ?? "",
          grant_type: "authorization_code",
          scope: SCOPE,
        }),
      });
      const tokenData = await tokenResponse.json();

      if (!tokenResponse.ok || tokenData.error) {
        return popupCallbackResponse(SOURCE, {
          success: false,
          error: `Outlook OAuth failed: ${tokenData.error ?? tokenData.error_description ?? "unknown error"}`,
          status: 400,
        }, redirectOrigin);
      }

      const meResp = await fetch("https://graph.microsoft.com/v1.0/me", {
        headers: { Authorization: `Bearer ${tokenData.access_token}` },
      });
      const meData = await meResp.json();
      const accountId = meData.mail ?? meData.userPrincipalName ?? "unknown";
      const displayName = meData.displayName ?? accountId;

      const encryptedToken = await encryptToken(tokenData.access_token);
      await ensureSourceConnectionDisplayNameColumn();
      await withTenant(tenantId, async (sql) => {
        await sql`
          insert into public.source_connections (
            tenant_id, source, external_workspace_id, display_name, oauth_token_ref,
            ingestion_mode, status, cursor_state, last_synced_at
          ) values (
            ${tenantId}::uuid,
            'outlook_calendar',
            ${accountId},
            ${displayName},
            ${encryptedToken},
            'polling',
            'active',
            ${sql.json({ refresh_token: tokenData.refresh_token ?? null })},
            null
          )
          on conflict (tenant_id, source, external_workspace_id)
          do update set
            oauth_token_ref = excluded.oauth_token_ref,
            display_name = excluded.display_name,
            status = 'active',
            cursor_state = excluded.cursor_state
        `;
      });

      return popupCallbackResponse(SOURCE, { success: true }, redirectOrigin);
    } catch (error) {
      console.error("Outlook OAuth error:", error);
      return popupCallbackResponse(SOURCE, {
        success: false,
        error: "Internal Server Error",
        status: 500,
      }, redirectOrigin);
    }
  }

  return new Response("Not found", { status: 404 });
});
