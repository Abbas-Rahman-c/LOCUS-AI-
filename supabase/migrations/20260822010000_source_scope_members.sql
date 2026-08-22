-- source_scope_members: real per-channel/page membership data, the thing
-- that makes the new memory layer's fail-closed permission check
-- (_shared/memory/permissions.ts) actually resolve access instead of
-- denying everything with a real scope forever. Slack-first per the
-- decided fast-follow scope - Notion's page-sharing model is structurally
-- different (page/workspace sharing, not channel membership) and needs
-- its own research pass before this table gets Notion rows, so nothing
-- assumes Notion works the same way.
--
-- Meant to be kept fresh by a recurring sync (not a one-time snapshot) -
-- last_synced_at exists specifically so staleness is visible, not hidden.

create table if not exists public.source_scope_members (
  tenant_id         uuid not null references public.tenants(id) on delete cascade,
  source            text not null check (source in ('slack', 'notion')),
  external_scope_id text not null,
  member_identifier text not null,
  last_synced_at    timestamptz not null default now(),
  primary key (tenant_id, source, external_scope_id, member_identifier)
);

create index if not exists idx_source_scope_members_lookup
  on public.source_scope_members (tenant_id, external_scope_id, member_identifier);

alter table public.source_scope_members enable row level security;

drop policy if exists tenant_isolation_source_scope_members on public.source_scope_members;
create policy tenant_isolation_source_scope_members on public.source_scope_members
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);
