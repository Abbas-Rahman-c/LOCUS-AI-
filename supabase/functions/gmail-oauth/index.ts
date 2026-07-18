import { withTenant } from "../_shared/db.ts";

console.log("Gmail OAuth handler started!");

const CLIENT_ID = Deno.env.get("GMAIL_CLIENT_ID");
const CLIENT_SECRET = Deno.env.get("GMAIL_CLIENT_SECRET");
const REDIRECT_URI = Deno.env.get("GMAIL_REDIRECT_URI");

// TODO: replace with real tenant resolution once Phase 4 Auth exists.
// Same test tenant used for Slack/Notion tonight, for consistency.
const TEST_TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658";

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);

  // GET /authorize: redirect to Google's consent screen
  if (url.pathname.endsWith("/authorize")) {
    const scopes = [
      "https://www.googleapis.com/auth/gmail.readonly",
      "https://www.googleapis.com/auth/userinfo.email",
      "openid",
    ];
    const googleAuthUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth");
    googleAuthUrl.searchParams.set("client_id", CLIENT_ID ?? "");
    googleAuthUrl.searchParams.set("redirect_uri", REDIRECT_URI ?? "");
    googleAuthUrl.searchParams.set("response_type", "code");
    googleAuthUrl.searchParams.set("scope", scopes.join(" "));
    googleAuthUrl.searchParams.set("access_type", "offline");
    googleAuthUrl.searchParams.set("prompt", "consent");

    return Response.redirect(googleAuthUrl.toString(), 302);
  }

  // GET /callback: handle Google's redirect back
  if (url.pathname.endsWith("/callback")) {
    const code = url.searchParams.get("code");
    if (!code) {
      return new Response("Missing authorization code", { status: 400 });
    }

    try {
      // 1. Exchange code for tokens
      const tokenResponse = await fetch("https://oauth2.googleapis.com/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          client_id: CLIENT_ID ?? "",
          client_secret: CLIENT_SECRET ?? "",
          code,
          redirect_uri: REDIRECT_URI ?? "",
          grant_type: "authorization_code",
        }),
      });

      const tokenData = await tokenResponse.json();
      if (!tokenResponse.ok) {
        return new Response(
          `Gmail OAuth failed: ${tokenData.error ?? "unknown error"}`,
          { status: 400 }
        );
      }

      // 2. Get the user's email address
      const userInfoResponse = await fetch(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        { headers: { Authorization: `Bearer ${tokenData.access_token}` } }
      );
      const userInfo = await userInfoResponse.json();
      const email = userInfo.email;
      if (!email) {
        return new Response("Email address not returned by Google", { status: 400 });
      }

      // 3. Store the connection under tenant GUC (locus_app / APP_DATABASE_URL).
      // Token stored as plain text for now to unblock testing.
      try {
        await withTenant(TEST_TENANT_ID, async (sql) => {
          await sql`
            insert into public.source_connections (
              tenant_id, source, external_workspace_id, oauth_token_ref,
              ingestion_mode, status, cursor_state
            ) values (
              ${TEST_TENANT_ID}::uuid,
              'gmail',
              ${email},
              ${tokenData.access_token},
              'polling',
              'active',
              ${sql.json({
                history_id: null,
                refresh_token: tokenData.refresh_token ?? null,
              })}::jsonb
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
        return new Response(`Failed to store token: ${message}`, {
          status: 500,
        });
      }

      return new Response("Gmail inbox connected successfully.", { status: 200 });
    } catch (error) {
      console.error("OAuth error:", error);
      return new Response("Internal Server Error", { status: 500 });
    }
  }

  return new Response("Not found", { status: 404 });
});