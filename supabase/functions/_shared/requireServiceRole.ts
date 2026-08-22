// supabase/functions/_shared/requireServiceRole.ts
//
// Extracted out of memory-api/index.ts so slack-membership-sync (and any
// future admin-only function) shares the exact same check rather than a
// third hand-copied version drifting from the original.

export function requireServiceRole(req: Request): Response | null {
  const header = req.headers.get("Authorization") ?? "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  if (!match) return json({ detail: "Missing Authorization: Bearer token" }, 401);
  try {
    const payloadB64 = match[1].split(".")[1];
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
