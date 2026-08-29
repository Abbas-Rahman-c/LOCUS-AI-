-- Removes the Memory Intelligence layer (MVP 02) entirely. The Memory
-- Explorer surface (public.decisions and its cascade) plus the original
-- ai-worker pipeline are enough for the product right now - the memory
-- layer (Memory Timeline, Attention strip, entity review queue, Loci
-- query patterns, the check_action MCP tool, Slack membership sync) added
-- real complexity (many filters, a second extraction pipeline, a second
-- permission model) without being worth that cost yet.
--
-- Every table dropped here was created exclusively for this layer,
-- starting at migration 20260822000000 - verified directly before writing
-- this migration: nothing predating that date references
-- public.entities/memories/memory_*/source_scope_members, and nothing in
-- public.decisions or its own cascade (decision_actors/decision_sources/
-- decision_embeddings/decision_conflicts) touches any table dropped here.
--
-- A full data export of every table below was taken before this migration
-- was written (all real rows, as JSON) and kept locally, outside git, in
-- case any of this is wanted again - this migration is not the only copy
-- of that data, and the code itself stays recoverable on two closed (not
-- deleted) branches: feat/memory-explorer-upgrade and
-- perf/ai-worker-deterministic-prefilter.
--
-- Real row counts at the time this was written (informational only):
--   entities 75, entity_embeddings 75, unresolved_entities 175,
--   memory_fixture_events 99, memories 63, memory_entities 141,
--   memory_source_events 63, memory_citations 63, memory_embeddings 63,
--   memory_conflicts 0, memory_resolutions 3, source_scope_members 63.

-- ── Stop the recurring sync before dropping what it writes to ─────────────
-- Paired with 20260822020000_slack_membership_sync_cron.sql, which is left
-- in place as historical record rather than edited - this is the migration
-- that reverses it, matching this repo's own append-only convention.
select cron.unschedule('slack-membership-sync-every-4h')
where exists (select 1 from cron.job where jobname = 'slack-membership-sync-every-4h');

-- ── Drop every memory-layer table ──────────────────────────────────────
-- Cascade order doesn't matter here (all FKs among these tables are
-- `on delete cascade` already, per each table's own creation migration) -
-- CASCADE on every statement is belt-and-suspenders, not load-bearing.
drop table if exists public.memory_resolutions cascade;
drop table if exists public.memory_conflicts cascade;
drop table if exists public.memory_embeddings cascade;
drop table if exists public.memory_citations cascade;
drop table if exists public.memory_source_events cascade;
drop table if exists public.memory_entities cascade;
drop table if exists public.memories cascade;
drop table if exists public.memory_fixture_events cascade;
drop table if exists public.unresolved_entities cascade;
drop table if exists public.entity_embeddings cascade;
drop table if exists public.entities cascade;
drop table if exists public.source_scope_members cascade;
