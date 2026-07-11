import { getServiceClient } from "../_shared/supabase.ts";

console.log('Notion OAuth handler started!');

const CLIENT_ID = Deno.env.get("NOTION_CLIENT_ID");
const CLIENT_SECRET = Deno.env.get("NOTION_CLIENT_SECRET");
const REDIRECT_URI = Deno.env.get("NOTION_REDIRECT_URI");

// TODO: replace with real tenant resolution once Phase 4 Auth exists.
const TEST_TENANT_ID = "13bcd0fa-1ed9-4634-93c7-278ba97ec658";

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);

  // GET /authorize: Redirect to Notion consent screen
  if (url.pathname.endsWith("/authorize")) {
    const notionAuthUrl = new URL("https://api.notion.com/v1/oauth/authorize");
    notionAuthUrl.searchParams.set("client_id", CLIENT_ID ?? "");
    notionAuthUrl.searchParams.set("response_type", "code");
    notionAuthUrl.searchParams.set("owner", "user");
    notionAuthUrl.searchParams.set("redirect_uri", REDIRECT_URI ?? "");

    return Response.redirect(notionAuthUrl.toString(), 302);
  }

  // GET /callback: Handle OAuth callback
  if (url.pathname.endsWith("/callback")) {
    const code = url.searchParams.get("code");
    if (!code) {
      return new Response("Missing authorization code", { status: 400 });
    }

    try {
      const tokenResponse = await fetch("https://api.notion.com/v1/oauth/token", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Basic ${btoa(`${CLIENT_ID}:${CLIENT_SECRET}`)}`,
        },
        body: JSON.stringify({
          grant_type: "authorization_code",
          code,
          redirect_uri: REDIRECT_URI ?? "",
        }),
      });

      const tokenData = await tokenResponse.json();

      if (!tokenResponse.ok || tokenData.error) {
        return new Response(
          `Notion OAuth failed: ${tokenData.error ?? "unknown error"}`,
          { status: 400 }
        );
      }

      const supabase = getServiceClient();

      // Store plain token in oauth_token_ref for now to unblock testing
      const { error } = await supabase.from("source_connections").upsert(
        {
          tenant_id: TEST_TENANT_ID,
          source: "notion",
          external_workspace_id: tokenData.workspace_id,
          oauth_token_ref: tokenData.access_token,
          ingestion_mode: "polling",
          status: "active",
        },
        { onConflict: "tenant_id,source,external_workspace_id" }
      );

      if (error) {
        return new Response(`Failed to store token: ${error.message}`, {
          status: 500,
        });
      }

      return new Response("Notion workspace connected successfully.", {
        status: 200,
      });
    } catch (error) {
      console.error("OAuth error:", error);
      return new Response("Internal Server Error", { status: 500 });
    }
  }

  return new Response("Not found", { status: 404 });
});
