-- Memory Intelligence layer (MVP 02) - canonical schema.
--
-- Fed by fixtures for now (hand-written NormalizedEvent[] plus a one-time,
-- read-only replay of real raw_events - see _shared/memory/historicalReplay.ts),
-- never by live ingestion traffic. The existing decisions/decision_actors/
-- decision_sources/decision_embeddings/decision_conflicts tables and the
-- ai-worker pipeline that writes them are completely untouched by this
-- migration - this is a new, parallel model, not a replacement.
--
-- Relational modeling follows this codebase's own precedent (decision_actors,
-- decision_sources as real join tables, not raw arrays): entities[],
-- source_events[], citations[] on the CanonicalMemoryObject each become a
-- join table here, assembled back into JSON shape at read time.
--
-- Every table is tenant-scoped and RLS'd the same way every other tenant
-- table in this schema already is (see 003_public_design_schema.sql) -
-- locus_app already has DML on every public-schema table via
-- 008_create_locus_app_role.sql's `alter default privileges`, so only
-- `enable row level security` + a tenant_isolation policy is needed here,
-- not a fresh grant.

-- ---------------------------------------------------------------------
-- 1. ENTITIES (canonical entity table, per Section 4 of the spec)
-- ---------------------------------------------------------------------
create table if not exists public.entities (
  entity_id      uuid primary key default gen_random_uuid(),
  tenant_id      uuid not null references public.tenants(id) on delete cascade,
  entity_type    text not null
                 check (entity_type in ('Person', 'Team', 'Project', 'Customer', 'Product', 'Topic', 'System')),
  canonical_name text not null,
  aliases        text[] not null default '{}',
  -- Not in the spec - lets the Attention strip's "scoped to user" narrowing
  -- (Batch 3) map a Person-type entity back to a real auth.users row,
  -- without duplicating identity resolution actors.ts already does.
  linked_actor_id uuid references public.actors(id) on delete set null,
  created_at     timestamptz not null default now(),
  unique (tenant_id, entity_type, canonical_name)
);

create index if not exists idx_entities_tenant on public.entities(tenant_id);

create table if not exists public.entity_embeddings (
  entity_id       uuid primary key references public.entities(entity_id) on delete cascade,
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  embedding       vector(1024) not null,
  embedding_model text not null default 'voyage-4-large',
  embedded_at     timestamptz not null default now()
);

create index if not exists idx_entity_embeddings_vec
  on public.entity_embeddings using hnsw (embedding vector_cosine_ops);
create index if not exists idx_entity_embeddings_tenant on public.entity_embeddings(tenant_id);

-- Review queue - low-confidence entity mentions land here instead of being
-- silently auto-created or auto-merged (spec Section 4: "never silently
-- merge two low-confidence candidate entities").
create table if not exists public.unresolved_entities (
  id                  uuid primary key default gen_random_uuid(),
  tenant_id           uuid not null references public.tenants(id) on delete cascade,
  mention_text        text not null,
  entity_type_guess   text,
  memory_id           uuid, -- fk added after memories exists below
  candidate_entity_id uuid references public.entities(entity_id) on delete set null,
  candidate_score     numeric,
  status              text not null default 'pending'
                      check (status in ('pending', 'confirmed_new', 'merged', 'dismissed')),
  resolved_entity_id  uuid references public.entities(entity_id) on delete set null,
  resolved_at         timestamptz,
  created_at          timestamptz not null default now()
);

create index if not exists idx_unresolved_entities_tenant_status
  on public.unresolved_entities(tenant_id, status);

-- ---------------------------------------------------------------------
-- 2. MEMORY_FIXTURE_EVENTS (the NormalizedEvent store - fixtures AND the
--    real historical replay both land here, never the live raw_events)
-- ---------------------------------------------------------------------
create table if not exists public.memory_fixture_events (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references public.tenants(id) on delete cascade,
  source           text not null,
  source_id        text not null,
  actor_id         uuid references public.actors(id) on delete set null,
  actor_display_name text,
  thread_ref       text,
  permission_scope text[] not null default '{}',
  raw_content      text not null,
  url              text,
  occurred_at      timestamptz not null,
  -- Set only for rows pulled from the real historical replay, so it's
  -- always possible to tell a real event apart from a hand-written one.
  replayed_from_raw_event_id uuid,
  created_at       timestamptz not null default now(),
  unique (tenant_id, source, source_id)
);

create index if not exists idx_memory_fixture_events_tenant on public.memory_fixture_events(tenant_id);

-- ---------------------------------------------------------------------
-- 3. MEMORIES (the canonical object itself)
-- ---------------------------------------------------------------------
create table if not exists public.memories (
  memory_id      uuid primary key default gen_random_uuid(),
  tenant_id      uuid not null references public.tenants(id) on delete cascade,
  type           text not null
                 check (type in ('Context', 'Change', 'Commitment', 'Decision', 'Rationale', 'Blocker', 'Outcome', 'Requirement', 'CustomerSignal')),
  title          text not null,
  summary        text not null,
  payload        jsonb not null default '{}',
  -- Promoted out of payload: temporal/reconciliation/Attention-strip queries
  -- all filter on these as first-class dimensions (spec Sections 5, 6, 10),
  -- so they're generated+indexed rather than left buried in jsonb.
  attribute_key   text generated always as (payload->>'attribute_key') stored,
  -- Kept as text, not timestamptz: a ::timestamptz cast isn't immutable
  -- (depends on session timezone), which Postgres rejects in a generated
  -- column. ISO-8601 text still sorts/compares correctly lexicographically;
  -- callers that need a real timestamptz cast it inline at query time
  -- (due_date::timestamptz), same as any other jsonb-derived field.
  due_date        text generated always as (nullif(payload->>'due_date', '')) stored,
  decision_status text generated always as (payload->>'decision_status') stored,
  occurred_at    timestamptz not null,
  valid_from     timestamptz not null,
  valid_until    timestamptz,
  observed_at    timestamptz not null default now(),
  confidence     numeric(4,3) not null check (confidence between 0 and 1),
  authority      numeric,
  -- "stale" is kept in the enum for spec-completeness but is vestigial in
  -- practice - freshness (computed on read, see _shared/memory/freshness.ts)
  -- already covers staleness as a derived state, so nothing here writes it.
  status         text not null default 'current'
                 check (status in ('proposed', 'current', 'stale', 'superseded', 'contradicted', 'unresolved')),
  supersedes     uuid references public.memories(memory_id),
  searchable_text text not null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

-- The reconciliation candidate-lookup index (spec Section 6's detectConflicts
-- query: same tenant + type + attribute_key, not yet superseded).
create index if not exists idx_memories_reconciliation
  on public.memories(tenant_id, type, attribute_key, status);
create index if not exists idx_memories_tenant_status on public.memories(tenant_id, status);
create index if not exists idx_memories_tenant_valid_from on public.memories(tenant_id, valid_from);
create index if not exists idx_memories_tenant_due_date
  on public.memories(tenant_id, due_date) where type = 'Commitment';

alter table public.unresolved_entities
  add constraint fk_unresolved_entities_memory
  foreign key (memory_id) references public.memories(memory_id) on delete set null;

create table if not exists public.memory_entities (
  memory_id  uuid not null references public.memories(memory_id) on delete cascade,
  entity_id  uuid not null references public.entities(entity_id) on delete cascade,
  tenant_id  uuid not null references public.tenants(id) on delete cascade,
  primary key (memory_id, entity_id)
);

create index if not exists idx_memory_entities_entity on public.memory_entities(entity_id);
create index if not exists idx_memory_entities_tenant on public.memory_entities(tenant_id);

create table if not exists public.memory_source_events (
  memory_id        uuid not null references public.memories(memory_id) on delete cascade,
  fixture_event_id uuid not null references public.memory_fixture_events(id) on delete cascade,
  tenant_id        uuid not null references public.tenants(id) on delete cascade,
  primary key (memory_id, fixture_event_id)
);

create index if not exists idx_memory_source_events_tenant on public.memory_source_events(tenant_id);

-- Deliberately separate from memory_source_events: a memory can have 2
-- source events but cite only 1 with a specific excerpt.
create table if not exists public.memory_citations (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references public.tenants(id) on delete cascade,
  memory_id        uuid not null references public.memories(memory_id) on delete cascade,
  fixture_event_id uuid not null references public.memory_fixture_events(id) on delete cascade,
  excerpt_ref      text not null,
  created_at       timestamptz not null default now()
);

create index if not exists idx_memory_citations_memory on public.memory_citations(memory_id);
create index if not exists idx_memory_citations_tenant on public.memory_citations(tenant_id);

create table if not exists public.memory_embeddings (
  memory_id       uuid primary key references public.memories(memory_id) on delete cascade,
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  embedding       vector(1024) not null,
  embedding_model text not null default 'voyage-4-large',
  embedded_at     timestamptz not null default now()
);

create index if not exists idx_memory_embeddings_vec
  on public.memory_embeddings using hnsw (embedding vector_cosine_ops);
create index if not exists idx_memory_embeddings_tenant on public.memory_embeddings(tenant_id);

-- Only ever stores the 'conflict' relation - 'update' never creates a row
-- here, it goes straight through memories.supersedes. This mirrors how
-- decision_conflicts today only ever stores 'contradicts' while
-- 'duplicates' goes through decisions.superseded_by directly - same shape,
-- deliberately, so the "never silently auto-resolve a real conflict" rule
-- (spec Section 6) is a structural fact about this table, not a runtime flag.
create table if not exists public.memory_conflicts (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references public.tenants(id) on delete cascade,
  memory_id        uuid not null references public.memories(memory_id) on delete cascade,
  related_memory_id uuid not null references public.memories(memory_id) on delete cascade,
  relationship     text not null default 'conflict' check (relationship = 'conflict'),
  reason           text,
  confidence       real,
  resolved_at      timestamptz,
  created_at       timestamptz not null default now(),
  unique (memory_id, related_memory_id)
);

create index if not exists idx_memory_conflicts_tenant on public.memory_conflicts(tenant_id);
create index if not exists idx_memory_conflicts_open
  on public.memory_conflicts(tenant_id) where resolved_at is null;

-- Audit log for resolveMemory() - same shape as radar_corrections
-- (008_radar_corrections.sql), the closest existing precedent, but for the
-- new memory model rather than a fresh port of that dead Python endpoint.
create table if not exists public.memory_resolutions (
  id                  uuid primary key default gen_random_uuid(),
  tenant_id           uuid not null references public.tenants(id) on delete cascade,
  memory_id           uuid not null references public.memories(memory_id) on delete cascade,
  action              text not null
                      check (action in ('confirm_current', 'mark_superseded', 'mark_contradicted', 'dismiss_conflict')),
  original_status     text not null,
  note                text,
  resolved_by_actor_id uuid references public.actors(id),
  resolved_at         timestamptz not null default now()
);

create index if not exists idx_memory_resolutions_memory on public.memory_resolutions(memory_id);
create index if not exists idx_memory_resolutions_tenant on public.memory_resolutions(tenant_id);

-- ---------------------------------------------------------------------
-- RLS - every table above, no exceptions, same tenant_isolation pattern
-- as every other tenant table in this schema (003_public_design_schema.sql).
-- ---------------------------------------------------------------------
alter table public.entities              enable row level security;
alter table public.entity_embeddings     enable row level security;
alter table public.unresolved_entities   enable row level security;
alter table public.memory_fixture_events enable row level security;
alter table public.memories              enable row level security;
alter table public.memory_entities       enable row level security;
alter table public.memory_source_events  enable row level security;
alter table public.memory_citations      enable row level security;
alter table public.memory_embeddings     enable row level security;
alter table public.memory_conflicts      enable row level security;
alter table public.memory_resolutions    enable row level security;

drop policy if exists tenant_isolation_entities on public.entities;
create policy tenant_isolation_entities on public.entities
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_entity_embeddings on public.entity_embeddings;
create policy tenant_isolation_entity_embeddings on public.entity_embeddings
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_unresolved_entities on public.unresolved_entities;
create policy tenant_isolation_unresolved_entities on public.unresolved_entities
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_memory_fixture_events on public.memory_fixture_events;
create policy tenant_isolation_memory_fixture_events on public.memory_fixture_events
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_memories on public.memories;
create policy tenant_isolation_memories on public.memories
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_memory_entities on public.memory_entities;
create policy tenant_isolation_memory_entities on public.memory_entities
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_memory_source_events on public.memory_source_events;
create policy tenant_isolation_memory_source_events on public.memory_source_events
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_memory_citations on public.memory_citations;
create policy tenant_isolation_memory_citations on public.memory_citations
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_memory_embeddings on public.memory_embeddings;
create policy tenant_isolation_memory_embeddings on public.memory_embeddings
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_memory_conflicts on public.memory_conflicts;
create policy tenant_isolation_memory_conflicts on public.memory_conflicts
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_memory_resolutions on public.memory_resolutions;
create policy tenant_isolation_memory_resolutions on public.memory_resolutions
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);
