-- =====================================================================
-- Migration 021: Add user prompt limits table
-- Purpose: Track weekly rolling window for Claude prompt usage per entity
-- =====================================================================

-- Create user_limits table for tracking per-entity prompt limits
CREATE TABLE IF NOT EXISTS public.user_limits (
    limit_key TEXT,
    limit_type TEXT DEFAULT 'claude_weekly_prompts',
    window_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    prompt_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (limit_key, limit_type)
);

-- Add comment to document the table's purpose
COMMENT ON TABLE public.user_limits IS 'Tracks per-entity rate limits for expensive operations like Claude API calls. Uses a rolling weekly window for claude_weekly_prompts limit type. The limit_key can be email, user_id, organization_id, or other identifier depending on the rate limiting scope.';

-- Add index for efficient lookups by limit_key
CREATE INDEX IF NOT EXISTS idx_user_limits_limit_key ON public.user_limits(limit_key);

-- Add index for window-based queries (for cleanup and reset operations)
CREATE INDEX IF NOT EXISTS idx_user_limits_window_start ON public.user_limits(window_start);
