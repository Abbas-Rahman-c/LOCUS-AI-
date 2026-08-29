-- Memory Explorer upgrade (MVP 02 architecture), Phase 1: schema changes.
-- Implements docs/Solution_for_upgrade_memory-explorer.md Section 1/5.
--
-- Scope decision, called out explicitly for reviewers: this migration is
-- deliberately ADDITIVE, not destructive. The source doc's Phase 1 step 3
-- says to drop public.unresolved_entities and public.memory_fixture_events
-- outright. Both memory_source_events and memory_citations currently hold
-- an `on delete cascade` FK to memory_fixture_events - dropping that table
-- as written would silently cascade-delete every existing memory's
-- provenance rows, including real production memories already loaded for
-- real tenants this session. That's not what "retire the fixture-event
-- indirection" should mean. This migration instead:
--   1. Points new provenance rows at raw_events directly (the doc's actual
--      goal - ai-worker writing straight from raw_events, no intermediary).
--   2. Leaves memory_fixture_events and its existing FKs in place so no
--      existing data is destroyed.
-- Actually dropping memory_fixture_events/unresolved_entities is left as a
-- separate, explicit follow-up once there's a real data migration path for
-- whatever rows still reference them - not bundled into this PR silently.

-- ── 3-core-type taxonomy (memories.type) ──────────────────────────────
-- Was: Context, Change, Commitment, Decision, Rationale, Blocker, Outcome,
-- Requirement, CustomerSignal (9 types). Rationale/Outcome/Requirement/
-- Change/CustomerSignal collapse into Decision's payload per the doc's
-- Section 2 mapping table rather than being separate memory rows.
alter table public.memories drop constraint if exists memories_type_check;
alter table public.memories add constraint memories_type_check
  check (type in ('Decision', 'Commitment', 'Blocker'));

-- ── 3 relational entity types (entities.entity_type) ──────────────────
-- Was: Person, Team, Project, Customer, Product, Topic, System (7 types).
-- Customer/Product/Topic/System demote to searchable tags on memories
-- rather than relational entities - see memories.tags below.
alter table public.entities drop constraint if exists entities_entity_type_check;
alter table public.entities add constraint entities_entity_type_check
  check (entity_type in ('Person', 'Team', 'Project'));

-- ── Demoted concepts become searchable tags, not entity rows ──────────
-- Section 3 "Demotion of Content Concepts": System/Topic/Product mentions
-- no longer create entities or occupy the review queue - they're metadata
-- on the memory itself instead.
alter table public.memories add column if not exists tags text[] not null default '{}';
create index if not exists idx_memories_tags on public.memories using gin (tags);

-- ── Direct raw_events provenance (retires the fixture-event indirection
-- for new writes going forward) ───────────────────────────────────────
alter table public.memory_source_events add column if not exists raw_event_id uuid references public.raw_events(id) on delete cascade;
alter table public.memory_source_events alter column fixture_event_id drop not null;
create index if not exists idx_memory_source_events_raw_event on public.memory_source_events(raw_event_id);

alter table public.memory_citations add column if not exists raw_event_id uuid references public.raw_events(id) on delete cascade;
alter table public.memory_citations alter column fixture_event_id drop not null;
create index if not exists idx_memory_citations_raw_event on public.memory_citations(raw_event_id);

-- A provenance row must point at exactly one of the two sources - never
-- both, never neither - so it's always clear which pipeline a given
-- memory's evidence came from.
alter table public.memory_source_events drop constraint if exists memory_source_events_one_source;
alter table public.memory_source_events add constraint memory_source_events_one_source
  check ((raw_event_id is not null) <> (fixture_event_id is not null));

alter table public.memory_citations drop constraint if exists memory_citations_one_source;
alter table public.memory_citations add constraint memory_citations_one_source
  check ((raw_event_id is not null) <> (fixture_event_id is not null));

-- ── Deterministic entity anchors (Section 3) ───────────────────────────
-- The connector-native identifier a Person/Project/Team entity was
-- resolved from, so re-encountering the same actor_id/channel_id/
-- notion_db_id upserts the SAME entity with zero LLM/vector calls, instead
-- of going through embedding similarity or judgeEntityMatch. Unique per
-- (tenant, entity_type, anchor) so two different connectors' ids can never
-- collide across tenants or types.
alter table public.entities add column if not exists source_anchor text;
create unique index if not exists idx_entities_source_anchor
  on public.entities(tenant_id, entity_type, source_anchor)
  where source_anchor is not null and status = 'active';

-- ── Bounded reconciliation candidate lookup (Section 4) ────────────────
-- The exact index the doc's own pre-filter query needs: tenant + type +
-- attribute_key + status='current' + valid_until is null, ORDER BY
-- valid_from DESC LIMIT 3. Without this the "bounded" query still scans.
create index if not exists idx_memories_reconcile_candidates
  on public.memories(tenant_id, type, attribute_key, valid_from desc)
  where status = 'current' and valid_until is null;
