import { withTenant } from "../_shared/db.ts";
import {
  authorizeErrorResponse,
  parseTenantState,
  popupCallbackResponse,
  resolveTenantFromAuthorize,
} from "../_shared/oauth_tenant.ts";

console.log("Notion OAuth handler started!");

const CLIENT_ID = Deno.env.get("NOTION_CLIENT_ID");
const CLIENT_SECRET = Deno.env.get("NOTION_CLIENT_SECRET");
const REDIRECT_URI = Deno.env.get("NOTION_REDIRECT_URI");

const SOURCE = "notion" as const;

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);

  // GET /authorize: Redirect to Notion consent screen
  if (url.pathname.endsWith("/authorize")) {
    try {
      const tenantId = await resolveTenantFromAuthorize(url);

      const notionAuthUrl = new URL("https://api.notion.com/v1/oauth/authorize");
      notionAuthUrl.searchParams.set("client_id", CLIENT_ID ?? "");
      notionAuthUrl.searchParams.set("response_type", "code");
      notionAuthUrl.searchParams.set("owner", "user");
      notionAuthUrl.searchParams.set("redirect_uri", REDIRECT_URI ?? "");
      notionAuthUrl.searchParams.set("state", tenantId);

      return Response.redirect(notionAuthUrl.toString(), 302);
    } catch (err) {
      return authorizeErrorResponse(SOURCE, err);
    }
  }

  // GET /callback: Handle OAuth callback
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
        return popupCallbackResponse(SOURCE, {
          success: false,
          error: `Notion OAuth failed: ${tokenData.error ?? "unknown error"}`,
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
              'notion',
              ${tokenData.workspace_id},
              ${tokenData.access_token},
              'polling',
              'active',
              '{}'::jsonb
            )
            on conflict (tenant_id, source, external_workspace_id)
            do update set
              oauth_token_ref = excluded.oauth_token_ref,
              status = 'active',
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
    } catch (error) {
      console.error("OAuth error:", error);
      return popupCallbackResponse(SOURCE, {
        success: false,
        error: "Internal Server Error",
        status: 500,
      });
    }
  }

  return new Response("Not found", { status: 404 });
});
