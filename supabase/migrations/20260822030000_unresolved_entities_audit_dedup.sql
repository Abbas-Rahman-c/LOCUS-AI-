-- Real bug found live: handleAuditBatch1Entities (POST /audit/batch1-entities)
-- inserts a public.unresolved_entities row for every flagged pair with no
-- dedup guard - unresolved_entities.id is the only unique key, so a second
-- call against the same tenant re-inserts every pair again. Confirmed live:
-- a tenant with 39 real flagged pairs had 78 pending rows, every one an
-- exact (mention_text, candidate_entity_id) duplicate.
--
-- Scoped narrowly to the audit's own insert shape (memory_id is null,
-- candidate_entity_id is not null) so it does NOT constrain
-- resolveEntityMention's normal queueing path, where the same
-- mention_text/candidate pair legitimately recurs across different
-- memory_id values (each real memory's mention needs its own row).

create unique index if not exists idx_unresolved_entities_audit_dedup
  on public.unresolved_entities (tenant_id, mention_text, candidate_entity_id)
  where status = 'pending' and memory_id is null and candidate_entity_id is not null;
