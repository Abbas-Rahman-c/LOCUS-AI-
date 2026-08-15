-- =====================================================================
-- Migration 021: Add user prompt limits table
-- Purpose: Track weekly rolling window for Claude prompt usage per user
-- =====================================================================

-- Create user_limits table for tracking per-user prompt limits
CREATE TABLE IF NOT EXISTS public.user_limits (
    email TEXT,
    limit_type TEXT DEFAULT 'claude_weekly_prompts',
    window_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    prompt_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (email, limit_type)
);

-- Add comment to document the table's purpose
COMMENT ON TABLE public.user_limits IS 'Tracks per-user rate limits for expensive operations like Claude API calls. Uses a rolling weekly window for claude_weekly_prompts limit type.';

-- Add index for efficient lookups by email
CREATE INDEX IF NOT EXISTS idx_user_limits_email ON public.user_limits(email);

-- Add index for window-based queries (for cleanup and reset operations)
CREATE INDEX IF NOT EXISTS idx_user_limits_window_start ON public.user_limits(window_start);
