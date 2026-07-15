
-- RPC for edge functions to enqueue into pgmq ingestion queue
CREATE OR REPLACE FUNCTION enqueue_ingestion_event(envelope jsonb)
RETURNS setof bigint
LANGUAGE sql
SECURITY DEFINER
AS $$
  -- We assume `pgmq` extension is installed and `ingestion` queue exists
  SELECT pgmq.send('ingestion', envelope);
$$;
