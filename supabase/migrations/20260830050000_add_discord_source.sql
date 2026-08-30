-- Adds 'discord' to every source CHECK constraint at once - learned from
-- the Jira/Confluence rollout, where source_connections, raw_events, and
-- capture_source_rules each needed the same widening separately and two
-- of the three were only found live, one at a time, via real ingestion
-- failures. All three swept and fixed together this time.

alter table public.source_connections drop constraint if exists source_connections_source_check;
alter table public.source_connections add constraint source_connections_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text]));

alter table public.raw_events drop constraint if exists raw_events_source_check;
alter table public.raw_events add constraint raw_events_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text]));

alter table public.capture_source_rules drop constraint if exists capture_source_rules_source_check;
alter table public.capture_source_rules add constraint capture_source_rules_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text]));

-- Actor identifier column for resolveActorId, same shape as
-- atlassian_account_id - Discord's own real per-user id.
alter table public.actors add column if not exists discord_user_id text;
