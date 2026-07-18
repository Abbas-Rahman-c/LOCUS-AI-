-- =====================================================================
-- Tenant isolation row-level security
-- Mirrors backend/src/database/rls/policies.sql (keep in sync)
-- Idempotent: safe to re-run.
-- =====================================================================

-- ---------------------------------------------------------------------
-- ENABLE + FORCE on tenant-scoped tables
-- ---------------------------------------------------------------------
alter table public.tenants             enable row level security;
alter table public.memberships         enable row level security;
alter table public.actors              enable row level security;
alter table public.source_connections  enable row level security;
alter table public.raw_events          enable row level security;
alter table public.decisions           enable row level security;
alter table public.decision_actors     enable row level security;
alter table public.decision_sources    enable row level security;
alter table public.decision_embeddings enable row level security;
alter table public.mcp_tool_calls      enable row level security;

alter table public.tenants             force row level security;
alter table public.memberships         force row level security;
alter table public.actors              force row level security;
alter table public.source_connections  force row level security;
alter table public.raw_events          force row level security;
alter table public.decisions           force row level security;
alter table public.decision_actors     force row level security;
alter table public.decision_sources    force row level security;
alter table public.decision_embeddings force row level security;
alter table public.mcp_tool_calls      force row level security;

-- ---------------------------------------------------------------------
-- Auth helpers: tenants / memberships (membership-based SELECT)
-- ---------------------------------------------------------------------
drop policy if exists memberships_select_own on public.memberships;
create policy memberships_select_own on public.memberships
  for select
  to authenticated
  using (user_id = auth.uid());

drop policy if exists tenants_select_member on public.tenants;
create policy tenants_select_member on public.tenants
  for select
  to authenticated
  using (
    id in (select m.tenant_id from public.memberships m where m.user_id = auth.uid())
  );

-- ---------------------------------------------------------------------
-- GUC policies (workers / non-bypass app role)
-- ---------------------------------------------------------------------
drop policy if exists tenant_isolation_actors on public.actors;
create policy tenant_isolation_actors on public.actors
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_source_connections on public.source_connections;
create policy tenant_isolation_source_connections on public.source_connections
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_raw_events on public.raw_events;
create policy tenant_isolation_raw_events on public.raw_events
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_decisions on public.decisions;
create policy tenant_isolation_decisions on public.decisions
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_decision_actors on public.decision_actors;
create policy tenant_isolation_decision_actors on public.decision_actors
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_decision_sources on public.decision_sources;
create policy tenant_isolation_decision_sources on public.decision_sources
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_decision_embeddings on public.decision_embeddings;
create policy tenant_isolation_decision_embeddings on public.decision_embeddings
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

drop policy if exists tenant_isolation_mcp_tool_calls on public.mcp_tool_calls;
create policy tenant_isolation_mcp_tool_calls on public.mcp_tool_calls
  using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);

-- ---------------------------------------------------------------------
-- authenticated companion policies (PostgREST / browser JWT)
-- ---------------------------------------------------------------------
drop policy if exists tenant_isolation_actors_authenticated on public.actors;
create policy tenant_isolation_actors_authenticated on public.actors
  for all
  to authenticated
  using (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  )
  with check (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  );

drop policy if exists tenant_isolation_source_connections_authenticated on public.source_connections;
create policy tenant_isolation_source_connections_authenticated on public.source_connections
  for all
  to authenticated
  using (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  )
  with check (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  );

drop policy if exists tenant_isolation_raw_events_authenticated on public.raw_events;
create policy tenant_isolation_raw_events_authenticated on public.raw_events
  for all
  to authenticated
  using (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  )
  with check (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  );

drop policy if exists tenant_isolation_decisions_authenticated on public.decisions;
create policy tenant_isolation_decisions_authenticated on public.decisions
  for all
  to authenticated
  using (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  )
  with check (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  );

drop policy if exists tenant_isolation_decision_actors_authenticated on public.decision_actors;
create policy tenant_isolation_decision_actors_authenticated on public.decision_actors
  for all
  to authenticated
  using (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  )
  with check (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  );

drop policy if exists tenant_isolation_decision_sources_authenticated on public.decision_sources;
create policy tenant_isolation_decision_sources_authenticated on public.decision_sources
  for all
  to authenticated
  using (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  )
  with check (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  );

drop policy if exists tenant_isolation_decision_embeddings_authenticated on public.decision_embeddings;
create policy tenant_isolation_decision_embeddings_authenticated on public.decision_embeddings
  for all
  to authenticated
  using (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  )
  with check (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  );

drop policy if exists tenant_isolation_mcp_tool_calls_authenticated on public.mcp_tool_calls;
create policy tenant_isolation_mcp_tool_calls_authenticated on public.mcp_tool_calls
  for all
  to authenticated
  using (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  )
  with check (
    tenant_id in (
      select m.tenant_id from public.memberships m where m.user_id = auth.uid()
    )
  );

-- ---------------------------------------------------------------------
-- Optional: feedback_events (present in schema.sql; may not exist on all envs)
-- ---------------------------------------------------------------------
do $$
begin
  if to_regclass('public.feedback_events') is null then
    return;
  end if;

  execute 'alter table public.feedback_events enable row level security';
  execute 'alter table public.feedback_events force row level security';

  execute 'drop policy if exists tenant_isolation_feedback_events on public.feedback_events';
  execute $p$
    create policy tenant_isolation_feedback_events on public.feedback_events
      using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
      with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
  $p$;

  execute 'drop policy if exists tenant_isolation_feedback_events_authenticated on public.feedback_events';
  execute $p$
    create policy tenant_isolation_feedback_events_authenticated on public.feedback_events
      for all
      to authenticated
      using (
        tenant_id in (
          select m.tenant_id from public.memberships m where m.user_id = auth.uid()
        )
      )
      with check (
        tenant_id in (
          select m.tenant_id from public.memberships m where m.user_id = auth.uid()
        )
      )
  $p$;
end $$;
