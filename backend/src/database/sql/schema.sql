-- Core schema: tenants, source connections, captures, decisions, feedback
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Workspaces table
CREATE TABLE IF NOT EXISTS public.workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Integration connection contract.  OAuth material is referenced, never embedded.
CREATE TABLE IF NOT EXISTS public.source_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES public.workspaces(id) ON DELETE CASCADE NOT NULL,
    source TEXT NOT NULL, -- 'gmail', 'slack', 'notion'
    external_workspace_id TEXT NOT NULL,
    oauth_token_ref UUID,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}',
    watch_expiry TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, source, external_workspace_id)
);

-- OAuth Tokens table
CREATE TABLE IF NOT EXISTS public.oauth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    access_token TEXT NOT NULL, -- AES-GCM Encrypted
    refresh_token TEXT,          -- AES-GCM Encrypted
    expires_at TIMESTAMPTZ,
    scopes TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.source_connections
    ADD CONSTRAINT source_connections_oauth_token_ref_fkey
    FOREIGN KEY (oauth_token_ref) REFERENCES public.oauth_tokens(id) ON DELETE SET NULL;

-- Raw Events table (for encrypted storage of incoming payloads)
CREATE TABLE IF NOT EXISTS public.raw_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES public.workspaces(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    payload BYTEA NOT NULL, -- AES-GCM Encrypted raw event payload
    created_at TIMESTAMPTZ DEFAULT NOW()
);
