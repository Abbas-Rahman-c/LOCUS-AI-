// supabase/functions/_shared/supabase.ts
//
// Supabase JS clients for Edge Functions.
//
// getServiceClient() — service_role, bypasses row-level security.
//   Use only for trusted cross-tenant admin paths or RPCs that cannot yet
//   go through APP_DATABASE_URL (e.g. enqueue_ingestion_event).
//
// For tenant-scoped public.* table access, use _shared/db.ts:
//   withTenant(tenantId, ...) / withAdmin(...)

import { createClient } from "npm:@supabase/supabase-js@2";

export function getServiceClient() {
  const url = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

  if (!url || !serviceKey) {
    throw new Error(
      "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variable.",
    );
  }

  return createClient(url, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}
