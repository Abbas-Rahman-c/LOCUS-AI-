-- =====================================================================
-- Migration 008: Radar Corrections
-- Creates radar_corrections table to capture every confirm/edit/reject
-- action as a distinct, queryable training signal for future prompt
-- versions. Corrections are NEVER just silent in-place overwrites —
-- each action produces a permanent record of what was corrected and to what.
-- =====================================================================

CREATE TABLE IF NOT EXISTS radar_corrections (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    decision_id           UUID NOT NULL,
    action                TEXT NOT NULL CHECK (action IN ('confirmed', 'edited', 'rejected')),
    original_statement    TEXT NOT NULL,           -- always captured for auditability
    corrected_statement   TEXT,                    -- set for 'edited' actions only
    original_status       TEXT NOT NULL,           -- status before this correction
    note                  TEXT,                    -- optional free-text from the user
    corrected_by_actor_id UUID,                    -- actor who made the correction (if known)
    corrected_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Belt-and-suspenders: composite FK enforces tenant scope at the DB level
    CONSTRAINT fk_radar_corrections_decision
        FOREIGN KEY (decision_id, tenant_id)
        REFERENCES decisions(id, tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_radar_corrections_decision
    ON radar_corrections (decision_id);
CREATE INDEX IF NOT EXISTS idx_radar_corrections_tenant_time
    ON radar_corrections (tenant_id, corrected_at DESC);

ALTER TABLE radar_corrections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_radar_corrections ON radar_corrections;
CREATE POLICY tenant_isolation_radar_corrections ON radar_corrections
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
