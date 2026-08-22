// supabase/functions/slack-membership-sync/index.ts
//
// The fast-follow the plan calls for immediately after Checkpoint C:
// isMemoryAccessible() (in _shared/memory/permissions.ts) fails closed on
// any scope it can't confirm real membership for via
// public.source_scope_members - this is what actually populates that
// table with real data, Slack-first, per the decided scope. Notion is
// deliberately NOT covered here - its sharing model is page/workspace
// based, not channel membership, and needs its own research pass before
// it gets rows in this table.
//
// Uses each tenant's EXISTING connected Slack OAuth token
// (source_connections.oauth_token_ref, the same token slack-oauth/index.ts
// already stores and backfillSlackHistory already calls conversations.list
// with) - no new auth surface, per the decided fast-follow scope.
//
// Meant to run on a recurring schedule (see the paired migration
// 20260822020000_slack_membership_sync_cron.sql), NOT as a one-time
// snapshot - a stale membership cache would reproduce the exact staleness
// problem this whole product exists to solve. Also callable directly with
// a single tenant_id for a one-off manual sync (used once for the
// Checkpoint C demo tenant, see the plan's pre-demo mitigation step).
//
// Gated the same way as memory-api's admin routes: service_role only. This
// writes real access-control data across every tenant, so it's at least as
// sensitive as /fixtures/load or /debug/delete-memories.

import { withAdmin, withTenant } from "../_shared/db.ts";
import { decryptToken } from "../_shared/tokenCrypto.ts";
import { requireServiceRole } from "../_shared/requireServiceRole.ts";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

interface SlackConnection {
  tenant_id: string;
  external_workspace_id: string | null;
  oauth_token_ref: string | null;
}

async function fetchActiveSlackConnections(tenantId?: string): Promise<SlackConnection[]> {
  return await withAdmin(async (sql) => {
    return tenantId
      ? await sql`
          select tenant_id, external_workspace_id, oauth_token_ref
          from public.source_connections
          where source = 'slack' and status = 'active' and tenant_id = ${tenantId}
        `
      : await sql`
          select tenant_id, external_workspace_id, oauth_token_ref
          from public.source_connections
          where source = 'slack' and status = 'active'
        `;
  });
}

interface SyncOutcome {
  tenant_id: string;
  channels_synced: number;
  members_upserted: number;
  error?: string;
}

async function syncOneConnection(conn: SlackConnection): Promise<SyncOutcome> {
  const outcome: SyncOutcome = { tenant_id: conn.tenant_id, channels_synced: 0, members_upserted: 0 };

  const accessToken = await decryptToken(conn.oauth_token_ref);
  if (!accessToken) {
    outcome.error = "No decryptable oauth token on this connection";
    return outcome;
  }

  try {
    const channelsResp = await fetch(
      "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200",
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
    const channelsData = await channelsResp.json();
    if (!channelsData.ok) {
      outcome.error = `conversations.list failed: ${channelsData.error}`;
      return outcome;
    }

    const channels = (channelsData.channels ?? []).filter((c: { is_member?: boolean }) => c.is_member);
    const now = new Date().toISOString();

    for (const channel of channels) {
      try {
        const membersResp = await fetch(
          `https://slack.com/api/conversations.members?channel=${channel.id}&limit=200`,
          { headers: { Authorization: `Bearer ${accessToken}` } },
        );
        const membersData = await membersResp.json();
        if (!membersData.ok) {
          console.error(`slack-membership-sync: conversations.members failed for channel ${channel.id} (tenant ${conn.tenant_id}):`, membersData.error);
          continue;
        }

        const memberIds: string[] = membersData.members ?? [];
        if (memberIds.length === 0) continue;

        await withTenant(conn.tenant_id, async (sql) => {
          for (const memberId of memberIds) {
            await sql`
              insert into public.source_scope_members (tenant_id, source, external_scope_id, member_identifier, last_synced_at)
              values (${conn.tenant_id}, 'slack', ${channel.id}, ${memberId}, ${now})
              on conflict (tenant_id, source, external_scope_id, member_identifier)
              do update set last_synced_at = excluded.last_synced_at
            `;
          }
          // Members who left the channel since the last sync shouldn't
          // keep indefinite access through a stale row - prune anything
          // for this scope not touched by this run.
          await sql`
            delete from public.source_scope_members
            where tenant_id = ${conn.tenant_id} and source = 'slack' and external_scope_id = ${channel.id}
              and last_synced_at < ${now}
          `;
        });

        outcome.channels_synced += 1;
        outcome.members_upserted += memberIds.length;
      } catch (err) {
        console.error(`slack-membership-sync: channel ${channel.id} (tenant ${conn.tenant_id}) failed:`, err);
      }
    }
  } catch (err) {
    outcome.error = err instanceof Error ? err.message : String(err);
  }

  return outcome;
}

Deno.serve(async (req: Request) => {
  const authError = requireServiceRole(req);
  if (authError) return authError;

  let tenantId: string | undefined;
  try {
    const body = await req.json();
    tenantId = body?.tenant_id;
  } catch {
    // No body / not JSON - fine, this means "sync every connected tenant",
    // the cron job's own call shape.
  }

  const connections = await fetchActiveSlackConnections(tenantId);
  if (connections.length === 0) {
    return json({ synced: 0, outcomes: [], note: tenantId ? "No active Slack connection for that tenant" : "No active Slack connections at all" });
  }

  const outcomes: SyncOutcome[] = [];
  for (const conn of connections) {
    outcomes.push(await syncOneConnection(conn));
  }

  console.log(JSON.stringify({ event: "slack_membership_synced", tenant_scope: tenantId ?? "all", outcomes }));
  return json({ synced: outcomes.length, outcomes });
});
