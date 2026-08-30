-- Real bug found live: Settings > Build Memory's "Pause all learning" and
-- "Core knowledge only" controls were both pure local React useState -
-- no database column, no API call, ai-worker had no way to know either
-- setting existed. Clicking them just changed which button looked
-- selected, with zero actual effect. This is the real backend for both.
--
-- learning_paused: checked first thing in ai-worker's ingestion handler -
-- a paused tenant's events are marked done and deleted from the queue
-- without ever calling Claude. Real $0 skip, not a display-only filter -
-- matches the UI's own copy ("Temporarily stop Locus AI from reading new
-- messages. All existing memory is preserved and search remains
-- available.").
--
-- core_knowledge_only: checked after extraction - an action_item/blocker
-- classification is discarded (never persisted to decisions) when set.
-- Does NOT reduce the triage+extraction call's own token cost (the same
-- call still runs) - this matches the UI's own stated intent ("Only
-- learn explicit conclusions and agreements. Lower volume, higher
-- precision.") which is about reducing captured VOLUME/noise, not API
-- spend. Worth being precise about since those are two different things.

alter table public.tenants add column if not exists learning_paused boolean not null default false;
alter table public.tenants add column if not exists core_knowledge_only boolean not null default false;
