-- =====================================================================
-- LOCUS-AI Step 6: sources, captures, feedback
-- Run in Supabase SQL Editor after Step 2 bootstrap.
-- All tables: tenant_id + RLS + updated_at
-- =====================================================================

create extension if not exists vector;

-- ---------------------------------------------------------------------
-- SOURCES (Slack / Gmail / Notion connections)
-- Matches backend queries: type, workspace_id, external_workspace_id
-- ---------------------------------------------------------------------
create table if not exists app.sources (
  id                    uuid primary key default gen_random_uuid(),
  tenant_id             uuid not null references app.workspaces(tenant_id) on delete cascade,
  type                  text not null check (type in ('slack', 'gmail', 'notion')),
  external_workspace_id text,
  oauth_token_ref       text,
  status                text not null default 'active'
                        check (status in ('active', 'paused', 'error', 'revoked')),
  ingestion_mode        text not null default 'realtime'
                        check (ingestion_mode in ('realtime', 'near_realtime', 'polling')),
  cursor_state          jsonb not null default '{}',
  watch_expiry          timestamptz,
  last_synced_at        timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  unique (tenant_id, type, external_workspace_id)
);

create index if not exists idx_sources_tenant_id on app.sources(tenant_id);
create index if not exists idx_sources_type on app.sources(type);
create index if not exists idx_sources_external_workspace_id on app.sources(external_workspace_id);
create index if not exists idx_sources_watch_expiry on app.sources(watch_expiry)
  where watch_expiry is not null;

drop trigger if exists trg_sources_updated_at on app.sources;
create trigger trg_sources_updated_at
before update on app.sources
for each row execute function app.set_updated_at();

-- ---------------------------------------------------------------------
-- CAPTURES (AI-extracted records from ingestion pipeline)
-- ---------------------------------------------------------------------
create table if not exists app.captures (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references app.workspaces(tenant_id) on delete cascade,
  source          text not null check (source in ('slack', 'gmail', 'notion')),
  source_id       text not null,
  record_type     text not null default 'decision'
                  check (record_type in ('decision', 'action_item', 'blocker')),
  title           text not null,
  body            text,
  confidence      numeric(4,3),
  status          text not null default 'proposed'
                  check (status in ('proposed', 'confirmed', 'rejected', 'superseded')),
  raw_event_id    uuid,
  metadata        jsonb not null default '{}',
  embedding       vector(1536),
  embedding_model text,
  embedded_at     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (tenant_id, source, source_id)
);

create index if not exists idx_captures_tenant_id on app.captures(tenant_id);
create index if not exists idx_captures_tenant_status on app.captures(tenant_id, status);
create index if not exists idx_captures_source on app.captures(tenant_id, source);
create index if not exists idx_captures_metadata on app.captures using gin (metadata);

drop trigger if exists trg_captures_updated_at on app.captures;
create trigger trg_captures_updated_at
before update on app.captures
for each row execute function app.set_updated_at();

-- ---------------------------------------------------------------------
-- FEEDBACK (thumbs up/down on answers or captures)
-- ---------------------------------------------------------------------
create table if not exists app.feedback (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references app.workspaces(tenant_id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  target_type text not null check (target_type in ('capture', 'answer')),
  target_id   uuid not null,
  signal      text not null check (signal in ('up', 'down')),
  comment     text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (tenant_id, user_id, target_type, target_id)
);

create index if not exists idx_feedback_tenant_id on app.feedback(tenant_id);
create index if not exists idx_feedback_target on app.feedback(tenant_id, target_type, target_id);

drop trigger if exists trg_feedback_updated_at on app.feedback;
create trigger trg_feedback_updated_at
before update on app.feedback
for each row execute function app.set_updated_at();

-- ---------------------------------------------------------------------
-- RLS helper: user belongs to tenant
-- ---------------------------------------------------------------------
create or replace function app.user_has_tenant_access(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = app, public
as $$
  select exists (
    select 1
    from app.memberships m
    where m.user_id = auth.uid()
      and m.tenant_id = p_tenant_id
  )
$$;

-- ---------------------------------------------------------------------
-- RLS: sources
-- ---------------------------------------------------------------------
alter table app.sources enable row level security;

drop policy if exists sources_select on app.sources;
create policy sources_select on app.sources
for select using (app.user_has_tenant_access(tenant_id));

drop policy if exists sources_insert on app.sources;
create policy sources_insert on app.sources
for insert with check (app.user_has_tenant_access(tenant_id));

drop policy if exists sources_update on app.sources;
create policy sources_update on app.sources
for update
using (app.user_has_tenant_access(tenant_id))
with check (app.user_has_tenant_access(tenant_id));

drop policy if exists sources_delete on app.sources;
create policy sources_delete on app.sources
for delete using (app.user_has_tenant_access(tenant_id));

-- ---------------------------------------------------------------------
-- RLS: captures
-- ---------------------------------------------------------------------
alter table app.captures enable row level security;

drop policy if exists captures_select on app.captures;
create policy captures_select on app.captures
for select using (app.user_has_tenant_access(tenant_id));

drop policy if exists captures_insert on app.captures;
create policy captures_insert on app.captures
for insert with check (app.user_has_tenant_access(tenant_id));

drop policy if exists captures_update on app.captures;
create policy captures_update on app.captures
for update
using (app.user_has_tenant_access(tenant_id))
with check (app.user_has_tenant_access(tenant_id));

drop policy if exists captures_delete on app.captures;
create policy captures_delete on app.captures
for delete using (app.user_has_tenant_access(tenant_id));

-- ---------------------------------------------------------------------
-- RLS: feedback
-- ---------------------------------------------------------------------
alter table app.feedback enable row level security;

drop policy if exists feedback_select on app.feedback;
create policy feedback_select on app.feedback
for select using (app.user_has_tenant_access(tenant_id));

drop policy if exists feedback_insert on app.feedback;
create policy feedback_insert on app.feedback
for insert with check (
  app.user_has_tenant_access(tenant_id)
  and user_id = auth.uid()
);

drop policy if exists feedback_update on app.feedback;
create policy feedback_update on app.feedback
for update
using (app.user_has_tenant_access(tenant_id) and user_id = auth.uid())
with check (app.user_has_tenant_access(tenant_id) and user_id = auth.uid());

drop policy if exists feedback_delete on app.feedback;
create policy feedback_delete on app.feedback
for delete using (app.user_has_tenant_access(tenant_id) and user_id = auth.uid());

-- ---------------------------------------------------------------------
-- Public views for Supabase REST API (/rest/v1/sources, etc.)
-- Maps workspace_id -> tenant_id for existing backend code.
-- ---------------------------------------------------------------------
create or replace view public.sources
with (security_invoker = true) as
select
  id,
  tenant_id as workspace_id,
  type,
  external_workspace_id,
  oauth_token_ref,
  status,
  ingestion_mode,
  cursor_state,
  watch_expiry,
  last_synced_at,
  created_at,
  updated_at
from app.sources;

create or replace view public.captures
with (security_invoker = true) as
select *
from app.captures;

create or replace view public.feedback
with (security_invoker = true) as
select *
from app.feedback;

grant select, insert, update, delete on public.sources to authenticated, service_role;
grant select, insert, update, delete on public.captures to authenticated, service_role;
grant select, insert, update, delete on public.feedback to authenticated, service_role;
