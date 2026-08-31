-- Same cadence and header shape as every other poller cron job here.
select cron.schedule(
  'clickup-poller-every-5-min',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := 'https://imazdfzxinltbgktrgmv.supabase.co/functions/v1/clickup-poller',
    headers := '{"Content-Type": "application/json"}'::jsonb
  );
  $$
);
