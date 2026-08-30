// supabase/functions/_shared/githubAuth.ts
//
// GitHub App authentication - JWT signing (RS256, App-level private key) +
// installation access token minting. One shared App identity
// (GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY, both Supabase secrets, not
// per-tenant) does all API auth - each tenant only stores which
// installation_id they connected (github-oauth/index.ts), never a
// per-tenant token to refresh or expire. Same shape as Discord's global
// bot token, not Jira/Confluence's per-tenant refresh_token model.
//
// Installation access tokens expire after 1h (GitHub's own hard limit) -
// minted fresh per poll run rather than cached across runs, since the
// poll interval is already only 5 minutes and caching across cold
// Deno.serve invocations would need its own storage anyway.
//
// Real gotcha, verified against GitHub's own docs before writing this:
// GitHub's downloaded private key is PKCS#1 ("BEGIN RSA PRIVATE KEY"),
// but jose's importPKCS8 requires PKCS#8 ("BEGIN PRIVATE KEY"). Converted
// once via `openssl pkcs8 -topk8 -in key.pem -out key.pkcs8 -nocrypt`
// before being stored as the GITHUB_APP_PRIVATE_KEY secret, so this file
// assumes PKCS#8 - it does not re-convert at runtime.

import { importPKCS8, SignJWT } from "npm:jose@5";

const APP_ID = Deno.env.get("GITHUB_APP_ID") ?? "";
const PRIVATE_KEY_PEM = Deno.env.get("GITHUB_APP_PRIVATE_KEY") ?? "";
const GITHUB_API_VERSION = "2022-11-28";

let cachedKey: CryptoKey | null = null;
async function getPrivateKey(): Promise<CryptoKey> {
  if (cachedKey) return cachedKey;
  if (!PRIVATE_KEY_PEM) throw new Error("GITHUB_APP_PRIVATE_KEY is not set");
  cachedKey = await importPKCS8(PRIVATE_KEY_PEM, "RS256");
  return cachedKey;
}

// Signs a short-lived App JWT - proves "this request is from the App
// itself", not any one installation. Only ever used to mint installation
// access tokens (below); the App JWT itself is never valid for normal
// REST calls like listing issues/commits.
export async function mintAppJwt(): Promise<string> {
  if (!APP_ID) throw new Error("GITHUB_APP_ID is not set");
  const key = await getPrivateKey();
  const now = Math.floor(Date.now() / 1000);
  return await new SignJWT({})
    .setProtectedHeader({ alg: "RS256" })
    .setIssuedAt(now - 60) // clock-drift allowance, per GitHub's own docs
    .setExpirationTime(now + 9 * 60) // GitHub's hard cap is 10 min - 9 leaves margin
    .setIssuer(APP_ID)
    .sign(key);
}

// Exchanges the App JWT for a real installation access token, scoped to
// exactly the repos/permissions that one installation grants (Contents/
// Issues/Pull requests: read-only, per the App's own configured
// permissions - never broader than what was set up in Step 1).
export async function mintInstallationToken(installationId: string): Promise<string> {
  const appJwt = await mintAppJwt();
  const resp = await fetch(`https://api.github.com/app/installations/${installationId}/access_tokens`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${appJwt}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": GITHUB_API_VERSION,
    },
  });
  if (!resp.ok) {
    throw new Error(`Failed to mint GitHub installation token: ${resp.status} ${await resp.text()}`);
  }
  const data = await resp.json();
  if (typeof data.token !== "string") {
    throw new Error("GitHub installation token response missing 'token'");
  }
  return data.token as string;
}

export function githubApiHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": GITHUB_API_VERSION,
  };
}
