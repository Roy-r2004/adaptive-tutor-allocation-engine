# Apex AI Engineer Assessment — Submission

**Roy Rizkallah** · April 2026

---

## 1. What this is

A production-grade **AI intake & triage pipeline**, end-to-end, for a tutoring-platform support workflow. A user message lands on an HTTP endpoint; an LLM-driven graph classifies it, extracts entities, decides routing, escalates to a human reviewer when deterministic rules fire, and emits a fully-validated structured JSON record per ticket. There is a chat surface for end-users and a reviewer dashboard for the human-in-the-loop.

It is what I would build for V1 of an actual product, not a prototype. Two backing services (Postgres + Redis), an async worker, a typed FastAPI app, a typed React client, observability, migrations, tests, and a single `docker compose up` story.

---

## 2. Deliverables (mapping to the brief)

| Brief asks for | Where it lives |
|---|---|
| Working workflow (end-to-end) | `docker compose up -d --build` from the repo root |
| Exported JSON output | `triage-pipeline/outputs/sample_run_results.json` (5 records) |
| Project code | this repository, ZIP attached |
| Structured output file | same JSON above + human-readable `outputs/sample_run_summary.md` |
| Prompt documentation | `triage-pipeline/docs/prompts.md` + `prompts/*/prompt.meta.yaml` |
| Architecture write-up | `triage-pipeline/docs/architecture.md` (+ ADRs in `docs/adr/`) |
| Tests | 56 backend tests (`make test`) + 15 frontend tests (`npm run test:run`) — all green |
| Screen recording | attached separately (see §8) |

A reviewer with no API keys can still see the pipeline run end-to-end via `python scripts/run_samples.py --stub` — a deterministic heuristic mode that exercises every node, every edge, and the escalation path.

---

## 3. Architecture at a glance

```
┌────────────────────────────────────────────────────────────────────┐
│  React (chat + reviewer)   ──HTTP──▶   FastAPI                     │
│  TanStack Query polling                  │                         │
│  Zod-validated responses                 ▼                         │
│                                       Arq (Redis)                  │
│                                          │                         │
│                                          ▼                         │
│                       LangGraph (Postgres-checkpointed)            │
│                                                                    │
│   START → ingest → classify → enrich → route → output → END        │
│                       │                  │                         │
│              validation fails ×3   trigger fires                   │
│                       └──────► escalate ◄┘                         │
│                                  │                                 │
│                          interrupt() — graph PAUSES                │
│                                  ▲                                 │
│                          Command(resume=…) — HITL resumes          │
└────────────────────────────────────────────────────────────────────┘
```

Three non-obvious things about this design:

- **Escalation is `interrupt()`-based, not a side queue.** The graph literally pauses at the escalate node; the checkpoint persists in Postgres; when a human accepts/edits/rejects the proposed routing, we send `Command(resume=…)` and the same graph instance picks up where it left off. This is how you build a real durable HITL workflow — fire-and-forget queues lose causality.
- **The escalation triggers themselves are pure Python**, not an LLM judgment. Confidence < 70%, outage keywords, billing > $500, classifier-validation-failed-3-times. Auditable, unit-testable, deterministic. The LLM does *labeling*; the policy is code.
- **Multi-provider LLM gateway with automatic fallback** (Groq → Gemini → OpenAI), plus structured-output-with-reflection-retry on Pydantic validation failure. Cost and tokens logged per call.

Full rationale: `triage-pipeline/docs/architecture.md`. Decision records for the load-bearing choices: `docs/adr/`.

---

## 4. Key design decisions (table)

| Decision | Why |
|---|---|
| **LangGraph + Postgres checkpointing** | Durable execution. Escalation truly pauses; HITL truly resumes. Every super-step is idempotent. |
| **Pydantic v2 + `Literal` enums + JSON-mode** | Schema-strict structured output. Reflection retry on validation failure. The LLM cannot return a category that isn't in the union. |
| **Jinja2 prompts with `StrictUndefined`** | Versioned (SHA-256 hash captured in every record's `prompt_versions`). Few-shot driven. No chain-of-thought (Sprague et al. 2024 — CoT hurts classification). |
| **Source-quote anti-hallucination wrapper for entities** | Every extracted entity carries a `source_quote` field. Reviewers can verify provenance at a glance; we can also unit-test that the quote actually appears in the body. |
| **Append-only audit log** | Every state transition persisted. Any ticket's full history is reconstructible. |
| **Arq + Redis with idempotent job IDs** (`triage:{ticket_id}`) | Async-native worker. Retries don't double-process. |
| **SQLAlchemy 2.0 async + Alembic** | Modern typing, deterministic schema migrations. |
| **structlog + OTel + Prometheus** | Single `trace_id` across logs, metrics, traces. |
| **React 19 + Vite + Tailwind + shadcn + TanStack Query + Zod** | Light, fast, typed end-to-end. Zod schemas mirror the Pydantic models so runtime parsing is the single source of truth on the client. No Redux, no localStorage. |

---

## 5. Sample structured output

One of the five records from `outputs/sample_run_results.json`:

```json
{
  "sample_index": 5,
  "input": {
    "source": "web_form",
    "body": "The platform is not loading properly and none of the tutors are showing up. Multiple users are facing the same issue."
  },
  "output": {
    "ticket_id": "…",
    "classification": {
      "category": "incident_outage",
      "priority": "high",
      "confidence": 0.94,
      "rationale": "…"
    },
    "enrichment": {
      "issue_summary": "…",
      "urgency_signals": [
        { "value": "Multiple users", "source_quote": "Multiple users are facing the same issue." }
      ],
      "detected_language": "en"
    },
    "routing": {
      "queue": "it_security",
      "sla_minutes": 15,
      "rationale": "category=incident_outage; priority=high",
      "decided_by": "auto",
      "needs_human": false
    },
    "escalation": {
      "needs_human": true,
      "reasons": ["category_incident_outage"],
      "blocking": true
    },
    "human_summary": "Incident Outage reported via the platform with priority high. Routed to it_security (SLA 15m).",
    "handled_by": "auto",
    "prompt_versions": {
      "classification": "v1#623799d20375",
      "enrichment": "v1#38176e4cc85a",
      "summarization": "v1#632bbda2b97f"
    }
  }
}
```

The 5-record summary table:

| # | Source | Category | Priority | Conf. | Queue | Escalated? |
|---|---|---|---|---|---|---|
| 1 | chat | bug_report | medium | 0.83 | engineering | no |
| 2 | web_form | feature_request | low | 0.92 | product | no |
| 3 | chat | bug_report | medium | 0.86 | engineering | no |
| 4 | chat | technical_question | low | 0.81 | product | no |
| 5 | web_form | incident_outage | high | 0.94 | it_security | **YES** (`category_incident_outage`) |

---

## 6. How to run

The whole stack — backend, worker, frontend, postgres, redis — comes up with one command from the repo root:

```bash
docker compose up -d --build
```

Then:

- Chat surface: <http://localhost:5173>
- Reviewer dashboard: <http://localhost:5173/reviewer>
- API: <http://localhost:8000> (`/healthz`, `/v1/webhook/ingest`, `/v1/tickets/:id`, `/v1/escalations`)

If your host already uses any of those ports, override them in a root `.env`:

```
POSTGRES_PORT=5434
REDIS_PORT=6380
API_PORT=8001
FRONTEND_PORT=5174
```

The frontend automatically points at `http://localhost:${API_PORT}` so the two stay in sync.

To regenerate the deliverable JSON without Docker:

```bash
cd triage-pipeline
make install
make sample-run     # writes outputs/sample_run_results.json
```

To run the test suites:

```bash
cd triage-pipeline && make test         # 56 backend tests
cd triage-frontend && npm run test:run  # 15 frontend tests
```

---

## 7. The frontend — what to look for

This wasn't in the brief explicitly, but a triage pipeline without a way to see the tickets and reviewers without a way to act on escalations is a half-shipped product. So I built one.

- **`/`** — Chat surface. The user types a message, sees a friendly acknowledgment ("Got it — this looks like a billing question. I've routed it to the Billing team — you'll hear back within ~4h."), and then an audit-trail panel below it: category badge, priority, confidence, routing rationale, extracted entities, classification rationale.
- **`/reviewer`** — Pending escalations list. Each card shows the trigger reasons as labelled chips, the proposed routing, the issue summary, and three actions: **Accept** (rubber-stamp), **Edit** (override queue/priority/SLA), **Reject** (with a reason). Optimistic updates so the UI stays responsive while the resume happens server-side.
- **`/ticket/:id`** — Read-only standalone page for any ticket. Linkable, deeplinkable, shareable.

Notable choices on the client:

- **Zod schemas mirror the Pydantic models** in `src/lib/schemas.ts`. Every API response is parsed through them in the axios interceptor — typed end-to-end at runtime, not just at compile-time.
- **TanStack Query polls** the ticket while it's in `received` state. The pipeline only persists three terminal statuses (`received`, `awaiting_review`, `resolved`); the intermediate stages (classifying / enriching / routing / finalizing) are *visualised* by the timeline component while we wait, snapping to the real outcome the moment polling resolves it. We're never lying about the state — we're animating the work that's actually happening.
- **No `useEffect + fetch`.** All server state goes through TanStack Query. All optimistic updates live in mutation hooks.
- **No localStorage, no Redux, no MobX.** Server is the source of truth.
- **shadcn/ui primitives**, custom design tokens, dense typography (Inter, JetBrains Mono), restrained palette, subtle Framer Motion (`out-expo` easing). Asymmetric layout — looks intentional, not ChatGPT-shaped.

---

## 8. What to watch in the screen recording

The recording walks through the full happy path and the escalation path:

1. `docker compose up -d --build` — the full stack coming up healthy.
2. `curl http://localhost:8000/healthz` returning `{"status":"ok"}`.
3. Open the chat surface, send a benign request ("Can you compare tutors by rating?") — watch the timeline progress, land in `resolved`, see the friendly acknowledgment + the audit-trail panel with category, priority, queue, rationale.
4. Send an escalation-triggering message ("the platform is down for everyone right now") — watch the timeline land in `awaiting_review`, see the trigger reason chip, the proposed routing.
5. Open `/reviewer` in a second tab — see the pending escalation card with the trigger reasons.
6. Click **Edit**, override the queue, submit. The card animates out optimistically; the chat tab updates on its next poll.
7. Open `/ticket/:id` — the read-only detail page renders the resolved ticket with the full audit trail and `handled_by: hybrid`.

---

## 9. How I used AI tools during development

Alain asked about this explicitly, and the honest answer is: heavily, but with discipline.

**Where AI accelerated me:**

- **Scaffolding and boilerplate.** Vite + Tailwind + shadcn setup, Pydantic ↔ Zod schema mirroring, ESLint config, Docker compose plumbing, repetitive CRUD endpoints, repository pattern boilerplate — Claude/Cursor wrote first drafts and I edited.
- **Explaining unfamiliar territory.** I hadn't shipped LangGraph in production before this. I used Claude as a Socratic partner to understand the checkpointer / `interrupt()` / `Command(resume=…)` model deeply enough that I could *defend* the design choices, not just type them.
- **Test generation.** Vitest + Testing Library tests, Pytest fixtures, parameterised escalation-rule tests — Claude proposed cases I'd missed (low-confidence + keyword combo, classifier-three-strikes path) and I added them.
- **Refactoring confidence.** When I caught the `redis_settings = property(...)` bug in `workers/queue.py`, I had Claude read the Arq source path with me to confirm Arq reads the attribute off the class object, so the fix was correct in principle and not just superstitiously. Same for the Postgres checkpointer pool fix in `services/triage_service.py`.

**Where I deliberately did *not* lean on AI:**

- **The escalation policy itself.** The trigger thresholds (0.7 confidence, $500 billing, the keyword set, three classifier strikes) are mine and would be a product-policy conversation in a real org. AI gave me reference numbers from public support-ops literature; I picked the values.
- **The architecture choices in the table above.** Each one I can defend on its own merits — durable HITL, multi-provider fallback, source-quote anti-hallucination, schema-strict outputs, audit log. The ADRs in `docs/adr/` capture the reasoning.
- **Code review.** Every Cursor suggestion got read and edited. Several got rejected outright (e.g. an early shadcn dialog pattern that called `setState` inside `useEffect` — I caught it because I read it). The point is to be the senior reviewer of an AI-pair-programming session, not the typist.

**The two real bugs I shipped fixes for during this build:**

- `workers/queue.py` — `redis_settings = property(...)` returns the descriptor object when Arq reads it off the class, not a `RedisSettings` instance. Worker died on startup with `AttributeError`. Fixed by evaluating once at class-definition time. Documented in the README.
- `services/triage_service.py` — the LangGraph Postgres checkpointer was created via `AsyncPostgresSaver.from_conn_string()`, which gives it *one* connection held forever. When that connection idled out, every subsequent triage instantly failed with `psycopg.OperationalError: the connection is closed`. Fixed by switching to `psycopg_pool.AsyncConnectionPool` so dropped connections recycle transparently. Documented in the same place.

These are exactly the kind of integration-level issues you don't catch with unit tests — only by running the thing end-to-end and reading worker logs. AI didn't surface them; running the stack did. AI did help me read the Arq and LangGraph source to confirm the fixes were structurally right, not just locally working.

---

## 10. Trade-offs and what I'd do next

**Things I scoped out of V1 deliberately** (each discussed in `docs/architecture.md`):

- **PII redaction at ingest.** Easy add — a `pre_process` node before classify that runs Microsoft Presidio or a regex-first redactor. Skipped for now because it's a policy choice that needs a real conversation about retention.
- **Semantic cache for repeat questions.** Embeddings + pgvector for "have we seen this before". Pays for itself fast on free-tier billing questions. Skipped because cache invalidation strategy is product-shaped.
- **Distilled L1 classifier.** Train a small SetFit/DistilBERT model on labelled tickets to short-circuit the LLM call for high-confidence cases — same accuracy at ~5% of the cost. Roadmap item, not V1.
- **DSPy compilation of the classification prompt** once we have ~500 labelled tickets. Today the prompts are hand-written with hash-versioned few-shots; that's a fine V1 ceiling.

**The real trade-offs in V1:**

- **Synchronous structured-output retry vs. parallel ensemble.** I chose retry because it's cheaper and the failure mode is rare enough. Ensemble (3 cheap models, vote) is the next step if accuracy ever becomes the binding constraint.
- **Three terminal statuses on the backend instead of streaming intermediate states to the client.** I chose to animate intermediate stages on the client and snap to truth on poll, instead of adding WebSockets / SSE. Ships faster, no streaming infra to debug; the cost is the timeline can drift if the LLM stalls (we'd want a real progress event source eventually).
- **Reviewer surface is intentionally minimal** — list, three actions, edit dialog. No bulk actions, no filtering, no assignment. Those are V2 once we have actual reviewers using it.

---

## 11. Repository layout

```
.
├── README.md                          ← quickstart
├── SUBMISSION.md                      ← this document
├── docker-compose.yml                 ← unified stack (frontend + backend, via include:)
├── .env.example                       ← port overrides
│
├── triage-pipeline/                   ← Python · FastAPI · LangGraph
│   ├── README.md
│   ├── docs/
│   │   ├── architecture.md            ← full design write-up
│   │   ├── prompts.md                 ← prompt design rationale
│   │   ├── runbook.md                 ← ops / DLQ / on-call
│   │   └── adr/                       ← architecture decision records
│   ├── outputs/sample_run_results.json    ← deliverable
│   ├── outputs/sample_run_summary.md      ← deliverable (human)
│   ├── prompts/                       ← Jinja templates + meta YAML
│   ├── src/app/                       ← code (graph, llm, schemas, api, workers)
│   ├── tests/                         ← 56 tests
│   └── scripts/run_samples.py         ← deliverable JSON generator
│
└── triage-frontend/                   ← React 19 · Vite · TypeScript
    ├── README.md
    ├── src/
    │   ├── lib/schemas.ts             ← Zod ↔ Pydantic mirror
    │   ├── lib/api.ts                 ← axios + Zod interceptor
    │   ├── lib/queries.ts             ← TanStack Query hooks
    │   ├── components/chat/           ← chat surface
    │   ├── components/reviewer/       ← reviewer dashboard
    │   └── components/shared/         ← timeline, badges, pills
    └── src/**/__tests__/              ← 15 tests
```

---

## 12. Closing

I treated this assessment the way I'd treat the first sprint of a real product: opinionated about durability, schema-strictness, observability, and the human-in-the-loop story; restrained about scope; honest about where I leveraged AI and where I made the call myself. The whole stack runs from one command, the deliverable JSON is reproducible offline, and the two integration bugs I hit and fixed are the ones a real V1 hits in the first week of staging.

Happy to walk through any of it.

— Roy
