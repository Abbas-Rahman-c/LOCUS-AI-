-- Adds the actor-identifier column resolveActorId needs for Jira and
-- Confluence. One shared column, not two - a user's Atlassian accountId
-- is the same identity across every product on one site (Jira and
-- Confluence included), unlike Slack/Notion's per-product ids.
--
-- No unique constraint, matching the existing slack_user_id/notion_user_id
-- columns exactly (only actors.email has one) - resolveActorId's
-- SELECT-then-INSERT for those two is already racy by the same amount;
-- not something this migration changes or improves, just matching the
-- precedent it's extending.

alter table public.actors add column if not exists atlassian_account_id text;
