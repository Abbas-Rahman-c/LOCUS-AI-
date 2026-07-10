-- Fallback schema for PGMQ in environments where the extension is not pre-installed.
CREATE SCHEMA IF NOT EXISTS pgmq;

CREATE TABLE IF NOT EXISTS pgmq.messages (
    msg_id BIGSERIAL PRIMARY KEY,
    queue_name TEXT NOT NULL,
    message JSONB NOT NULL,
    read_ct INT DEFAULT 0,
    vt TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION pgmq.create(queue TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION pgmq.send(queue TEXT, msg JSONB)
RETURNS BIGINT AS $$
DECLARE
    new_id BIGINT;
BEGIN
    INSERT INTO pgmq.messages (queue_name, message)
    VALUES (queue, msg)
    RETURNING msg_id INTO new_id;
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION pgmq.read(queue TEXT, vt_sec INT, qty INT)
RETURNS TABLE (
    msg_id BIGINT,
    read_ct INT,
    enqueued_at TIMESTAMPTZ,
    vt TIMESTAMPTZ,
    message JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH target_messages AS (
        SELECT m.msg_id
        FROM pgmq.messages m
        WHERE m.queue_name = queue
          AND m.vt <= NOW()
        ORDER BY m.msg_id ASC
        LIMIT qty
        FOR UPDATE SKIP LOCKED
    )
    UPDATE pgmq.messages m
    SET vt = NOW() + (vt_sec || ' seconds')::INTERVAL,
        read_ct = m.read_ct + 1
    FROM target_messages t
    WHERE m.msg_id = t.msg_id
    RETURNING m.msg_id, m.read_ct, m.created_at, m.vt, m.message;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION pgmq.delete(queue TEXT, message_id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    deleted BOOLEAN := FALSE;
BEGIN
    DELETE FROM pgmq.messages
    WHERE queue_name = queue AND msg_id = message_id;
    IF FOUND THEN
        deleted := TRUE;
    END IF;
    RETURN deleted;
END;
$$ LANGUAGE plpgsql;
