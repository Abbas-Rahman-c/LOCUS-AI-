-- =====================================================================
-- M3: Auth trigger → public.tenants/memberships
--     + public.sources compatibility view for Slack REST (/rest/v1/sources)
-- Run AFTER 004_migrate_app_to_public.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- 3.1 Signup trigger: create tenant + owner membership
-- ---------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_tenant_id uuid := gen_random_uuid();
  base_slug text;
  final_slug text;
begin
  base_slug := lower(
    regexp_replace(
      coalesce(nullif(trim(new.raw_user_meta_data->>'full_name'), ''), split_part(new.email, '@', 1), 'workspace'),
      '[^a-zA-Z0-9]+',
      '-',
      'g'
    )
  );
  final_slug := trim(both '-' from base_slug) || '-' || substr(replace(new_tenant_id::text, '-', ''), 1, 8);

  insert into public.tenants (id, name, slug, plan)
  values (
    new_tenant_id,
    coalesce(new.raw_user_meta_data->>'full_name', new.email, 'My Workspace'),
    final_slug,
    'self_serve'
  );

  insert into public.memberships (tenant_id, user_id, role)
  values (new_tenant_id, new.id, 'owner');

  return new;
end;
$$;

-- Remove old app-schema trigger if present, then attach to auth.users
drop trigger if exists on_auth_user_created on auth.users;
drop function if exists app.handle_new_user();

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------
-- 3.2 Compatibility view: public.sources
-- Maps design source_connections → Slack connector field names
-- workspace_id = tenant_id, type = source
-- ---------------------------------------------------------------------
drop view if exists public.sources cascade;

create view public.sources
with (security_invoker = true)
as
select
  id,
  tenant_id as workspace_id,
  source as type,
  external_workspace_id,
  oauth_token_ref,
  status,
  ingestion_mode,
  cursor_state,
  last_synced_at,
  created_at
from public.source_connections;

grant select on public.sources to authenticated, service_role;

-- Writable path for service_role / connectors: prefer source_connections directly.
-- Optional INSTEAD OF triggers can be added later if REST inserts must hit /sources.

-- ---------------------------------------------------------------------
-- 3.3 Verify
-- ---------------------------------------------------------------------
select
  tgname as trigger_name,
  pg_get_triggerdef(t.oid) as definition
from pg_trigger t
join pg_class c on c.oid = t.tgrelid
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'auth'
  and c.relname = 'users'
  and not t.tgisinternal
  and tgname = 'on_auth_user_created';

select table_schema, table_name, table_type
from information_schema.tables
where table_schema = 'public'
  and table_name = 'sources';

select count(*) as source_connections_via_view
from public.sources;
