// supabase/functions/_shared/supabase.ts
//
// NOTE FOR REBIRA: This mirrors the shared client Sudhira already built in
// PR #4 (supabase/functions/_shared/supabase.ts). Once that PR merges,
// DELETE this file and import the real one instead — don't keep two
// versions of the same shared client around (same mistake we already hit
// once with slack.config.py / slack_config.py in the Python backend).
// This copy exists only so you can build and test independently right now.

import { createClient } from "npm:@supabase/supabase-js@2";

export function getServiceClient() {
  const url = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

  if (!url || !serviceKey) {
    throw new Error(
      "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variable."
    );
  }

  // Service-role client: bypasses RLS. Only use this inside Edge Functions
  // that run as trusted backend code (webhook handlers, cron jobs) — never
  // expose the service key to a client-facing endpoint.
  return createClient(url, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}
