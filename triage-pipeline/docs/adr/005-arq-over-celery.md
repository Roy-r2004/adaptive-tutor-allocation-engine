# ADR 005 — Arq for async workers


## Context

The triage pipeline does most of its work in worker processes —
classification, enrichment, summarization, persistence. The webhook
returns 202 Accepted in milliseconds; the heavy lifting happens
behind a queue. We need a queue + worker library.

Three real options for Python in 2026:
1. **Celery** — the default, decades old.
2. **Arq** — async-native, Redis-backed, lightweight.
3. **Dramatiq** — middle ground.

## Decision

**Arq.**

## Why

The deciding factor is **async-native execution.**

Our handlers call:
- `httpx.AsyncClient` for LiteLLM provider calls
- `asyncpg`/SQLAlchemy 2.0 async for DB
- `langgraph.ainvoke()` for the graph

Celery's prefork model forces every task to be a sync function. To
call our async stack from a Celery task we'd have to do
`asyncio.run(...)` per task, which:
- creates a fresh event loop per call (slow)
- breaks shared httpx clients ("Future attached to a different loop")
- can't share asyncpg connection pools

Arq runs the worker in a single asyncio loop and dispatches coroutine
tasks directly. Our `triage_message` task is `async def`, awaited
natively.

Other Arq wins:
- **Tiny dependency surface.** Arq is essentially "Redis + asyncio +
  pydantic." No transports, no result backends.
- **Built-in deduplication via `_job_id`.** We pass
  `_job_id=f"triage:{ticket_id}"` to enqueue, so retried webhooks
  collapse to one job.
- **Built-in cron and delayed jobs.** Phase 2's SLA breach watcher
  drops in here.

## What we lose vs. Celery

- Celery's mature monitoring (Flower) — we use Prometheus + Grafana
  instead.
- Celery's broker abstraction (Redis, RabbitMQ, SQS, etc.) — we lock
  to Redis. Acceptable for our scale; SQS would be a Phase 2 swap.
- Celery's task-result backend — Arq has one, we don't use it
  (results live in Postgres `tickets` rows instead).

## Tradeoffs

- Arq is Redis-only. If we needed a managed broker (SQS, etc.)
  Celery wins.
- Smaller community than Celery. Documentation is thinner. Mitigated
  by the small surface area.

## Consequences

- `pyproject.toml` depends on `arq` and `redis`.
- `src/app/workers/queue.py` is the entry point. The
  `WorkerSettings` class is what Arq's CLI looks for:
  ```bash
  arq app.workers.queue.WorkerSettings
  ```
- The `worker` service in `docker-compose.yml` runs that command.
- Job IDs are deterministic: `triage:{ticket_id}` and
  `resume:{escalation_id}`. Idempotent on retry.
