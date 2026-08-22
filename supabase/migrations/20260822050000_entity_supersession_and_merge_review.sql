-- Real bug found live: confirmNewEntity only checked for an exact
-- (tenant_id, entity_type, canonical_name) conflict, never re-ran the same
-- similarity check resolveEntityMention uses at extraction time. Bulk-
-- confirming a batch of queued mentions in one sitting created real
-- duplicate entities with zero flag - worse than a deferred review, a
-- silent wrong merge. Two schema additions to fix this properly:

-- 1. entities needs a real supersession concept - merging two CONFIRMED
-- entities (not "mention -> entity", which unresolved_entities already
-- handles) must never delete the losing side, same convention memories
-- already uses (status='superseded', never a hard delete).
alter table public.entities add column if not exists status text not null default 'current'
  check (status in ('current', 'superseded'));
alter table public.entities add column if not exists superseded_by uuid references public.entities(entity_id) on delete set null;

-- 2. unresolved_entities was built around "a raw mention needs resolving",
-- not "two already-confirmed entities might be the same thing" - its
-- mention_text/candidate_entity_id shape doesn't naturally represent that.
-- source_entity_id distinguishes the two cases: null means a genuine
-- unconfirmed mention (existing behavior, unchanged); set means this row
-- represents an ALREADY-CONFIRMED entity flagged for a merge decision,
-- found live-checking at confirm time or by the cross-table audit.
alter table public.unresolved_entities add column if not exists source_entity_id uuid references public.entities(entity_id) on delete cascade;

create index if not exists idx_entities_status on public.entities(tenant_id, status);
create index if not exists idx_unresolved_entities_source on public.unresolved_entities(source_entity_id) where source_entity_id is not null;
