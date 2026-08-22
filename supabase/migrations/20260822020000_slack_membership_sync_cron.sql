-- Registers the recurring Slack channel-membership sync on pg_cron -
-- deliberately NOT a one-time job. slack-membership-sync (the paired Edge
-- Function) fails closed if this never runs again after its first pass,
-- reproducing the exact staleness problem the memory layer's permission
-- model exists to avoid, so this has to actually keep firing.
--
-- Every 4 hours: frequent enough that a channel membership change (someone
-- added/removed) shows up same-day, without hammering Slack's rate limits
-- across every connected tenant on every run.
--
-- slack-membership-sync requires the service_role key (requireServiceRole)
-- because it writes real access-control data - net.http_post needs that
-- key in its Authorization header. It is NOT inlined here as plaintext;
-- it's read from Supabase Vault at call time via vault.decrypted_secrets.
-- The secret itself ('slack_membership_sync_service_key') must be created
-- once, out of band, e.g.:
--   select vault.create_secret('<service-role-key>', 'slack_membership_sync_service_key');
-- This migration only wires the cron job to look it up - it never contains
-- the key value itself.

select cron.schedule(
  'slack-membership-sync-every-4h',
  '0 */4 * * *',
  $$
  select net.http_post(
    url := 'https://imazdfzxinltbgktrgmv.supabase.co/functions/v1/slack-membership-sync',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'slack_membership_sync_service_key')
    ),
    body := '{}'::jsonb
  );
  $$
);
