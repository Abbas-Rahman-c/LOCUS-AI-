// supabase/functions/_shared/memory/permissions.ts
//
// FAILS CLOSED on unmapped scope - a deliberate departure from the old
// isDecisionAccessible (api/index.ts), decided during Batch 3 planning,
// not inherited by default. The old model's "unmapped Slack channel/
// Notion page -> granted anyway" fallback made sense for a flat decision
// list; it does not carry over here, because the new memory layer links
// content across sources through shared entities - the aggregation is
// exactly what raises the blast radius of over-sharing. A memory whose
// only scopes are all unmapped is denied by default, for every surface,
// until source_scope_members has real data to prove access.

export async function isMemoryAccessible(
  // deno-lint-ignore no-explicit-any
  sql: any,
  tenantId: string,
  permissionScopes: string[],
  memoryVisibleTo: string[],
): Promise<boolean> {
  // Empty scope = workspace-wide, same as the old model - not the gap
  // being closed here (that's specifically about a REAL, non-empty scope
  // we can't verify).
  if (memoryVisibleTo.length === 0) return true;

  // Real overlap with the caller's own scopes always wins.
  if (memoryVisibleTo.some((s) => permissionScopes.includes(s))) return true;

  // The fail-closed check: does source_scope_members actually confirm the
  // caller belongs to any of this memory's scopes? No membership row at
  // all for a scope = denied, not granted - the opposite of the old
  // model's fallback.
  const rows = await sql`
    select 1 from public.source_scope_members
    where tenant_id = ${tenantId} and external_scope_id = any(${memoryVisibleTo})
      and member_identifier = any(${permissionScopes})
    limit 1
  `;
  return rows.length > 0;
}
