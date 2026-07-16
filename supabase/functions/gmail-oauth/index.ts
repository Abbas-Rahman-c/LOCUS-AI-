import { getServiceClient } from "../_shared/supabase.ts";

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

      // 3. Store the connection. Token stored as plain text for now to
      // unblock testing, same shortcut Slack/Notion currently use.
      const supabase = getServiceClient();
      const { error } = await supabase.from("source_connections").upsert(
        {
          tenant_id: TEST_TENANT_ID,
          source: "gmail",
          external_workspace_id: email,
          oauth_token_ref: tokenData.access_token, // TODO: move to Vault
          ingestion_mode: "polling",
          status: "active",
          cursor_state: { history_id: null, refresh_token: tokenData.refresh_token },
        },
        { onConflict: "tenant_id,source,external_workspace_id" }
      );

      if (error) {
        return new Response(`Failed to store token: ${error.message}`, {
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