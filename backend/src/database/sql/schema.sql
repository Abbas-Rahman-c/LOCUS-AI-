-- Core schema: workspaces, memberships, sources, captures, decisions, feedback
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Workspaces table
CREATE TABLE IF NOT EXISTS public.workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sources table (integrations)
CREATE TABLE IF NOT EXISTS public.sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES public.workspaces(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL, -- 'gmail', 'slack', 'notion'
    status TEXT NOT NULL DEFAULT 'active',
    config JSONB NOT NULL DEFAULT '{}',
    watch_expiry TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- OAuth Tokens table
CREATE TABLE IF NOT EXISTS public.oauth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES public.sources(id) ON DELETE CASCADE UNIQUE,
    access_token TEXT NOT NULL, -- AES-GCM Encrypted
    refresh_token TEXT,          -- AES-GCM Encrypted
    expires_at TIMESTAMPTZ,
    scopes TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Raw Events table (for encrypted storage of incoming payloads)
CREATE TABLE IF NOT EXISTS public.raw_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES public.workspaces(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    payload BYTEA NOT NULL, -- AES-GCM Encrypted raw event payload
    created_at TIMESTAMPTZ DEFAULT NOW()
);
