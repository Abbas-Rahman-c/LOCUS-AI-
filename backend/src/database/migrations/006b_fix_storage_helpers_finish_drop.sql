-- =====================================================================
-- M5.2 fix: move Storage RLS helpers from app → public, then finish drop
-- Run this after 006 failed on app.user_can_access_storage_object
-- =====================================================================

-- ---------------------------------------------------------------------
-- A) Recreate helpers in public (use public.memberships)
-- ---------------------------------------------------------------------
create or replace function public.storage_tenant_id(object_name text)
returns uuid
language sql
stable
as $$
  select nullif(split_part(object_name, '/', 2), '')::uuid
$$;

create or replace function public.user_can_access_storage_object(object_name text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.memberships m
    where m.user_id = auth.uid()
      and m.tenant_id = public.storage_tenant_id(object_name)
  )
$$;

-- ---------------------------------------------------------------------
-- B) Drop old storage policies that reference app.* helpers
-- ---------------------------------------------------------------------
drop policy if exists "raw_ingestion_select" on storage.objects;
drop policy if exists "raw_ingestion_insert" on storage.objects;
drop policy if exists "raw_ingestion_update" on storage.objects;
drop policy if exists "raw_ingestion_delete" on storage.objects;

drop policy if exists "artifacts_select" on storage.objects;
drop policy if exists "artifacts_insert" on storage.objects;
drop policy if exists "artifacts_update" on storage.objects;
drop policy if exists "artifacts_delete" on storage.objects;

drop policy if exists "exports_select" on storage.objects;
drop policy if exists "exports_insert" on storage.objects;
drop policy if exists "exports_update" on storage.objects;
drop policy if exists "exports_delete" on storage.objects;

-- ---------------------------------------------------------------------
-- C) Recreate storage policies using public.* helpers
-- Path format remains: tenant/{tenant_id}/...
-- ---------------------------------------------------------------------
create policy "raw_ingestion_select"
on storage.objects for select
using (
  bucket_id = 'raw-ingestion'
  and public.user_can_access_storage_object(name)
);

create policy "raw_ingestion_insert"
on storage.objects for insert
with check (
  bucket_id = 'raw-ingestion'
  and public.user_can_access_storage_object(name)
);

create policy "raw_ingestion_update"
on storage.objects for update
using (
  bucket_id = 'raw-ingestion'
  and public.user_can_access_storage_object(name)
)
with check (
  bucket_id = 'raw-ingestion'
  and public.user_can_access_storage_object(name)
);

create policy "raw_ingestion_delete"
on storage.objects for delete
using (
  bucket_id = 'raw-ingestion'
  and public.user_can_access_storage_object(name)
);

create policy "artifacts_select"
on storage.objects for select
using (
  bucket_id = 'artifacts'
  and public.user_can_access_storage_object(name)
);

create policy "artifacts_insert"
on storage.objects for insert
with check (
  bucket_id = 'artifacts'
  and public.user_can_access_storage_object(name)
);

create policy "artifacts_update"
on storage.objects for update
using (
  bucket_id = 'artifacts'
  and public.user_can_access_storage_object(name)
)
with check (
  bucket_id = 'artifacts'
  and public.user_can_access_storage_object(name)
);

create policy "artifacts_delete"
on storage.objects for delete
using (
  bucket_id = 'artifacts'
  and public.user_can_access_storage_object(name)
);

create policy "exports_select"
on storage.objects for select
using (
  bucket_id = 'exports'
  and public.user_can_access_storage_object(name)
);

create policy "exports_insert"
on storage.objects for insert
with check (
  bucket_id = 'exports'
  and public.user_can_access_storage_object(name)
);

create policy "exports_update"
on storage.objects for update
using (
  bucket_id = 'exports'
  and public.user_can_access_storage_object(name)
)
with check (
  bucket_id = 'exports'
  and public.user_can_access_storage_object(name)
);

create policy "exports_delete"
on storage.objects for delete
using (
  bucket_id = 'exports'
  and public.user_can_access_storage_object(name)
);

-- ---------------------------------------------------------------------
-- D) Now safe to drop remaining app helpers / schema
-- ---------------------------------------------------------------------
drop function if exists app.user_has_tenant_access(uuid);
drop function if exists app.user_can_access_storage_object(text);
drop function if exists app.storage_tenant_id(text);
drop function if exists app.current_tenant_id();
drop function if exists app.set_updated_at();
drop function if exists app.handle_new_user();

drop schema if exists app cascade;

-- ---------------------------------------------------------------------
-- E) Verify
-- ---------------------------------------------------------------------
select nspname
from pg_namespace
where nspname = 'app';

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

select policyname
from pg_policies
where schemaname = 'storage'
  and tablename = 'objects'
order by 1;

select queue_name from pgmq.list_queues() order by 1;
