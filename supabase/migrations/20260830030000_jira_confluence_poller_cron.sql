-- Registers the recurring Jira and Confluence pollers on pg_cron, same
-- shape as notion-poller-every-5-min (verified live against the real
-- cron.job row before writing this - no Authorization header needed,
-- since jira-poller/confluence-poller both have verify_jwt disabled at
-- the platform gateway level, same as every other poller/oauth function
-- in this project).

select cron.schedule(
  'jira-poller-every-5-min',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := 'https://imazdfzxinltbgktrgmv.supabase.co/functions/v1/jira-poller',
    headers := '{"Content-Type": "application/json"}'::jsonb
  );
  $$
);

select cron.schedule(
  'confluence-poller-every-5-min',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := 'https://imazdfzxinltbgktrgmv.supabase.co/functions/v1/confluence-poller',
    headers := '{"Content-Type": "application/json"}'::jsonb
  );
  $$
);
