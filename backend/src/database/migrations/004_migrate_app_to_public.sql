-- =====================================================================
-- M2: Copy data from app.* → public.*
-- Run AFTER 003_public_design_schema.sql
-- Does NOT copy app.captures (not the dedup ledger; will be dropped in M5)
-- Does NOT copy stub app.decisions unless you uncomment that block
-- =====================================================================

-- ---------------------------------------------------------------------
-- 2.1 workspaces → tenants
-- ---------------------------------------------------------------------
insert into public.tenants (id, name, slug, plan, created_at)
select
  w.tenant_id,
  w.name,
  lower(
    regexp_replace(coalesce(nullif(trim(w.name), ''), 'workspace'), '[^a-zA-Z0-9]+', '-', 'g')
  ) || '-' || substr(replace(w.tenant_id::text, '-', ''), 1, 8),
  'self_serve',
  w.created_at
from app.workspaces w
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- 2.2 memberships
-- ---------------------------------------------------------------------
insert into public.memberships (id, tenant_id, user_id, role, created_at, updated_at)
select m.id, m.tenant_id, m.user_id, m.role, m.created_at, m.updated_at
from app.memberships m
on conflict (tenant_id, user_id) do nothing;

-- ---------------------------------------------------------------------
-- 2.3 sources → source_connections
-- type → source; oauth_token_ref may be null
-- ---------------------------------------------------------------------
insert into public.source_connections (
  id,
  tenant_id,
  source,
  external_workspace_id,
  oauth_token_ref,
  ingestion_mode,
  status,
  cursor_state,
  last_synced_at,
  created_at
)
select
  s.id,
  s.tenant_id,
  s.type,
  s.external_workspace_id,
  s.oauth_token_ref,
  s.ingestion_mode,
  s.status,
  s.cursor_state,
  s.last_synced_at,
  s.created_at
from app.sources s
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- 2.4 Optional: stub app.decisions → public.decisions
-- Uncomment only if you have real rows worth keeping.
-- Design decisions requires decision_statement + confidence NOT NULL.
-- ---------------------------------------------------------------------
-- insert into public.decisions (
--   id, tenant_id, record_type, decision_statement, rationale,
--   status, confidence, created_at, updated_at
-- )
-- select
--   d.id,
--   d.tenant_id,
--   'decision',
--   coalesce(nullif(trim(d.title), ''), 'Migrated decision'),
--   d.body,
--   'proposed',
--   0.500,
--   d.created_at,
--   d.updated_at
-- from app.decisions d
-- on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- 2.5 Verify counts
-- ---------------------------------------------------------------------
select 'tenants' as t, count(*) as n from public.tenants
union all select 'memberships', count(*) from public.memberships
union all select 'source_connections', count(*) from public.source_connections
union all select 'raw_events', count(*) from public.raw_events
union all select 'actors', count(*) from public.actors
union all select 'decisions', count(*) from public.decisions;
