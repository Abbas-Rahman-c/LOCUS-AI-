-- Real bug found live: 20260830010000 widened
-- source_connections_source_check to allow 'jira'/'confluence', but
-- missed two other tables with their own, separate source CHECK
-- constraints - raw_events and capture_source_rules. Confirmed live: a
-- real Jira poll's ingestion messages all failed with "new row for
-- relation raw_events violates check constraint raw_events_source_check"
-- (deleted, not retried, per handleIngestionMessage's own error-handling
-- convention) before ever reaching triage. Found the second one
-- (capture_source_rules) by sweeping every constraint referencing the
-- old 3-source list at once, not by waiting to hit it separately later.

alter table public.raw_events drop constraint if exists raw_events_source_check;
alter table public.raw_events add constraint raw_events_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text]));

alter table public.capture_source_rules drop constraint if exists capture_source_rules_source_check;
alter table public.capture_source_rules add constraint capture_source_rules_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text]));
