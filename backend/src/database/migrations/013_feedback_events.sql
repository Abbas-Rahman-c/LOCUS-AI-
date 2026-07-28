-- =====================================================================
-- Migration 013: Feedback Events
-- Creates feedback_events, the table modules/feedback/service.py has
-- always written to. It never existed under the current (post-app-schema)
-- design — migration 002's app.feedback is a different, legacy table in
-- the app schema, dropped in 006/006c. Because store_feedback() swallows
-- write errors and always returns success to the caller (by design, so a
-- DB hiccup never blocks the user from rating an answer), this gap was
-- silent: /feedback returned 200 while discarding every submission.
-- =====================================================================

CREATE TABLE IF NOT EXISTS feedback_events (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query              TEXT NOT NULL,
    synthesized_answer TEXT NOT NULL,
    signal             TEXT NOT NULL CHECK (signal IN ('up', 'down')),
    comment            TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_events_tenant_time
    ON feedback_events (tenant_id, created_at DESC);

ALTER TABLE feedback_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_feedback_events ON feedback_events;
CREATE POLICY tenant_isolation_feedback_events ON feedback_events
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
