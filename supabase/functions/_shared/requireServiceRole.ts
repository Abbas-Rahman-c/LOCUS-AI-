// supabase/functions/_shared/requireServiceRole.ts
//
// Extracted out of memory-api/index.ts so slack-membership-sync (and any
// future admin-only function) shares the exact same check rather than a
// third hand-copied version drifting from the original.
//
// Supabase now issues two different service-role key shapes depending on
// when a project's keys were created/rotated: the legacy three-segment JWT
// (role encoded in the payload, what this originally checked), and the
// newer opaque `sb_secret_...` key with no JWT structure at all. Found
// live after a key rotation: this function's own atob()/JSON.parse() on a
// new-format key always threw, so every admin-gated route (this one,
// memory-api's /debug and /fixtures/load routes) silently 401'd for
// anyone using the rotated key. Both shapes must actually authorize.

export function requireServiceRole(req: Request): Response | null {
  const header = req.headers.get("Authorization") ?? "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  if (!match) return json({ detail: "Missing Authorization: Bearer token" }, 401);
  const token = match[1];

  // New-format opaque secret key - no JWT payload to inspect. Possessing
  // this key at all is equivalent to the old JWT's role=service_role claim,
  // since Supabase never issues it to a browser/anon context.
  if (token.startsWith("sb_secret_")) return null;

  try {
    const payloadB64 = token.split(".")[1];
    const payload = JSON.parse(atob(payloadB64.replace(/-/g, "+").replace(/_/g, "/")));
    if (payload.role !== "service_role") {
      return json({ detail: "This function requires the service role key, not a user or anon token." }, 403);
    }
  } catch {
    return json({ detail: "Malformed Authorization token" }, 401);
  }
  return null; // authorized
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
