-- =====================================================================
-- Migration 011: Add Stripe billing columns to tenants table
-- Purpose: Track Stripe customer, subscription, and payment state
-- =====================================================================

-- Stripe customer ID — created during first checkout
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT UNIQUE;

-- Active Stripe subscription ID
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT UNIQUE;

-- Subscription lifecycle status — mirrors Stripe's subscription.status
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS subscription_status TEXT
        NOT NULL DEFAULT 'inactive'
        CHECK (subscription_status IN (
            'inactive',       -- no subscription yet
            'active',         -- paying and current
            'past_due',       -- payment failed, grace period
            'canceled',       -- explicitly canceled
            'trialing'        -- free trial (future use)
        ));
