-- Adds 'outlook_calendar' to every source CHECK constraint at once, same
-- lesson from every connector before it: sweep all three tables together.

alter table public.source_connections drop constraint if exists source_connections_source_check;
alter table public.source_connections add constraint source_connections_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text, 'github'::text, 'monday'::text, 'clickup'::text, 'outlook_calendar'::text]));

alter table public.raw_events drop constraint if exists raw_events_source_check;
alter table public.raw_events add constraint raw_events_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text, 'github'::text, 'monday'::text, 'clickup'::text, 'outlook_calendar'::text]));

alter table public.capture_source_rules drop constraint if exists capture_source_rules_source_check;
alter table public.capture_source_rules add constraint capture_source_rules_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text, 'discord'::text, 'github'::text, 'monday'::text, 'clickup'::text, 'outlook_calendar'::text]));

-- Actor identifier column for resolveActorId - a Microsoft account's
-- email/UPN, reusing the "email" column shape rather than adding a new
-- one: Microsoft attendee/organizer identity is already an email
-- address, the exact same identifier space actors.email already
-- indexes for Gmail. No new column needed.
