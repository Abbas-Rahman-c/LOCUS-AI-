-- Same cadence and header shape as every other poller cron job here.
select cron.schedule(
  'github-poller-every-5-min',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := 'https://imazdfzxinltbgktrgmv.supabase.co/functions/v1/github-poller',
    headers := '{"Content-Type": "application/json"}'::jsonb
  );
  $$
);
