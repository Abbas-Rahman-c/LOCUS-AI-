-- =====================================================================
-- Migration 010: Switch public.decision_embeddings to Voyage AI
-- Model change: text-embedding-3-small (1536-dim) -> voyage-4 (1024-dim)
-- Document embeddings must be generated with input_type="document";
-- query-time embeddings must be generated with input_type="query"
-- (Voyage AI requirement — enforced in application code, not SQL; see
-- backend/src/modules/ai/embeddings/provider.py).
--
-- This branch's decision_embeddings table (schema.sql /
-- 003_public_design_schema.sql) still declares vector(1536), the
-- pre-Voyage dimension. The write path (modules.ai.embeddings.service,
-- modules.decisions.pipeline_persistence) only ever produces 1024-dim
-- Voyage vectors, and Phase 2 retrieval (modules.retrieval.vector.
-- repository) already requires exactly 1024 - so this migration must run
-- before either the ingestion write path or Phase 2 retrieval is pointed
-- at a real database.
--
-- The AI ingestion pipeline (this branch) has not started writing
-- embeddings yet, so this table is expected to be empty. This migration
-- refuses to run otherwise rather than silently deleting or corrupting
-- existing vectors.
--
-- Run AFTER 009_search_decisions_fts.sql. Do NOT apply this to any shared
-- or live database as part of this porting work - local/CI verification
-- only.
--
-- Rollback: safe only while decision_embeddings is still empty (the same
-- condition 10.1 requires to apply forward). To roll back before any row
-- has ever been written under the 1024-dim column:
--   drop index if exists public.idx_decision_embeddings_vec;
--   alter table public.decision_embeddings alter column embedding type vector(1536);
--   alter table public.decision_embeddings alter column embedding_model set default 'text-embedding-3-small';
--   create index if not exists idx_decision_embeddings_vec
--     on public.decision_embeddings using hnsw (embedding vector_cosine_ops);
-- Once any real 1024-dim Voyage row exists, this is no longer a rollback -
-- reverting the column to vector(1536) at that point would be exactly as
-- lossy as the forward resize this migration guards against, and must go
-- through the same "re-embed and intentionally clear the table" path
-- described in 10.1, not a silent ALTER.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 10.0 Pre-flight: vector extension
-- Already enabled by 003_public_design_schema.sql
-- (`create extension if not exists vector;`). Not re-declared here —
-- re-running it is harmless but redundant, and this migration should
-- only ever run after 003.
-- ---------------------------------------------------------------------

-- ---------------------------------------------------------------------
-- 10.1 Safety guard: refuse to run against a non-empty table
-- Resizing vector(1536) -> vector(1024) is lossy: 1536-dim embeddings
-- are not valid points in the 1024-dim Voyage space, so there is no
-- correct way to convert existing rows. Abort loudly instead of
-- truncating or corrupting data if the ingestion pipeline turns out to
-- have already written rows.
-- ---------------------------------------------------------------------
do $$
declare
  existing_rows bigint;
begin
  select count(*) into existing_rows from public.decision_embeddings;

  if existing_rows > 0 then
    raise exception
      'Migration 010 aborted: public.decision_embeddings has % existing row(s). Resizing embedding vector(1536) -> vector(1024) (switch to Voyage voyage-4) would corrupt or discard those rows. Re-embed with voyage-4 and intentionally clear the table before re-running this migration.',
      existing_rows;
  end if;
end $$;

-- ---------------------------------------------------------------------
-- 10.2 Drop the HNSW index before resizing the vector column
-- The index is built against a fixed dimension; drop it here and
-- recreate it after the ALTER so it always matches the live column.
-- ---------------------------------------------------------------------
drop index if exists public.idx_decision_embeddings_vec;

-- ---------------------------------------------------------------------
-- 10.3 Resize embedding: vector(1536) -> vector(1024)
-- Safe only because 10.1 guaranteed the table is empty.
-- ---------------------------------------------------------------------
alter table public.decision_embeddings
  alter column embedding type vector(1024);

-- ---------------------------------------------------------------------
-- 10.4 Drop the old default — require callers to state the model
-- explicitly rather than defaulting to 'text-embedding-3-small'. Voyage
-- ships several model variants (voyage-4, voyage-4-lite, voyage-4-large;
-- see backend/src/common/config/voyage_config.py), so a silent default
-- risks mislabeling embeddings if the chosen model changes. Column stays
-- NOT NULL — every row must still name its model.
-- ---------------------------------------------------------------------
alter table public.decision_embeddings
  alter column embedding_model drop default;

-- ---------------------------------------------------------------------
-- 10.5 Recreate the HNSW index on the resized column
-- Idempotent: `if not exists` matches this repo's existing migration
-- convention (e.g. 003_public_design_schema.sql's own index creation).
-- ---------------------------------------------------------------------
create index if not exists idx_decision_embeddings_vec
  on public.decision_embeddings using hnsw (embedding vector_cosine_ops);

-- decision_id primary key, the tenant_id foreign key, embedded_at,
-- idx_decision_embeddings_tenant, and the RLS policy
-- tenant_isolation_decision_embeddings (all from
-- 003_public_design_schema.sql) are untouched by this migration.
-- No other tables (including public.decisions) are modified.

-- ---------------------------------------------------------------------
-- 10.6 Verify
-- ---------------------------------------------------------------------
select
  a.attname as column_name,
  format_type(a.atttypid, a.atttypmod) as data_type,
  pg_get_expr(d.adbin, d.adrelid) as column_default,
  a.attnotnull as not_null
from pg_attribute a
left join pg_attrdef d
  on d.adrelid = a.attrelid and d.adnum = a.attnum
where a.attrelid = 'public.decision_embeddings'::regclass
  and a.attname in ('embedding', 'embedding_model')
  and a.attnum > 0
  and not a.attisdropped
order by a.attname;

select indexname, indexdef
from pg_indexes
where schemaname = 'public'
  and tablename = 'decision_embeddings';
