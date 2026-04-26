# Apex AI Triage

End-to-end AI intake & triage pipeline with a FastAPI + LangGraph backend and a React frontend, both fully containerized.

```
.
├── triage-pipeline/      Python · FastAPI · LangGraph · Postgres · Redis · Arq
└── triage-frontend/      React 19 · Vite · TypeScript · Tailwind · shadcn/ui
```

## Run everything with Docker

```bash
docker compose up -d --build
```

That brings up the full stack from this directory:

| Service | Default port | Description |
|---|---|---|
| `frontend` | **5173** | Chat UI + reviewer dashboard |
| `app` | **8000** | FastAPI — `/v1/webhook/ingest`, `/v1/tickets/:id`, `/v1/escalations`, `/healthz` |
| `worker` | — | Arq worker driving the LangGraph pipeline |
| `migrate` | — | One-shot Alembic migration |
| `postgres` | 5432 | Postgres 16 + pgvector |
| `redis` | 6379 | Redis 7 (queue) |

After a minute (first build) you can:

- Open http://localhost:5173 — chat surface
- Open http://localhost:5173/reviewer — pending escalations
- `curl http://localhost:8000/healthz` — should return `{"status":"ok"}`

The root `docker-compose.yml` uses Compose's `include:` directive to pull in the backend stack from `triage-pipeline/docker-compose.yml` and adds the frontend service on top — no duplication.

### If your host already uses 5432 / 6379 / 8000 / 5173

Every host port is overridable. Drop a `.env` next to this README:

```
POSTGRES_PORT=5434
REDIS_PORT=6380
API_PORT=8001
FRONTEND_PORT=5174
```

The frontend automatically points at `http://localhost:${API_PORT}` so the two stay in sync. `.env.example` has the same template.

## Run pieces individually

| Goal | Command |
|---|---|
| Backend only (Docker) | `cd triage-pipeline && docker compose up -d --build` |
| Frontend only (host) | `cd triage-frontend && npm install && npm run dev` |
| Backend tests | `cd triage-pipeline && make test` |
| Frontend tests | `cd triage-frontend && npm run test:run` |
| Frontend build | `cd triage-frontend && npm run build` |

## Configuration

`triage-pipeline/.env` holds the LLM provider keys and model identifiers. See `triage-pipeline/README.md` for the full set.

`triage-frontend/.env` is just three knobs:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=
VITE_ENV=dev
```

When the unified Docker stack is up, those defaults are correct — no edits needed.

## What to look at

- **`triage-pipeline/`** — see `README.md`, `docs/architecture.md`, `docs/adr/` for backend design and decisions.
- **`triage-frontend/`** — see `README.md`. Highlights:
  - `src/lib/schemas.ts` — Zod schemas mirroring the backend's Pydantic models (single source of truth)
  - `src/lib/api.ts` — axios + Zod-validated response interceptor
  - `src/lib/queries.ts` — TanStack Query hooks with polling and optimistic updates
  - `src/components/shared/PipelineTimeline.tsx` — the live status timeline

## One backend tweak (worth flagging)

`triage-pipeline/src/app/workers/queue.py` previously declared `redis_settings` as a `property(...)` on the `WorkerSettings` class. Arq reads that attribute off the *class* (not an instance), so it received the descriptor object rather than a `RedisSettings`, and the worker died on startup with `AttributeError: 'property' object has no attribute 'host'`. Fixed by evaluating it once at class-definition time:

```python
redis_settings = _redis_settings()
```

That's the only backend change. API contracts and behavior are untouched.
