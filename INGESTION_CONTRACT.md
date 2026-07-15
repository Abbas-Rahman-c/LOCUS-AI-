# Ingestion Queue Contract

**Read this before writing any connector's queue call.**

## The correct pattern

Every connector enqueues a shaped event by calling:

```python
from queue.pgmq.producer import enqueue_event

await enqueue_event(envelope)
```

This calls into `queue/pgmq/client.py`, the single pgmq connection point in the
codebase, which sends the message onto Supabase's `ingestion` (pgmq).

## What NOT to do

- **Do not** push events to Upstash Redis, or any Redis instance. Redis was part
  of the *original* (non-refined) sprint plan, before the team standardized on
  Supabase end to end. It is no longer part of this architecture.
- **Do not** call a function named `ingestEvent()`. That name is a holdover from
  the same original plan. The canonical function is `enqueue_event()`, above.
- **Do not** instantiate a separate pgmq/database connection inside a connector
  module. Always import the shared client.

## Why this matters

Dedup, raw storage, and the AI pipeline all read from the Supabase `ingestion` queue.
An event that lands anywhere else — Redis included — is invisible to the
rest of the system, even if the connector itself is working perfectly.

## Open item: runtime

The team has decided connector and business logic will run as Supabase Edge
Functions (Deno/TypeScript). This repository is currently scaffolded in Python
(FastAPI, `backend/src/...`), including the `enqueue_event()` pattern documented
above. That mismatch is not yet resolved — needs a team decision on whether this
scaffold is ported to Edge Functions or the runtime choice is revisited. Until
that's settled, treat the *queue contract* above (call the shared enqueue
function, target Supabase pgmq, never Redis) as fixed regardless of which
runtime it ends up implemented in.
