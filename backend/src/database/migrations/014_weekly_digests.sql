-- =====================================================================
-- Migration 014: Weekly digests (Team Pulse persistence)
-- Monday cron generates digests; GET /digest serves the stored row when
-- present so delivery is passive (no user-triggered regeneration).
-- =====================================================================

CREATE TABLE IF NOT EXISTS weekly_digests (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    -- NULL for scope='team'; set to the member's auth user id for 'personal'
    user_id       UUID NULL,
    scope         TEXT NOT NULL CHECK (scope IN ('personal', 'team')),
    -- Monday (UTC) that identifies this digest week (job delivery day)
    week_of       DATE NOT NULL,
    period_start  DATE NOT NULL,
    period_end    DATE NOT NULL,
    summary       TEXT NOT NULL,
    items         JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT weekly_digests_team_user_null CHECK (
        (scope = 'team' AND user_id IS NULL)
        OR (scope = 'personal' AND user_id IS NOT NULL)
    )
);

-- One team digest per tenant per week
CREATE UNIQUE INDEX IF NOT EXISTS weekly_digests_team_week_uniq
    ON weekly_digests (tenant_id, week_of)
    WHERE scope = 'team';

-- One personal digest per member per week
CREATE UNIQUE INDEX IF NOT EXISTS weekly_digests_personal_week_uniq
    ON weekly_digests (tenant_id, user_id, week_of)
    WHERE scope = 'personal';

CREATE INDEX IF NOT EXISTS idx_weekly_digests_tenant_week
    ON weekly_digests (tenant_id, week_of DESC);

ALTER TABLE weekly_digests ENABLE ROW LEVEL SECURITY;
ALTER TABLE weekly_digests FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_weekly_digests ON weekly_digests;
CREATE POLICY tenant_isolation_weekly_digests ON weekly_digests
    USING (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid);
