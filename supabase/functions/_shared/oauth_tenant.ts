// Shared helpers for Slack / Notion / Gmail OAuth Edge Functions:
// - resolve tenant from /authorize?tenant_id=&access_token=
// - read tenant_id from OAuth state on /callback
// - return popup HTML that postMessages the opener and closes

import { withAdmin } from "./db.ts";
import { getServiceClient } from "./supabase.ts";

export type SourceKind = "slack" | "notion" | "gmail";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export class OAuthTenantError extends Error {
  status: number;

  constructor(message: string, status = 400) {
    super(message);
    this.name = "OAuthTenantError";
    this.status = status;
  }
}

function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}

/**
 * Validate tenant_id + access_token on /authorize.
 * Verifies the Supabase Auth JWT and that the user is a member of the tenant.
 */
export async function resolveTenantFromAuthorize(url: URL): Promise<string> {
  const tenantId = url.searchParams.get("tenant_id")?.trim() ?? "";
  const accessToken = url.searchParams.get("access_token")?.trim() ?? "";

  if (!tenantId || !accessToken) {
    throw new OAuthTenantError("Missing tenant_id or access_token");
  }
  if (!isUuid(tenantId)) {
    throw new OAuthTenantError("Invalid tenant_id");
  }

  const userId = await verifyAccessToken(accessToken);
  await assertMembership(userId, tenantId);
  return tenantId;
}

async function verifyAccessToken(accessToken: string): Promise<string> {
  const supabase = getServiceClient();
  const { data, error } = await supabase.auth.getUser(accessToken);

  if (error || !data.user?.id) {
    throw new OAuthTenantError("Invalid or expired access_token", 401);
  }

  return data.user.id;
}

async function assertMembership(
  userId: string,
  tenantId: string,
): Promise<void> {
  const rows = await withAdmin(async (sql) => {
    return await sql`
      select 1
      from public.memberships
      where user_id = ${userId}::uuid
        and tenant_id = ${tenantId}::uuid
      limit 1
    `;
  });

  if (rows.length === 0) {
    throw new OAuthTenantError("User is not a member of this tenant", 403);
  }
}

/** Read and validate tenant_id carried in the provider OAuth `state` param. */
export function parseTenantState(state: string | null): string {
  const tenantId = state?.trim() ?? "";
  if (!tenantId || !isUuid(tenantId)) {
    throw new OAuthTenantError("Missing or invalid OAuth state (tenant_id)");
  }
  return tenantId;
}

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/**
 * HTML response for OAuth popup completion.
 * Posts { type: 'locus:source-oauth', source, success, error? } to opener, then closes.
 *
 * Optional secret OAUTH_POPUP_TARGET_ORIGIN restricts postMessage target
 * (defaults to "*" so any opener can receive the event).
 */
export function popupCallbackResponse(
  source: SourceKind,
  options: { success: boolean; error?: string; status?: number },
): Response {
  const payload = {
    type: "locus:source-oauth",
    source,
    success: options.success,
    ...(options.error ? { error: options.error } : {}),
  };

  // Prevent </script> breakout if an error string ever contains HTML-ish text.
  const payloadJson = JSON.stringify(payload).replaceAll("<", "\\u003c");
  const targetOrigin = Deno.env.get("OAUTH_POPUP_TARGET_ORIGIN") ?? "*";
  const targetOriginJson = JSON.stringify(targetOrigin);

  const visibleMessage = options.success
    ? `${source[0]!.toUpperCase()}${source.slice(1)} connected successfully. You can close this window.`
    : (options.error ?? "Connection failed. You can close this window.");

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Locus OAuth</title>
</head>
<body>
  <p>${escapeHtml(visibleMessage)}</p>
  <script>
    (function () {
      var payload = ${payloadJson};
      var targetOrigin = ${targetOriginJson};
      try {
        if (window.opener) {
          window.opener.postMessage(payload, targetOrigin);
        }
      } catch (e) {}
      window.close();
    })();
  </script>
</body>
</html>`;

  return new Response(html, {
    status: options.status ?? (options.success ? 200 : 400),
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

export function authorizeErrorResponse(
  source: SourceKind,
  err: unknown,
): Response {
  if (err instanceof OAuthTenantError) {
    return popupCallbackResponse(source, {
      success: false,
      error: err.message,
      status: err.status,
    });
  }

  const message = err instanceof Error ? err.message : String(err);
  return popupCallbackResponse(source, {
    success: false,
    error: message,
    status: 500,
  });
}
