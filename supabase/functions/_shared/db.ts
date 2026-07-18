// supabase/functions/_shared/db.ts
//
// Postgres access for Edge Functions that must obey row-level security.
// Mirrors backend database/tenant_context.py:
//   APP_DATABASE_URL  → locus_app (non-bypass) + set app.current_tenant_id
//   DATABASE_URL      → postgres (admin / cross-tenant lookup)
//
// Prefer this over getServiceClient() for public.* tenant table reads/writes.
// Keep getServiceClient() only where PostgREST service_role is still required
// (e.g. enqueue RPC until callers move fully to SQL).

import postgres from "npm:postgres@3.4.5";

type Sql = ReturnType<typeof postgres>;

function requireEnv(name: string): string {
  const value = Deno.env.get(name);
  if (!value) {
    throw new Error(`${name} is not set — add it to Edge Function secrets`);
  }
  return value;
}

function createSql(url: string): Sql {
  // prepare: false required for Supabase transaction-mode pooler
  return postgres(url, { prepare: false, max: 1 });
}

/**
 * Run work as locus_app with app.current_tenant_id bound for this transaction.
 */
export async function withTenant<T>(
  tenantId: string,
  fn: (sql: Sql) => Promise<T>,
): Promise<T> {
  const sql = createSql(requireEnv("APP_DATABASE_URL"));
  try {
    return await sql.begin(async (tx) => {
      await tx`select set_config('app.current_tenant_id', ${tenantId}, true)`;
      return await fn(tx as unknown as Sql);
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
}

/**
 * Run work as DATABASE_URL (postgres / bypass).
 * Use only for cross-tenant scans or lookups before tenant_id is known.
 */
export async function withAdmin<T>(fn: (sql: Sql) => Promise<T>): Promise<T> {
  const url = Deno.env.get("DATABASE_URL") ?? Deno.env.get("SUPABASE_DB_URL");
  if (!url) {
    throw new Error(
      "DATABASE_URL or SUPABASE_DB_URL is not set — add it to Edge Function secrets",
    );
  }
  const sql = createSql(url);
  try {
    return await fn(sql);
  } finally {
    await sql.end({ timeout: 5 });
  }
}
