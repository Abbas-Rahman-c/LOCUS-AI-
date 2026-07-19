-- =====================================================================
-- Local-dev-only schema for docker-compose's `db` service.
--
-- This is NOT one of backend/src/database/migrations/*.sql and is not a
-- substitute for them. Those migrations target Supabase specifically
-- (they reference auth.users, auth.uid(), and Supabase-managed RLS) and
-- will not run against a plain postgres/pgvector image. This file
-- creates just the tables modules.retrieval actually reads/writes
-- (tenants, decisions, decision_sources, decision_embeddings) with the
-- same column shapes and indexes as migration 003, so hybrid.py/rrf.py/
-- resolver.py/the embedding worker can be exercised end-to-end locally
-- without a full Supabase stack.
--
-- No RLS policies here on purpose: tenant isolation for this local schema
-- relies solely on modules.security.tenant_guard's explicit "WHERE
-- tenant_id = $1" pre-filter layer (every retrieval query already
-- carries one) -- see tenant_guard.py's docstring for why that is
-- considered layer one, not a fallback. Deploying against real Supabase
-- restores the RLS layer via the real migrations.
-- =====================================================================

create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists public.tenants (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  slug        text unique not null,
  created_at  timestamptz not null default now()
);

create table if not exists public.actors (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  display_name    text,
  email           text,
  slack_user_id   text,
  notion_user_id  text,
  kind            text not null default 'internal',
  unique (tenant_id, email),
  constraint actors_id_tenant_id_key unique (id, tenant_id)
);

create table if not exists public.decisions (
  id                      uuid primary key default gen_random_uuid(),
  tenant_id               uuid not null references public.tenants(id) on delete cascade,
  record_type             text not null default 'decision',
  decision_statement      text not null,
  rationale               text,
  alternatives_considered text[] not null default '{}',
  status                  text not null default 'proposed',
  scope                   text not null default 'team',
  scope_actor_id          uuid,
  confidence              numeric(4,3) not null default 0.8,
  permission_scope        text[] not null default '{}',
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  constraint decisions_id_tenant_id_key unique (id, tenant_id)
);

create index if not exists idx_decisions_tenant_status on public.decisions (tenant_id, status);
create index if not exists idx_decisions_fts
  on public.decisions
  using gin (to_tsvector('english', decision_statement || ' ' || coalesce(rationale, '')));

create table if not exists public.decision_sources (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  decision_id   uuid not null,
  permalink     text not null,
  created_at    timestamptz not null default now(),
  unique (decision_id, permalink),
  constraint fk_decision_sources_tenant
    foreign key (decision_id, tenant_id)
    references public.decisions(id, tenant_id) on delete cascade
);

create index if not exists idx_decision_sources_decision on public.decision_sources (decision_id);

create table if not exists public.decision_embeddings (
  decision_id     uuid primary key,
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  embedding       vector(1024) not null,
  embedding_model text not null,
  embedded_at     timestamptz not null default now(),
  constraint fk_decision_embeddings_tenant
    foreign key (decision_id, tenant_id)
    references public.decisions(id, tenant_id) on delete cascade
);

create index if not exists idx_decision_embeddings_vec
  on public.decision_embeddings using hnsw (embedding vector_cosine_ops);
create index if not exists idx_decision_embeddings_tenant on public.decision_embeddings (tenant_id);
