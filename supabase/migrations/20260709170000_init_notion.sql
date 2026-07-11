CREATE TABLE IF NOT EXISTS public.sources (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id text NOT NULL,
    source_type text NOT NULL,
    credentials jsonb,
    last_poll_time timestamptz,
    status text DEFAULT 'active',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- RPC for edge functions to enqueue into pgmq ingestion queue
CREATE OR REPLACE FUNCTION enqueue_ingestion_event(envelope jsonb)
RETURNS setof bigint
LANGUAGE sql
SECURITY DEFINER
AS $$
  -- We assume `pgmq` extension is installed and `ingestion` queue exists
  SELECT pgmq.send('ingestion', envelope);
$$;
