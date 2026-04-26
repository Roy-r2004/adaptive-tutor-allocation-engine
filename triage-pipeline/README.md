# AI Engineer Assessment — Roy Rizkallah

**Apex AI take-home: AI-powered intake & triage pipeline for a tutoring platform.**

A production-grade, durable, multi-step LangGraph pipeline that ingests
unstructured user messages, classifies them with an LLM, extracts entities,
routes to the right queue, escalates to a human when the rules fire, and
emits a fully-validated structured JSON record per ticket.

---

## TL;DR for reviewers

```bash
# 1) Clone, copy env, set at least one provider key (optional for stub mode)
cp .env.example .env
# Edit .env: set GROQ_API_KEY (free tier) or GEMINI_API_KEY or OPENAI_API_KEY

# 2) Generate the deliverable JSON for the 5 brief samples (no Docker needed)
make install
make sample-run
# → outputs/sample_run_results.json   ← exported JSON output (deliverable)
# → outputs/sample_run_summary.md     ← human-readable summary

# 3) (optional) Boot the full stack
make up                # postgres + redis + api + worker
# Then POST to http://localhost:8000/v1/webhook/ingest

# 4) (optional) Run the test suite
make test              # 56 tests: schemas, prompts, escalation rules, graph
```

If you don't have any LLM keys handy, run `python scripts/run_samples.py --stub`
— it uses a deterministic heuristic classifier so the pipeline can be reviewed
end-to-end offline. The graph wiring, escalation triggers, routing, and
JSON-schema validation are the same.

---

## What you're looking at

This is a **6-stage LangGraph pipeline** (matching the brief 1:1):

```
START → ingest → classify → enrich → route → output → END
                    ↓ validation fail x3      ↓ trigger fires
                                escalate ← ← ←
                                   ↓ interrupt() — graph PAUSES, persists state
                                   ↑ Command(resume=...) — HITL resumes graph
```

**Key design choices** (full rationale in `docs/architecture.md`):

| Choice | Why |
|---|---|
| **LangGraph + checkpointing** | Durable execution. Escalations literally pause the graph; HITL resumes from the checkpoint. Not a side queue. |
| **Multi-provider LLM gateway (Groq → Gemini → OpenAI → Ollama)** | Resilience and cost. Falls through automatically; cost/tokens logged per call. |
| **Pydantic + Literal enums + JSON-mode** | Schema-strict structured output. Reflection retry on validation failure. |
| **Jinja2 prompts with `StrictUndefined`** | Versioned (SHA-256), few-shot driven, no chain-of-thought (Sprague et al. 2024). |
| **Deterministic escalation rules** | Step 6 triggers are pure Python — auditable, unit-testable, never an LLM judgment. |
| **structlog + OTel + Prometheus** | Single `trace_id` across logs / metrics / traces. |
| **Append-only audit log** | Every state change persisted; reproducibility for any ticket's history. |
| **Arq + Redis** | Async-native worker. Idempotent job IDs (`triage:{ticket_id}`). |
| **SQLAlchemy 2.0 async + Alembic** | Modern typing, deterministic migrations. |
| **Docker compose, multi-stage, non-root** | One command brings up the whole stack. |

---

## Repository layout

```
ai-triage-pipeline/
├── src/app/
│   ├── api/v1/                FastAPI routers (ingest, tickets, escalations)
│   ├── core/                  config, logging, db, lifecycle
│   ├── graph/                 LangGraph nodes, state, builder, escalation rules
│   │   ├── nodes/
│   │   │   ├── ingest.py      Step 1
│   │   │   ├── classify.py    Step 2
│   │   │   ├── enrich.py      Step 3
│   │   │   ├── route.py       Step 4
│   │   │   ├── output.py      Step 5
│   │   │   └── escalate.py    Step 6 (uses interrupt())
│   │   ├── edges.py           deterministic escalation triggers
│   │   ├── state.py           TypedDict graph state
│   │   └── builder.py         compiled StateGraph
│   ├── llm/
│   │   ├── gateway.py         multi-provider LiteLLM router + reflection retry
│   │   └── tracking.py        per-call cost/token logging
│   ├── models/                SQLAlchemy 2.0 ORM
│   ├── schemas/               Pydantic v2 (LLM contracts + API I/O)
│   ├── prompts/registry.py    Jinja loader, hashing, examples
│   ├── repositories/          data access
│   ├── services/triage_service.py  bridges API ↔ graph
│   ├── workers/queue.py       Arq tasks + WorkerSettings
│   ├── observability/metrics.py    Prometheus
│   └── main.py                FastAPI app
├── prompts/                   Jinja templates (versioned in git)
│   ├── _shared/safety.j2
│   ├── classification/ticket_classify_v1.j2 + examples/few_shot.yaml + meta
│   ├── enrichment/extract_v1.j2 + meta
│   └── summarization/summary_v1.j2 + meta
├── alembic/                   migrations
├── tests/
│   ├── unit/                  schema, prompt, escalation-rule tests
│   └── graph/                 end-to-end with mocked LLM (the 5 brief samples)
├── scripts/run_samples.py     deliverable JSON generator
├── docs/
│   ├── architecture.md        full design write-up (system / routing / escalation / phase 2)
│   ├── prompts.md             prompt design rationale
│   ├── runbook.md             operations / DLQ / on-call
│   └── adr/                   architecture decision records
├── outputs/                   sample_run_results.json (deliverable)
├── configs/                   prometheus, grafana
├── Dockerfile                 multi-stage, non-root
├── docker-compose.yml         postgres + redis + app + worker (+ obs profile)
├── pyproject.toml
├── Makefile
└── .env.example
```

---

## The six pipeline steps, mapped to the codebase

| Step | Brief requirement | Implementation |
|---|---|---|
| 1. Ingestion | Accept raw message via webhook, folder, form, etc. | `src/app/api/v1/ingest.py` → persists `messages` + `tickets`, enqueues Arq job (idempotent on `ticket_id`) |
| 2. Classification | LLM assigns Category, Priority, Confidence | `src/app/graph/nodes/classify.py` + `prompts/classification/ticket_classify_v1.j2`. Pydantic-validated. |
| 3. Enrichment | Core issue, identifiers, error codes, urgency | `src/app/graph/nodes/enrich.py` + `prompts/enrichment/extract_v1.j2`. Source-quote anti-hallucination pattern. |
| 4. Routing | Map to queue + low-confidence fallback | `src/app/graph/nodes/route.py` + `src/app/graph/edges.py`. Deterministic Python rules. |
| 5. Structured Output | JSON with classification + entities + routing + summary | `src/app/graph/nodes/output.py` + `src/app/schemas/triage.py::FinalOutput` |
| 6. Escalation | Confidence < 70%, outage keywords, billing > $500 | `src/app/graph/edges.py::evaluate_escalation_triggers` + `src/app/graph/nodes/escalate.py` (uses `interrupt()`) |

---

## Quick API tour

```bash
# 1) Submit a ticket
curl -X POST http://localhost:8000/v1/webhook/ingest \
  -H "Content-Type: application/json" \
  -d '{"source":"chat","body":"platform is down for all users","tenant_id":"acme"}'
# {"message_id": "...", "ticket_id": "...", "job_id": "triage:..."}

# 2) Check status
curl http://localhost:8000/v1/tickets/{ticket_id}

# 3) See pending escalations
curl http://localhost:8000/v1/escalations

# 4) Resolve one (resumes the paused graph)
curl -X POST http://localhost:8000/v1/escalations/{id}/resolve \
  -H "Content-Type: application/json" \
  -d '{"action":"accept","reviewer":"alice"}'
```

---

## What's been built vs. roadmap

This implementation covers everything the brief asks for plus all the
"surprise" decisions called out in `docs/architecture.md`:
durable HITL via `interrupt()`, multi-provider fallback, audit log,
Prometheus metrics, full test suite, Docker compose with the full stack,
deterministic offline mode for review without API keys.

Phase-2 ideas (PII redaction, semantic cache, hybrid retrieval as a k-NN
classification prior, DSPy compilation, distilled L1 classifier) are
deliberately scoped out — they're discussed in the architecture doc as
the post-V1 roadmap. The design is structured so each can drop in without
disturbing the V1 contracts.

---

## Submission deliverables checklist

- [x] **Working workflow** — `make sample-run` end-to-end
- [x] **Exported JSON output** — `outputs/sample_run_results.json` (5 records)
- [x] **Project code (zipped)** — this archive
- [x] **Structured output file** — `outputs/sample_run_results.json` + `outputs/sample_run_summary.md`
- [x] **Prompt documentation** — `docs/prompts.md` + `prompts/*/prompt.meta.yaml`
- [x] **Architecture write-up** — `docs/architecture.md`
- [x] **Tests** — 56 passing (unit + graph)
- [ ] **Screen recording** — to be recorded

---

**Roy Rizkallah** — submission for Apex AI's AI Engineer assessment.
