// supabase/functions/_shared/microsoftAuth.ts
//
// Shared by outlook-oauth's connectors (Calendar first, Teams later if
// built) - both go through the same Azure app registration. Microsoft
// Graph access tokens expire in ~1h (expires_in in the token response,
// typically ~3600s), same shape as Atlassian's - a poller running on any
// real interval needs to refresh before every call, not just react to a
// 401 after the fact.
//
// Unlike Atlassian (which ALWAYS rotates the refresh_token on every use),
// Microsoft's refresh response only SOMETIMES includes a new
// refresh_token - falls back to keeping the existing one when it
// doesn't, same defensive shape refreshAtlassianAccess already uses.
//
// `tenant` is always "common" here (not a specific Azure tenant id) -
// matches the app registration's "any organizational directory and
// personal Microsoft accounts" support, letting both work/school and
// personal Microsoft accounts connect.

import { withTenant } from "./db.ts";
import { encryptToken } from "./tokenCrypto.ts";

const CLIENT_ID = Deno.env.get("MICROSOFT_CLIENT_ID");
const CLIENT_SECRET = Deno.env.get("MICROSOFT_CLIENT_SECRET");
const SCOPE = "offline_access Calendars.Read";

export interface MicrosoftConnection {
  id: string;
  tenant_id: string;
  oauth_token_ref: string | null;
  cursor_state: { refresh_token?: string | null } | null;
}

/**
 * Refreshes a Microsoft Graph connection's access token unconditionally
 * (same "once per connection per run, cheap" reasoning as
 * refreshAtlassianAccess - not gated on tracking exact expiry). Returns
 * null and marks the connection 'error' if the refresh itself fails
 * (refresh_token revoked/expired - the user needs to reconnect).
 */
export async function refreshMicrosoftAccess(
  connection: MicrosoftConnection,
): Promise<{ accessToken: string } | null> {
  const refreshToken = connection.cursor_state?.refresh_token;
  if (!refreshToken) {
    console.error(`Connection ${connection.id} missing refresh_token in cursor_state`);
    return null;
  }

  try {
    const resp = await fetch("https://login.microsoftonline.com/common/oauth2/v2.0/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: CLIENT_ID ?? "",
        client_secret: CLIENT_SECRET ?? "",
        refresh_token: refreshToken,
        grant_type: "refresh_token",
        scope: SCOPE,
      }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.access_token) {
      console.error(`Microsoft token refresh failed for connection ${connection.id}:`, JSON.stringify(data));
      await withTenant(connection.tenant_id, async (sql) => {
        await sql`UPDATE public.source_connections SET status = 'error' WHERE id = ${connection.id}`;
      });
      return null;
    }

    const encryptedToken = await encryptToken(data.access_token);
    await withTenant(connection.tenant_id, async (sql) => {
      await sql`
        UPDATE public.source_connections
        SET oauth_token_ref = ${encryptedToken},
            cursor_state = ${sql.json({
              ...connection.cursor_state,
              // Only sometimes a new one - Microsoft doesn't always
              // rotate, unlike Atlassian which always does.
              refresh_token: data.refresh_token ?? refreshToken,
            })}
        WHERE id = ${connection.id}
      `;
    });

    return { accessToken: data.access_token };
  } catch (err) {
    console.error(`Microsoft token refresh threw for connection ${connection.id}:`, err);
    return null;
  }
}
