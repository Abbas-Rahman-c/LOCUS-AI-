-- =====================================================================
-- Non-bypass app role for tenant-scoped workers / API
-- Mirrors backend/src/database/migrations/008_create_locus_app_role.sql
-- Apply AFTER rls_tenant_isolation migration. Set password out-of-band:
--   alter role locus_app with password '<strong-password>';
-- APP_DATABASE_URL connects as locus_app; DATABASE_URL stays postgres.
-- =====================================================================

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'locus_app') then
    create role locus_app with
      login
      nosuperuser
      nocreatedb
      nocreaterole
      nobypassrls;
  else
    alter role locus_app with login nosuperuser nobypassrls;
  end if;
end $$;

grant usage on schema public to locus_app;

grant select, insert, update, delete on all tables in schema public to locus_app;
grant usage, select on all sequences in schema public to locus_app;
grant execute on all functions in schema public to locus_app;

alter default privileges in schema public
  grant select, insert, update, delete on tables to locus_app;
alter default privileges in schema public
  grant usage, select on sequences to locus_app;
alter default privileges in schema public
  grant execute on functions to locus_app;

do $$
begin
  if exists (select 1 from pg_namespace where nspname = 'pgmq') then
    execute 'grant usage on schema pgmq to locus_app';
    execute 'grant select, insert, update, delete on all tables in schema pgmq to locus_app';
    execute 'grant usage, select on all sequences in schema pgmq to locus_app';
    execute 'grant execute on all functions in schema pgmq to locus_app';
    execute 'alter default privileges in schema pgmq grant select, insert, update, delete on tables to locus_app';
    execute 'alter default privileges in schema pgmq grant execute on functions to locus_app';
  end if;
end $$;

-- oauth_tokens has no tenant_id; allow locus_app only (clients stay denied)
alter table public.oauth_tokens enable row level security;
alter table public.oauth_tokens force row level security;
drop policy if exists oauth_tokens_locus_app on public.oauth_tokens;
create policy oauth_tokens_locus_app on public.oauth_tokens
  for all
  to locus_app
  using (true)
  with check (true);
