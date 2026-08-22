-- memory_resolutions.action's check constraint only covered conflict-review
-- actions (confirm_current/mark_superseded/mark_contradicted/dismiss_conflict)
-- from Batch 1's schema design - written before the Attention strip's four
-- resolution types (spec Section 10: "Resolve / Confirm / Check in /
-- Recheck") existed. Extending rather than reusing a mismatched existing
-- value, so the audit log records what a human actually did, not a
-- same-ish-sounding label from a different feature.

alter table public.memory_resolutions drop constraint if exists memory_resolutions_action_check;
alter table public.memory_resolutions add constraint memory_resolutions_action_check
  check (action in (
    'confirm_current', 'mark_superseded', 'mark_contradicted', 'dismiss_conflict',
    'confirm_decision', 'check_in_commitment', 'recheck_freshness'
  ));
