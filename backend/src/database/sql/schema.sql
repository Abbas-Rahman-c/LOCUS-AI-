-- =====================================================================
-- Locus AI — Database Schema (v3.2, Production Hardened)
-- Target: Supabase Postgres 15+ with pgvector
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. TENANTS
CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    plan        TEXT NOT NULL DEFAULT 'self_serve' CHECK (plan IN ('self_serve','team')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. ACTORS
CREATE TABLE actors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    auth_user_id    UUID,
    display_name    TEXT,
    email           TEXT,
    slack_user_id   TEXT,
    notion_user_id  TEXT,
    kind            TEXT NOT NULL DEFAULT 'internal' CHECK (kind IN ('internal','external')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email),
    CONSTRAINT actors_id_tenant_id_key UNIQUE (id, tenant_id) -- Built for composite FKs
);

-- 3. SOURCE CONNECTIONS
CREATE TABLE source_connections (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source                  TEXT NOT NULL CHECK (source IN ('slack','gmail','notion')),
    external_workspace_id   TEXT,
    oauth_token_ref         TEXT NOT NULL,
    ingestion_mode          TEXT NOT NULL CHECK (ingestion_mode IN ('realtime','near_realtime','polling')),
    status                  TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','error','revoked')),
    cursor_state            JSONB NOT NULL DEFAULT '{}',
    last_synced_at          TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source, external_workspace_id)
);

-- 4. RAW_EVENTS 
CREATE TABLE raw_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    connection_id       UUID NOT NULL REFERENCES source_connections(id) ON DELETE CASCADE,
    source              TEXT NOT NULL CHECK (source IN ('slack','gmail','notion')),
    source_id           TEXT NOT NULL,
    thread_ref          TEXT,
    actor_id            UUID,
    permission_scope    TEXT[] NOT NULL DEFAULT '{}',
    raw_content         BYTEA NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}',
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 days'),
    triage_result       TEXT CHECK (triage_result IN ('pending','kept','uncertain','discarded')),
    triage_at           TIMESTAMPTZ,
    UNIQUE (tenant_id, source, source_id),
    CONSTRAINT raw_events_id_tenant_id_key UNIQUE (id, tenant_id), -- Built for composite FKs
    CONSTRAINT fk_raw_events_actor_tenant FOREIGN KEY (actor_id, tenant_id) REFERENCES actors(id, tenant_id)
);

CREATE INDEX idx_raw_events_tenant_time ON raw_events (tenant_id, received_at DESC);
CREATE INDEX idx_raw_events_thread      ON raw_events (thread_ref);
CREATE INDEX idx_raw_events_expiry      ON raw_events (expires_at);
CREATE INDEX idx_raw_events_metadata    ON raw_events USING GIN (metadata);
CREATE INDEX idx_raw_events_triage      ON raw_events (triage_result) WHERE triage_result = 'discarded';

-- 5. DECISIONS
CREATE TABLE decisions (
    id                      UUID DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    record_type             TEXT NOT NULL DEFAULT 'decision' CHECK (record_type IN ('decision','action_item','blocker')),
    decision_statement      TEXT NOT NULL,
    rationale               TEXT,
    alternatives_considered TEXT[] NOT NULL DEFAULT '{}',
    status                  TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','decided','superseded')),
    superseded_by           UUID,
    scope                   TEXT NOT NULL DEFAULT 'team' CHECK (scope IN ('user','team')),
    scope_actor_id          UUID,
    confidence              NUMERIC(4,3) NOT NULL,
    permission_scope        TEXT[] NOT NULL DEFAULT '{}',
    origin_raw_event_id     UUID,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT decisions_id_tenant_id_key UNIQUE (id, tenant_id),
    -- Hardened Cross-Tenant Cross References:
    CONSTRAINT fk_decisions_superseded_tenant FOREIGN KEY (superseded_by, tenant_id) REFERENCES decisions(id, tenant_id),
    CONSTRAINT fk_decisions_actor_tenant FOREIGN KEY (scope_actor_id, tenant_id) REFERENCES actors(id, tenant_id),
    CONSTRAINT fk_decisions_origin_event_tenant FOREIGN KEY (origin_raw_event_id, tenant_id) REFERENCES raw_events(id, tenant_id)
);

CREATE INDEX idx_decisions_tenant_status ON decisions (tenant_id, status);
CREATE INDEX idx_decisions_scope         ON decisions (tenant_id, scope, scope_actor_id);
CREATE INDEX idx_decisions_fts           ON decisions USING GIN (to_tsvector('english', decision_statement || ' ' || coalesce(rationale, '')));

-- 6. DECISION_ACTORS
CREATE TABLE decision_actors (
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    decision_id UUID NOT NULL,
    actor_id    UUID NOT NULL,
    role        TEXT NOT NULL DEFAULT 'decided_by' CHECK (role IN ('decided_by','mentioned')),
    PRIMARY KEY (decision_id, actor_id, role),
    CONSTRAINT fk_decision_actors_tenant FOREIGN KEY (decision_id, tenant_id) REFERENCES decisions(id, tenant_id) ON DELETE CASCADE,
    CONSTRAINT fk_decision_actors_actor FOREIGN KEY (actor_id, tenant_id) REFERENCES actors(id, tenant_id) ON DELETE CASCADE
);
CREATE INDEX idx_decision_actors_tenant ON decision_actors (tenant_id);

-- 7. DECISION_SOURCES
CREATE TABLE decision_sources (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    decision_id   UUID NOT NULL,
    raw_event_id  UUID,
    permalink     TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (decision_id, permalink),
    CONSTRAINT fk_decision_sources_tenant FOREIGN KEY (decision_id, tenant_id) REFERENCES decisions(id, tenant_id) ON DELETE CASCADE,
    CONSTRAINT fk_decision_sources_event FOREIGN KEY (raw_event_id, tenant_id) REFERENCES raw_events(id, tenant_id) ON DELETE SET NULL
);
CREATE INDEX idx_decision_sources_decision ON decision_sources (decision_id);
CREATE INDEX idx_decision_sources_tenant   ON decision_sources (tenant_id);

-- 8. DECISION_EMBEDDINGS
CREATE TABLE decision_embeddings (
    decision_id     UUID PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    embedding       VECTOR(1536) NOT NULL,
    embedding_model TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    embedded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_decision_embeddings_tenant FOREIGN KEY (decision_id, tenant_id) REFERENCES decisions(id, tenant_id) ON DELETE CASCADE
);
CREATE INDEX idx_decision_embeddings_vec    ON decision_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_decision_embeddings_tenant ON decision_embeddings (tenant_id);

-- 9. MCP_TOOL_CALLS
CREATE TABLE mcp_tool_calls (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    requesting_client   TEXT NOT NULL,
    tool_name           TEXT NOT NULL,
    request_params      JSONB NOT NULL,
    result_decision_ids UUID[],
    latency_ms          INT,
    called_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mcp_tool_calls_tenant_time ON mcp_tool_calls (tenant_id, called_at DESC);

-- =====================================================================
-- ROW-LEVEL SECURITY
-- =====================================================================
ALTER TABLE actors              ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_connections  ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_events          ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_actors      ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_sources    ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_tool_calls      ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_actors ON actors
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_source_connections ON source_connections
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_raw_events ON raw_events
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_decisions ON decisions
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_decision_actors ON decision_actors
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_decision_sources ON decision_sources
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_decision_embeddings ON decision_embeddings
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_mcp_tool_calls ON mcp_tool_calls
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- =====================================================================
-- AUTOMATIC MODIFICATION TIME TRIGGER
-- =====================================================================
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_decisions_modtime
    BEFORE UPDATE ON decisions
    FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

-- =====================================================================
-- EVALUATION DATA (FEEDBACK LOOP)
-- =====================================================================
CREATE TABLE feedback_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query               TEXT NOT NULL,
    synthesized_answer  TEXT NOT NULL,
    signal              TEXT NOT NULL CHECK (signal IN ('up', 'down')),
    comment             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE feedback_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_feedback_events ON feedback_events
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);