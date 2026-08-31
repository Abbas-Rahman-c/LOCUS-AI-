-- Adds 'monday' to every source CHECK constraint at once, same lesson
-- from Jira/Confluence/Discord/GitHub: sweep all three tables together
-- rather than finding the second and third one live, one at a time.

alter table public.source_connections drop constraint if exists source_connections_source_check;
alter table public.source_connections add constraint source_connections_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text, 'github'::text, 'monday'::text]));

alter table public.raw_events drop constraint if exists raw_events_source_check;
alter table public.raw_events add constraint raw_events_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text, 'github'::text, 'monday'::text]));

alter table public.capture_source_rules drop constraint if exists capture_source_rules_source_check;
alter table public.capture_source_rules add constraint capture_source_rules_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text, 'github'::text, 'monday'::text]));

-- Actor identifier column for resolveActorId - a Monday.com user's numeric
-- account id (item creator / update author), same shape as
-- github_user_id/discord_user_id/atlassian_account_id.
alter table public.actors add column if not exists monday_user_id text;
