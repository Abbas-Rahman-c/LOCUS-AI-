# Migration 010 — apply & verify notes

`010_decision_embeddings_voyage_ai.sql` resizes `public.decision_embeddings.embedding`
from `vector(1536)` to `vector(1024)` for the Voyage voyage-4 switch. It has **not**
been applied to any database as part of this branch's work — local/CI verification
only. Do not run this against a shared or live database without following the steps
below first.

## 1. Check whether decision_embeddings already contains rows

Before applying, run (as whichever role can read the table — `postgres` or `locus_app`):

```sql
select count(*) from public.decision_embeddings;
```

## 2. What happens if rows already exist

The migration's own precondition check (section 10.1) runs this same count and
**aborts the entire migration with `raise exception`** if it is greater than zero.
No `ALTER`, `DROP INDEX`, or `CREATE INDEX` statement in the file ever executes in
that case — the table is left completely untouched. This is not a warning you can
ignore and re-run past; the migration will keep aborting every time until the table
is genuinely empty.

## 3. Existing embeddings must be backed up or regenerated deliberately

A `vector(1536)` embedding (produced by the old `text-embedding-3-small` model) is
not a valid point in Voyage voyage-4's 1024-dimensional space — there is no
correct mathematical conversion between them. If `decision_embeddings` already has
rows when this migration needs to run:

- Export/back up the existing rows first if they have any value (e.g.
  `copy (select * from public.decision_embeddings) to '<path>' with csv header;`,
  or a `pg_dump --table=public.decision_embeddings`), **not** as an automatic step
  performed by this migration.
- Regenerate embeddings for every affected `decision_id` using
  `modules.ai.embeddings.service.process_embedding_job()` (Voyage voyage-4,
  1024-dim) after clearing the table — this is the only correct path back to a
  consistent state, not a `vector(1536)` -> `vector(1024)` cast.
- Only once that is done and the table is confirmed empty should this migration
  be re-run.

## 4. No automatic deletion is authorized

This migration never issues a `DELETE`, `TRUNCATE`, or `DROP TABLE` against
`decision_embeddings` or any other table. If the table needs to be cleared to
unblock this migration, that is a deliberate, separately-authorized operational
action taken by whoever owns the database — never something this migration (or
anyone applying it) should do silently or as a "fix" for the abort in step 2.

## 5. Validating the index and column dimension afterward

The migration's own section 10.6 already runs this verification automatically as
its last step; re-run it standalone any time to confirm:

```sql
-- Column type and default
select a.attname as column_name,
       format_type(a.atttypid, a.atttypmod) as data_type,
       pg_get_expr(d.adbin, d.adrelid) as column_default,
       a.attnotnull as not_null
from pg_attribute a
left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
where a.attrelid = 'public.decision_embeddings'::regclass
  and a.attname in ('embedding', 'embedding_model')
  and a.attnum > 0 and not a.attisdropped
order by a.attname;
-- Expect: embedding -> vector(1024), embedding_model -> no default, not_null = true for both

-- Index presence and definition
select indexname, indexdef
from pg_indexes
where schemaname = 'public' and tablename = 'decision_embeddings';
-- Expect: idx_decision_embeddings_vec using hnsw (embedding vector_cosine_ops)
--         idx_decision_embeddings_tenant on (tenant_id) - untouched by this migration
```

Also confirm application-side that `VOYAGE_OUTPUT_DIMENSION` (backend/.env) is `1024`
and unset/matches `common.config.voyage_config.REQUIRED_OUTPUT_DIMENSION` — a
mismatch there fails loudly at `get_voyage_config()` rather than silently writing
the wrong dimension, but it's worth confirming directly after any migration run.
