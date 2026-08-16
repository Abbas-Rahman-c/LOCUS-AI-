-- Early access gate: only allowlisted emails get a tenant + owner membership
-- provisioned on signup (public.handle_new_user(), fired by the
-- on_auth_user_created trigger on auth.users - see
-- backend/src/database/migrations/005_auth_trigger_and_sources_view.sql for
-- the original version this replaces).
--
-- This trigger only fires on INSERT into auth.users, i.e. brand new signups
-- - it never runs again for existing rows, so every account that already
-- has a tenant (the team's own accounts) is completely unaffected by this
-- change. A rejected new signup still gets a normal Supabase Auth session
-- (their auth.users row is created either way - Supabase Auth requires
-- that to succeed), but with no tenant every RLS-protected query returns
-- nothing; the frontend is expected to detect "authenticated with no
-- tenant" and show a waitlist screen rather than a broken empty dashboard.

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
  allowed_emails text[] := array[
    'djagani@umich.edu',
    'saishrivastava09@gmail.com',
    'saiapurva.shrivastava04@gmail.com',
    'kirtirungta60@gmail.com',
    'lam.dao@cstu.edu',
    'tansalmir.digi@gmail.com',
    'apply@pmaccelerator.io',
    'soumyasharma364@gmail.com',
    'moniqueamavour@gmail.com',
    'anil.thomas.mba@gmail.com'
  ];
begin
  if not (lower(new.email) = any(allowed_emails)) then
    return new;
  end if;

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
