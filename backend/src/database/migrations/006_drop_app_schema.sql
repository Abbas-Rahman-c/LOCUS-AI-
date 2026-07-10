-- =====================================================================
-- M5: Drop legacy app.* bootstrap tables
-- Run ONLY after M1–M4 verified (data in public.*, Auth trigger on public)
-- If storage policies still reference app.* helpers, run 006b instead/after.
-- Keeps: public design tables, public.sources view, pgmq queues
-- Removes: app.captures (false ledger) and other app.* tables
-- =====================================================================

-- Safety: refuse if public.tenants is empty but app.workspaces still has rows
do $$
declare
  app_ws bigint := 0;
  pub_tenants bigint := 0;
begin
  if to_regclass('app.workspaces') is not null then
    execute 'select count(*) from app.workspaces' into app_ws;
  end if;
  select count(*) into pub_tenants from public.tenants;

  if app_ws > 0 and pub_tenants = 0 then
    raise exception
      'Abort M5: app.workspaces has % rows but public.tenants is empty. Re-run M2 first.',
      app_ws;
  end if;
end $$;

-- Drop in dependency-safe order
drop table if exists app.feedback cascade;
drop table if exists app.captures cascade;   -- not the dedup ledger
drop table if exists app.decisions cascade;
drop table if exists app.sources cascade;
drop table if exists app.memberships cascade;
drop table if exists app.workspaces cascade;

-- Do NOT drop storage helpers here — they are owned by storage.policies.
-- Finish with: 006b_fix_storage_helpers_finish_drop.sql

-- Optional non-storage leftovers
drop function if exists app.user_has_tenant_access(uuid);
drop function if exists app.current_tenant_id();
drop function if exists app.set_updated_at();
drop function if exists app.handle_new_user();

-- ---------------------------------------------------------------------
-- Verify (partial — complete after 006b)
-- ---------------------------------------------------------------------
select table_schema, table_name
from information_schema.tables
where table_schema = 'app'
order by 1, 2;

select table_name
from information_schema.tables
where table_schema = 'public'
  and table_type = 'BASE TABLE'
  and table_name in (
    'tenants', 'memberships', 'actors', 'source_connections', 'raw_events',
    'decisions', 'decision_actors', 'decision_sources',
    'decision_embeddings', 'mcp_tool_calls'
  )
order by 1;

select queue_name
from pgmq.list_queues()
order by 1;
