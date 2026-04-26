# Runbook

> Operations guide for the AI Triage Pipeline.

This document covers the typical incidents and operational tasks the
on-call engineer needs to perform. Pair it with the dashboards in
Grafana (started via `make up-obs`) and the structured logs in your
log aggregator.

---

## 1. Service map

| Service | Image / process | Port | Healthcheck |
|---|---|---|---|
| `app` | uvicorn (FastAPI) | 8000 | `GET /healthz`, `GET /readyz` |
| `worker` | arq | — | `arq` health-check ping every 30s |
| `postgres` | pgvector/pg16 | 5432 | `pg_isready` |
| `redis` | redis:7 | 6379 | `redis-cli ping` |
| `prometheus` | prom/prometheus | 9090 | `/-/healthy` |
| `grafana` | grafana | 3001 | `/api/health` |

---

## 2. Daily checks

### 2.1 Are tickets being triaged?

```sql
SELECT status, count(*) FROM tickets
WHERE created_at > now() - interval '1 hour'
GROUP BY status;
```

Healthy mix:
- `resolved` — vast majority
- `awaiting_review` — small steady number
- `received` / `classified` / `routed` — should be transient (< 30s)
- `failed` — should be ~0

If `received` is growing without moving forward, **the worker is stuck
or down.** See §4.1.

### 2.2 What's the LLM bill looking like?

```sql
SELECT
  date_trunc('day', created_at) AS day,
  provider,
  count(*) AS calls,
  sum(total_tokens) AS tokens,
  round(sum(cost_usd)::numeric, 2) AS cost_usd
FROM llm_calls
WHERE created_at > now() - interval '7 days'
GROUP BY 1, 2
ORDER BY 1 DESC, 4 DESC;
```

Sudden jump in `cost_usd` per ticket → check `provider` column. If we
fell off the primary (Groq) onto OpenAI for a sustained period, tokens
got 5–10x more expensive. See §4.2.

### 2.3 What's the escalation rate?

```sql
SELECT
  date_trunc('hour', created_at) AS hour,
  count(*) FILTER (WHERE status = 'pending') AS pending,
  count(*) FILTER (WHERE status = 'accepted') AS accepted,
  count(*) FILTER (WHERE status = 'edited') AS edited,
  count(*) FILTER (WHERE status = 'rejected') AS rejected
FROM escalations
WHERE created_at > now() - interval '24 hours'
GROUP BY 1
ORDER BY 1 DESC;
```

If `edited` is much larger than `accepted`, the model's auto-routing is
systematically wrong on a subset — investigate which categories
dominate the edits and consider a prompt iteration.

If `pending` keeps growing, reviewers aren't keeping up — check the
queue UI.

---

## 3. Common operational tasks

### 3.1 Replay a stuck ticket

If a ticket is in `failed` or stuck in `received`:

```bash
# Re-enqueue the triage job manually via redis-cli
docker compose exec redis redis-cli \
  XADD arq:queue '*' job_id triage:<TICKET_ID> ...
# Or just re-POST the original payload to /v1/webhook/ingest
```

The job_id `triage:<TICKET_ID>` is deterministic and idempotent — Arq
will not double-process if the original is still queued.

### 3.2 Clear the dead-letter queue

```bash
docker compose exec redis redis-cli LLEN arq:dlq
docker compose exec redis redis-cli LRANGE arq:dlq 0 -1 | jq
# Inspect, then drain
docker compose exec redis redis-cli DEL arq:dlq
```

### 3.3 Apply a new migration

```bash
# Generate
docker compose run --rm app alembic revision --autogenerate -m "description"
# Review the file in alembic/versions/...
# Apply
docker compose run --rm migrate
```

### 3.4 Rotate a prompt version

See `docs/prompts.md` § 7. Steps:

1. Copy template to `*_v2.j2`.
2. Bump `TEMPLATE` constant in the corresponding node.
3. PR + tests + merge.
4. The next request hits the new version. The old version's
   `prompt_versions` row stays for historical audit.

### 3.5 Resolve a stuck escalation

The escalation row exists but the graph won't resume:

```sql
-- Check the escalation
SELECT * FROM escalations WHERE id = '<ID>';
-- Check its ticket's checkpoint exists
SELECT * FROM checkpoints WHERE thread_id = '<TICKET_ID>'
ORDER BY checkpoint_id DESC LIMIT 1;
```

If the checkpoint is missing, the graph state is gone — manually mark
the escalation as `expired` and re-ingest the ticket.

---

## 4. Incident playbooks

### 4.1 "Workers are not processing jobs"

**Symptoms:** queue depth growing in Grafana, tickets stuck in
`received` for > 1 minute.

```bash
# Check worker is alive
docker compose ps worker
docker compose logs worker --tail 100

# Check it can reach Redis
docker compose exec worker redis-cli -h redis ping

# Check it can reach Postgres
docker compose exec worker python -c "
import asyncio
from app.core.db import get_engine
async def t():
    e = get_engine()
    async with e.begin() as c:
        print(await c.scalar(__import__('sqlalchemy').text('SELECT 1')))
asyncio.run(t())
"

# If hung, restart
docker compose restart worker
```

Common causes:
- Redis connection limit hit (raise `maxclients` in redis.conf).
- Asyncpg pool exhausted (raise `db_pool_size`).
- A task is wedged in `interrupt()` re-execution loop because the
  caller didn't supply `Command(resume=...)` correctly.

### 4.2 "All requests are routing to the slowest LLM provider"

**Symptoms:** `llm_latency_seconds` p50 jumps; `llm_requests_total` for
the primary provider goes to ~zero; cost per ticket spikes.

The primary (Groq) is in cooldown — LiteLLM won't try it again until
its cooldown timer expires. Check:

```sql
SELECT provider, model, outcome, error, count(*) AS n
FROM llm_calls
WHERE created_at > now() - interval '15 minutes'
GROUP BY 1, 2, 3, 4
ORDER BY n DESC;
```

If you see lots of `outcome=error` for the primary, it's down or
rate-limited. Either:

- Wait for cooldown / let upstream recover.
- Bump `LLM_PRIMARY_MODEL` to one of the fallbacks temporarily and
  redeploy.

### 4.3 "Confidence is suspiciously high on everything"

**Symptoms:** escalation rate near zero, edit rate climbs.

Almost always: the model is over-confident. Until calibration ships
(Phase 2), tighten the threshold:

```bash
# In .env, then redeploy
ESCALATION_CONFIDENCE_THRESHOLD=0.85
```

This is a one-line ops knob — not a code change.

### 4.4 "Database disk is filling up"

The `audit_log` and `llm_calls` tables grow forever in V1. Add a
periodic prune (Phase 2 — should be a cron-driven Arq task):

```sql
DELETE FROM llm_calls WHERE created_at < now() - interval '90 days';
DELETE FROM audit_log WHERE created_at < now() - interval '180 days';
VACUUM ANALYZE;
```

Resolved tickets older than the retention window can be cold-archived
to S3 / MinIO.

### 4.5 "Customer is asking why their ticket was routed wrongly"

```sql
SELECT
  t.id, t.created_at, t.handled_by, t.status,
  c.category, c.priority, c.confidence, c.rationale, c.model_used,
  r.queue, r.sla_minutes, r.decided_by, r.rationale AS routing_rationale
FROM tickets t
LEFT JOIN classifications c ON c.ticket_id = t.id
LEFT JOIN routing_decisions r ON r.ticket_id = t.id
WHERE t.id = '<TICKET_ID>';

-- Then the audit trail
SELECT created_at, actor, event, extra
FROM audit_log
WHERE ticket_id = '<TICKET_ID>'
ORDER BY created_at;

-- And the LLM calls that produced it
SELECT created_at, operation, model, prompt_tokens, completion_tokens,
       latency_ms, outcome
FROM llm_calls
WHERE ticket_id = '<TICKET_ID>'
ORDER BY created_at;
```

Together these tell the complete story: every model call, every state
transition, every human action.

---

## 5. Capacity planning

| Bottleneck | First sign | Mitigation |
|---|---|---|
| LLM rate limits | 429s in `llm_calls.error` | LiteLLM cooldown handles this. Add a second provider key or upgrade tier. |
| Postgres connections | "remaining connection slots are reserved" | Lower `db_pool_size`, add PgBouncer. |
| Redis memory | `used_memory > maxmemory * 0.8` | Add `maxmemory-policy allkeys-lru`. |
| Worker CPU | Latency p99 climbs | Add `arq` worker replicas (Arq is lock-free). |
| Postgres disk | %used > 80% | Apply pruning (§4.4) or attach larger volume. |

---

## 6. Disaster recovery

The system is designed so a complete pod loss does not lose tickets:

- **Inbound message persisted before enqueue.** Loss of an in-flight
  request → the customer sees a 5xx and retries.
- **Graph state persisted to Postgres after every super-step.** Loss
  of a worker pod → next worker picks up the same job and resumes
  from the checkpoint, not from scratch.
- **Escalations persist independently in the `escalations` table.**
  Loss of the reviewer UI → state is intact, reviewers re-authenticate
  and resume.

Backup expectations:
- Postgres: PITR continuous archive, daily snapshot.
- Redis: AOF + daily snapshot to S3 (queue is replayable from
  `messages` table anyway).
- Prompts: in git. No backup needed beyond git itself.

---

## 7. Useful one-liners

```bash
# Tail app + worker logs together
make logs

# Replay all 5 brief samples (offline, no LLM keys needed)
make sample-run

# Run the test suite
make test

# Open a SQL shell
docker compose exec postgres psql -U app

# Open a redis shell
docker compose exec redis redis-cli

# Inspect the current graph definition
PYTHONPATH=src python -c "from app.graph import build_graph; print(build_graph().get_graph().draw_mermaid())"
```
