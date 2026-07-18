-- Migration 009: Add search_decisions_fts function for the MCP edge function

CREATE OR REPLACE FUNCTION search_decisions_fts(
    p_query text,
    p_tenant_id uuid,
    p_limit int DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    tenant_id UUID,
    record_type TEXT,
    decision_statement TEXT,
    rationale TEXT,
    status TEXT,
    scope TEXT,
    confidence NUMERIC,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    rank REAL
)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT id, tenant_id, record_type, decision_statement, rationale,
           status, scope, confidence, created_at, updated_at,
           ts_rank(
               to_tsvector('english', decision_statement || ' ' || COALESCE(rationale, '')),
               plainto_tsquery('english', p_query)
           ) AS rank
    FROM decisions
    WHERE tenant_id = p_tenant_id
      AND to_tsvector('english', decision_statement || ' ' || COALESCE(rationale, ''))
          @@ plainto_tsquery('english', p_query)
    ORDER BY rank DESC, created_at DESC
    LIMIT p_limit;
$$;
