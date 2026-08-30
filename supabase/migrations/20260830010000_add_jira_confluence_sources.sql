-- Adds 'jira' and 'confluence' as valid public.source_connections.source
-- values. Both connectors share one Atlassian OAuth 2.0 (3LO) app
-- (ATLASSIAN_CLIENT_ID/ATLASSIAN_CLIENT_SECRET) but write two separate
-- source_connections rows - one per product - matching this table's
-- existing one-row-per-product convention (a tenant connecting both gets
-- two rows, same as if Slack and Gmail were two unrelated apps).

alter table public.source_connections drop constraint if exists source_connections_source_check;
alter table public.source_connections add constraint source_connections_source_check
  check (source = any (array['slack'::text, 'gmail'::text, 'notion'::text, 'jira'::text, 'confluence'::text]));
