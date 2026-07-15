-- Gmail OAuth tokens are referenced by source_connections.oauth_token_ref,
-- whose authoritative schema type is TEXT.  Keep the token key TEXT as well
-- so connector queries never rely on UUID-to-text casts.
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id            TEXT PRIMARY KEY,
    access_token  TEXT NOT NULL,
    refresh_token TEXT,
    expires_at    TIMESTAMPTZ,
    scopes        TEXT[] NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
