-- =====================================================================
-- M1: Create design schema in public (empty tables)
-- Source: REF/Design/Data/updated schema.sql (v3.2) + memberships
-- Dedup ledger = raw_events UNIQUE (tenant_id, source, source_id)
-- Does NOT create captures
-- =====================================================================

create extension if not exists vector;
create extension if not exists pgcrypto;

-- Drop Step-6 compatibility views that pointed at app.* (recreated in M3)
drop view if exists public.sources cascade;
drop view if exists public.captures cascade;
drop view if exists public.feedback cascade;

-- ---------------------------------------------------------------------
-- 1. TENANTS
-- ---------------------------------------------------------------------
create table if not exists public.tenants (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  slug        text unique not null,
  plan        text not null default 'self_serve'
              check (plan in ('self_serve', 'team')),
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 1b. MEMBERSHIPS (Auth; not in design SQL but required)
-- ---------------------------------------------------------------------
create table if not exists public.memberships (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  role        text not null check (role in ('owner', 'admin', 'member')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (tenant_id, user_id)
);

create index if not exists idx_memberships_user_id on public.memberships(user_id);
create index if not exists idx_memberships_tenant_id on public.memberships(tenant_id);

-- ---------------------------------------------------------------------
-- 2. ACTORS
-- ---------------------------------------------------------------------
create table if not exists public.actors (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  auth_user_id    uuid,
  display_name    text,
  email           text,
  slack_user_id   text,
  notion_user_id  text,
  kind            text not null default 'internal'
                  check (kind in ('internal', 'external')),
  created_at      timestamptz not null default now(),
  unique (tenant_id, email),
  constraint actors_id_tenant_id_key unique (id, tenant_id)
);

-- ---------------------------------------------------------------------
-- 3. SOURCE_CONNECTIONS
-- oauth_token_ref nullable until Vault wiring is complete
-- ---------------------------------------------------------------------
create table if not exists public.source_connections (
  id                      uuid primary key default gen_random_uuid(),
  tenant_id               uuid not null references public.tenants(id) on delete cascade,
  source                  text not null check (source in ('slack', 'gmail', 'notion')),
  external_workspace_id   text,
  oauth_token_ref         text,
  ingestion_mode          text not null
                          check (ingestion_mode in ('realtime', 'near_realtime', 'polling')),
  status                  text not null default 'active'
                          check (status in ('active', 'paused', 'error', 'revoked')),
  cursor_state            jsonb not null default '{}',
  last_synced_at          timestamptz,
  created_at              timestamptz not null default now(),
  unique (tenant_id, source, external_workspace_id)
);

create index if not exists idx_source_connections_tenant
  on public.source_connections(tenant_id);
create index if not exists idx_source_connections_external
  on public.source_connections(external_workspace_id);

-- ---------------------------------------------------------------------
-- 4. RAW_EVENTS  (= Section 1.5 dedup ledger + 1.6 raw store)
-- UNIQUE (tenant_id, source, source_id) is the dedup key
-- ---------------------------------------------------------------------
create table if not exists public.raw_events (
  id                  uuid primary key default gen_random_uuid(),
  tenant_id           uuid not null references public.tenants(id) on delete cascade,
  connection_id       uuid not null references public.source_connections(id) on delete cascade,
  source              text not null check (source in ('slack', 'gmail', 'notion')),
  source_id           text not null,
  thread_ref          text,
  actor_id            uuid,
  permission_scope    text[] not null default '{}',
  raw_content         bytea not null,
  metadata            jsonb not null default '{}',
  received_at         timestamptz not null default now(),
  expires_at          timestamptz not null default (now() + interval '30 days'),
  triage_result       text check (triage_result in ('pending', 'kept', 'uncertain', 'discarded')),
  triage_at           timestamptz,
  unique (tenant_id, source, source_id),
  constraint raw_events_id_tenant_id_key unique (id, tenant_id),
  constraint fk_raw_events_actor_tenant
    foreign key (actor_id, tenant_id) references public.actors(id, tenant_id)
);

create index if not exists idx_raw_events_tenant_time
  on public.raw_events (tenant_id, received_at desc);
create index if not exists idx_raw_events_thread
  on public.raw_events (thread_ref);
create index if not exists idx_raw_events_expiry
  on public.raw_events (expires_at);
create index if not exists idx_raw_events_metadata
  on public.raw_events using gin (metadata);
create index if not exists idx_raw_events_triage
  on public.raw_events (triage_result) where triage_result = 'discarded';

-- ---------------------------------------------------------------------
-- 5. DECISIONS
-- ---------------------------------------------------------------------
create table if not exists public.decisions (
  id                      uuid primary key default gen_random_uuid(),
  tenant_id               uuid not null references public.tenants(id) on delete cascade,
  record_type             text not null default 'decision'
                          check (record_type in ('decision', 'action_item', 'blocker')),
  decision_statement      text not null,
  rationale               text,
  alternatives_considered text[] not null default '{}',
  status                  text not null default 'proposed'
                          check (status in ('proposed', 'decided', 'superseded')),
  superseded_by           uuid,
  scope                   text not null default 'team'
                          check (scope in ('user', 'team')),
  scope_actor_id          uuid,
  confidence              numeric(4,3) not null,
  permission_scope        text[] not null default '{}',
  origin_raw_event_id     uuid,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  constraint decisions_id_tenant_id_key unique (id, tenant_id),
  constraint fk_decisions_superseded_tenant
    foreign key (superseded_by, tenant_id) references public.decisions(id, tenant_id),
  constraint fk_decisions_actor_tenant
    foreign key (scope_actor_id, tenant_id) references public.actors(id, tenant_id),
  constraint fk_decisions_origin_event_tenant
    foreign key (origin_raw_event_id, tenant_id) references public.raw_events(id, tenant_id)
);

create index if not exists idx_decisions_tenant_status
  on public.decisions (tenant_id, status);
create index if not exists idx_decisions_scope
  on public.decisions (tenant_id, scope, scope_actor_id);
create index if not exists idx_decisions_fts
  on public.decisions
  using gin (to_tsvector('english', decision_statement || ' ' || coalesce(rationale, '')));

-- ---------------------------------------------------------------------
-- 6. DECISION_ACTORS
-- ---------------------------------------------------------------------
create table if not exists public.decision_actors (
  tenant_id   uuid not null references public.tenants(id) on delete cascade,
  decision_id uuid not null,
  actor_id    uuid not null,
  role        text not null default 'decided_by'
              check (role in ('decided_by', 'mentioned')),
  primary key (decision_id, actor_id, role),
  constraint fk_decision_actors_tenant
    foreign key (decision_id, tenant_id)
    references public.decisions(id, tenant_id) on delete cascade,
  constraint fk_decision_actors_actor
    foreign key (actor_id, tenant_id)
    references public.actors(id, tenant_id) on delete cascade
);

create index if not exists idx_decision_actors_tenant
  on public.decision_actors (tenant_id);

-- ---------------------------------------------------------------------
-- 7. DECISION_SOURCES
-- ---------------------------------------------------------------------
create table if not exists public.decision_sources (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  decision_id   uuid not null,
  raw_event_id  uuid,
  permalink     text not null,
  created_at    timestamptz not null default now(),
  unique (decision_id, permalink),
  constraint fk_decision_sources_tenant
    foreign key (decision_id, tenant_id)
    references public.decisions(id, tenant_id) on delete cascade,
  constraint fk_decision_sources_event
    foreign key (raw_event_id, tenant_id)
    references public.raw_events(id, tenant_id) on delete set null
);

create index if not exists idx_decision_sources_decision
  on public.decision_sources (decision_id);
create index if not exists idx_decision_sources_tenant
  on public.decision_sources (tenant_id);

-- ---------------------------------------------------------------------
-- 8. DECISION_EMBEDDINGS
-- ---------------------------------------------------------------------
create table if not exists public.decision_embeddings (
  decision_id     uuid primary key,
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  embedding       vector(1536) not null,
  embedding_model text not null default 'text-embedding-3-small',
  embedded_at     timestamptz not null default now(),
  constraint fk_decision_embeddings_tenant
    foreign key (decision_id, tenant_id)
    references public.decisions(id, tenant_id) on delete cascade
);

create index if not exists idx_decision_embeddings_vec
  on public.decision_embeddings using hnsw (embedding vector_cosine_ops);
create index if not exists idx_decision_embeddings_tenant
  on public.decision_embeddings (tenant_id);

-- ---------------------------------------------------------------------
-- 9. MCP_TOOL_CALLS
-- ---------------------------------------------------------------------
create table if not exists public.mcp_tool_calls (
  id                  uuid primary key default gen_random_uuid(),
  tenant_id           uuid not null references public.tenants(id) on delete cascade,
  requesting_client   text not null,
  tool_name           text not null,
  request_params      jsonb not null,
  result_decision_ids uuid[],
  latency_ms          int,
  called_at           timestamptz not null default now()
);

create index if not exists idx_mcp_tool_calls_tenant_time
  on public.mcp_tool_calls (tenant_id, called_at desc);

-- ---------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------
create or replace function public.update_modified_column()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists update_decisions_modtime on public.decisions;
create trigger update_decisions_modtime
before update on public.decisions
for each row execute function public.update_modified_column();

drop trigger if exists update_memberships_modtime on public.memberships;
create trigger update_memberships_modtime
before update on public.memberships
for each row execute function public.update_modified_column();

-- ---------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------
alter table public.tenants             enable row level security;
alter table public.memberships         enable row level security;
alter table public.actors              enable row level security;
alter table public.source_connections  enable row level security;
alter table public.raw_events          enable row level security;
alter table public.decisions           enable row level security;
alter table public.decision_actors     enable row level security;
alter table public.decision_sources    enable row level security;
alter table public.decision_embeddings enable row level security;
alter table public.mcp_tool_calls      enable row level security;

-- Design-style tenant GUC policies
drop policy if exists tenant_isolation_actors on public.actors;
create policy tenant_isolation_actors on public.actors
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_source_connections on public.source_connections;
create policy tenant_isolation_source_connections on public.source_connections
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_raw_events on public.raw_events;
create policy tenant_isolation_raw_events on public.raw_events
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_decisions on public.decisions;
create policy tenant_isolation_decisions on public.decisions
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_decision_actors on public.decision_actors;
create policy tenant_isolation_decision_actors on public.decision_actors
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_decision_sources on public.decision_sources;
create policy tenant_isolation_decision_sources on public.decision_sources
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_decision_embeddings on public.decision_embeddings;
create policy tenant_isolation_decision_embeddings on public.decision_embeddings
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_mcp_tool_calls on public.mcp_tool_calls;
create policy tenant_isolation_mcp_tool_calls on public.mcp_tool_calls
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

-- Memberships: user can see their own membership rows
drop policy if exists memberships_select_own on public.memberships;
create policy memberships_select_own on public.memberships
  for select using (user_id = auth.uid());

-- Tenants: user can see tenants they belong to
drop policy if exists tenants_select_member on public.tenants;
create policy tenants_select_member on public.tenants
  for select using (
    id in (select m.tenant_id from public.memberships m where m.user_id = auth.uid())
  );
