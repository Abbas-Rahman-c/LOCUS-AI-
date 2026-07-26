-- =====================================================================
-- Migration 012: Add updated_at to tenants table
-- Purpose: Track when tenant billing/subscription state last changed
-- =====================================================================

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();