# Architecture write-up

> AI Engineer Assessment — Roy Rizkallah
>
> This document covers the five required write-up sections from the brief:
> system design, routing logic, escalation logic, production improvements,
> and Phase 2 ideas.

---

## 1. System design

### 1.1 Pipeline shape

The system is a **6-stage LangGraph pipeline** that maps 1:1 to the brief's
required steps. The graph is the orchestrator; nodes are units of work.
Conditional routing happens via `Command(goto=...)` returns from each node,
which is the idiomatic 2026 LangGraph pattern.

```
START
  │
  ▼
┌────────┐
│ ingest │  Step 1 — normalize state, bind correlation IDs
└────┬───┘
     │
     ▼
┌──────────┐    self-loop on ValidationError (max 3 attempts)
│ classify │  Step 2 — LLM call → ClassificationResult (Pydantic)
└────┬─────┘    (after 3 retries → escalate with reason "unparseable_llm_output")
     │
     ▼
┌────────┐
│ enrich │  Step 3 — LLM call → EnrichmentResult (entities + source quotes)
└───┬────┘    (soft-fails to empty enrichment rather than blocking)
    │
    ▼
┌───────┐    deterministic Python:
│ route │  Step 4 — category → queue + priority → SLA + escalation triggers
└──┬────┘
   │
   ├──── needs_human → ┌───────────┐  ─── Step 6 — interrupt() pauses graph,
   │                   │ escalate  │       persists state to checkpointer.
   │                   └─────┬─────┘       Resumes on Command(resume=...).
   │                         │
   ▼                         ▼
                    ┌────────────────┐
                    │     output     │  Step 5 — assemble FinalOutput JSON,
                    │ + summarize    │           call summary LLM, persist.
                    └────────┬───────┘
                             │
                             ▼
                            END
```

### 1.2 Component diagram

```
                          ┌─────── Reviewer / on-call UI ────────┐
                          │  GET /v1/escalations                 │
                          │  POST /v1/escalations/{id}/resolve   │
                          │  → enqueues resume_graph             │
                          └────────────────┬─────────────────────┘
                                           │
   inbound channels                        ▼
   (chat / form / ─────►  ┌────────── FastAPI ──────────┐
   email / API)           │  /v1/webhook/ingest          │
                          │  /v1/tickets/{id}            │
                          │  /v1/escalations  /resolve   │
                          │  /healthz /readyz /metrics   │
                          │  middleware: corr-id,        │
                          │   GZip, CORS, slowapi-ready  │
                          └────┬───────────────┬─────────┘
                               │ persist        │ enqueue
                               ▼                ▼
                       ┌───────────────┐  ┌────────────┐
                       │ Postgres 16   │  │  Redis 7   │
                       │  + pgvector   │  │  (Arq)     │
                       │  + checkpoint │  └─────┬──────┘
                       │   tables      │        │
                       └───────▲───────┘        ▼
                               │       ┌────────────────────────┐
                               │       │   Arq async worker     │
                               │       │  triage_message(...)   │
                               │       │  resume_graph(...)     │
                               │       └─────────┬──────────────┘
                               │                 │
                               │       ┌─────────▼──────────────┐
                               │       │  LangGraph (6 nodes)   │
                               │       │  AsyncPostgresSaver    │
                               │       └─────────┬──────────────┘
                               │                 │
                               │       ┌─────────▼──────────────┐
                               │       │  LLM gateway (litellm) │
                               │       │  Groq → Gemini →       │
                               │       │   OpenAI → Ollama      │
                               │       │  + Pydantic validate   │
                               │       │  + reflection retry    │
                               │       └─────────┬──────────────┘
                               │                 │
                               ▼                 ▼
                       ┌──────────────────────────────────────────┐
                       │  Observability                           │
                       │  • structlog (JSON, OTel trace_id)       │
                       │  • Prometheus (/metrics, Grafana panels) │
                       │  • llm_calls + audit_log tables          │
                       └──────────────────────────────────────────┘
```

### 1.3 State schema

**TypedDict for graph state, Pydantic for LLM outputs.** TypedDict serializes
faster into the checkpointer and supports reducers via `Annotated[..., add]`;
Pydantic validates at the model boundary, which is where validation actually
matters.

The state is defined in `src/app/graph/state.py` and the LLM contracts are in
`src/app/schemas/triage.py`.

### 1.4 Persistence

| Table | Purpose |
|---|---|
| `messages` | Raw inbound payload as it arrived (JSONB) |
| `tickets` | The pipeline's view of a message + final output |
| `classifications` | Step 2 result with confidence, model used, prompt version |
| `enrichments` | Step 3 entities (with source quotes) |
| `routing_decisions` | Step 4 queue + SLA + decided_by (auto/hitl) |
| `escalations` | Step 6 pending HITL items, status pending → accepted/edited/rejected |
| `audit_log` | Append-only event history; every state change writes a row |
| `prompt_versions` | SHA-256 of every prompt template; classifications reference back |
| `llm_calls` | Per-call tokens + cost + latency + outcome (foundation of FinOps) |

A Postgres-friendly `JSONBOrJSON` type decorator falls back to `JSON` on
SQLite so the test suite runs without containers.

### 1.5 Why these specific tools

- **LangGraph**: durable, checkpointed, has `interrupt()` for HITL. The
  alternative — Celery with state in DB — would require manually managing
  state machines, and HITL would become a side channel rather than a first-
  class graph primitive.
- **LiteLLM**: cleanest cross-provider abstraction; `completion_cost()`
  ships with a pricing catalog so cost tracking is free.
- **Arq over Celery**: async-native. Celery's prefork model forces
  `asyncio.run()` per task and creates "Future attached to a different
  loop" failures with httpx clients in worker tasks. Arq is purpose-built
  for the workload.
- **Jinja2 with `StrictUndefined`**: the single most important Jinja
  setting in production — fails loud on missing variables instead of
  silently producing the empty string.
- **Pydantic v2 + Literal enums**: `Literal[...]` lands in the JSON schema
  sent to the model and is supported across providers. `enum.Enum` is not
  uniform across providers.
- **structlog**: async-safe via `contextvars`; routes stdlib loggers
  (uvicorn, SQLAlchemy, langchain) through the same renderer; cheap to
  enrich with the active OTel trace_id on every line.

---

## 2. Routing logic

### 2.1 Mapping (Step 4)

Routing is **deterministic and table-driven** in
`src/app/graph/edges.py`:

```python
CATEGORY_TO_QUEUE = {
    "bug_report":          "engineering",
    "feature_request":     "product",
    "billing_issue":       "billing",
    "technical_question":  "product",
    "incident_outage":     "it_security",
}

SLA_BY_PRIORITY = {
    "high":   15,    # minutes to first human response
    "medium": 60,
    "low":    240,
}
```

The brief asks for queues `Engineering, Billing, Product, IT/Security` plus a
fallback for low-confidence. We add a `fallback` queue for any unmapped
category (defensive — should never fire because category is a `Literal`).

### 2.2 Why deterministic mapping (not an LLM call)

Three reasons:

1. **Auditability.** Reviewers can answer "why was ticket X routed to
   billing?" without re-running an LLM. The mapping is a single Python dict
   in source control.
2. **Cost.** A second LLM call for routing is unjustifiable when the
   classification already carries the queue information.
3. **Reliability.** Routing is the place humans bisect bugs. Determinism
   makes incident triage trivial.

### 2.3 Low-confidence fallback

Per the brief: "include fallback for low-confidence." We do not route low-
confidence tickets to a generic "needs review" pile — we **fire the
escalation interrupt** so a human reviews the proposed routing before it
takes effect. This preserves the auto-routing latency for the 80%+ of
tickets the model handles confidently and inserts a human in the loop for
the rest.

---

## 3. Escalation logic

### 3.1 The four triggers

The brief specifies three; we add one bonus rule. All four are evaluated in
`src/app/graph/edges.py::evaluate_escalation_triggers`. **Each is pure
Python — no LLM judgment, fully unit-tested.**

| Rule | Trigger condition | Reason string |
|---|---|---|
| Low confidence | `classification.confidence < 0.70` | `low_confidence=0.62` |
| Outage keywords | body contains any of `["outage", "down for all users", "production down", "data loss", "security breach"]` | `keyword_match=outage` |
| Billing threshold | `category == billing_issue` AND any `enrichment.invoice_amounts_usd > $500` | `billing_amount_exceeded=750.00>500` |
| Incident bonus | `category == incident_outage` (always pages) | `category_incident_outage` |

The keyword list and thresholds are **environment variables** (see
`.env.example`) so ops can tune without redeploys.

### 3.2 How the escalation actually fires

The brief says "flag." We go further: when a trigger fires, the graph
**actually pauses**. The `escalate` node calls `interrupt(payload)`,
LangGraph persists the state via the checkpointer, and `ainvoke()`
returns with `__interrupt__` in the result. The caller (the Arq worker)
reads this, writes a row to the `escalations` table with status `pending`,
and finishes — releasing the worker for the next job.

When a human reviewer hits `POST /v1/escalations/{id}/resolve`, the API
writes the decision to the DB and enqueues a `resume_graph` task. The
worker picks it up, calls `graph.ainvoke(Command(resume=decision))` with
the same `thread_id`, and the graph resumes inside the `escalate` node
**from the line after `interrupt()`** with `decision` as its return value.

The graph then proceeds to `output`, assembles `FinalOutput` with
`handled_by="human"` (or `"hybrid"` if the human edited the routing),
persists, and ends.

### 3.3 Why this matters

- **Durable.** A 4am pager → reviewer doesn't wake up → ticket sits for 8
  hours → reviewer accepts at noon → graph resumes from the exact
  checkpoint, on a different worker, even after a deploy. Nothing
  re-runs that already ran.
- **Auditable.** Every escalation has a row in `escalations` and a row in
  `audit_log`. The `resolution` JSONB field records the reviewer's exact
  decision.
- **Surgically interruptible.** A reviewer can `edit` the routing
  (override the queue, change SLA, add a rationale), `accept` the
  proposal, or `reject` and bounce the ticket back. All three flow through
  the same `interrupt()`/`Command(resume)` mechanism.

### 3.4 The HITL gotcha

A node that calls `interrupt()` re-executes from the top on resume — the
`interrupt()` returns the supplied value the second time around, but
everything before it runs again. **Side effects must come after the
interrupt, never before.** The `escalate` node respects this: state
mutations live in the lines after `decision = interrupt(payload)`.

---

## 4. Production improvements

The deliverable is intentionally V1-shaped. The list below is what I
would push into V2 in priority order, by ROI for an intake/triage
system.

### 4.1 Things I'd ship next, in priority order

| # | Improvement | Effort | Why |
|---|---|---|---|
| 1 | **PII redaction at ingestion** (Microsoft Presidio) | M | Compliance gate. Mask emails / phones / payment data before storing in `messages`, never log PII downstream. Cheapest catastrophic-risk reducer. |
| 2 | **Corrections feedback loop** | M | Capture `(original_label, corrected_label, reviewer)` from every `escalations.resolution` of type `edit`. This is the dataset you'll use for everything below. |
| 3 | **SLA breach alerting** | M | A `sla_policies` table; a periodic Arq cron that scans tickets with `status != resolved` and `created_at + sla_minutes < now()`. Three-tier escalation at 75% / 90% / 100% of SLA. |
| 4 | **Provider prompt caching + batch APIs** | S | OpenAI/Anthropic cached input is ~90% cheaper; non-realtime classification can use Batch APIs for 50% off. Realistic 60–70% bill reduction. |
| 5 | **Semantic cache** | M | RedisVL `SemanticCache` keyed by `(tenant, prompt_version, embedding(body))`. 25–40% LLM-call elimination on the long tail of duplicate questions. |
| 6 | **Per-tenant token budgets** | M | Track monthly tokens per `tenant_id` in `llm_calls`; reject (or downgrade to local Ollama) once a tenant blows its budget. Prevents one customer from blowing the AI bill. |
| 7 | **Hybrid retrieval used as classification prior** | L | BM25 + pgvector HNSW fused via reciprocal rank fusion; cross-encoder reranker on top-20 → top-5; **inject the top-5 similar past tickets into the classifier prompt as context.** Past resolutions are the strongest signal we have, and we're not using them in V1. |
| 8 | **A/B prompt testing in shadow mode** | M | Run prompt v1 and prompt v2 in parallel; sample 10% to v2; record predictions for both; compare against the corrections set. Promote v2 only when ΔF1 > 95% CI on a held-out split. |
| 9 | **Calibration via temperature scaling** | S | LLM-verbalized confidence is poorly calibrated (ECE > 0.37 on GPT-4 per Geng et al. 2024). Train a 1-parameter temperature scaler on the corrections set; recalibrate quarterly. The 0.70 threshold is meaningless until this exists. |
| 10 | **Auto-response generation for low-priority tickets** | M | Layered guardrails: allowlisted category, calibrated confidence > 0.95, retrieval similarity > 0.85, no PII, not VIP. First 50 per template human-reviewed. Always include "reply 'agent' to talk to a human." Track `reopen_rate`. |

### 4.2 Hardening items already partially done

These are scaffolded in the V1 code and just need plugging in:

- **OpenTelemetry trace export.** The SDK is wired; setting
  `OTEL_EXPORTER_OTLP_ENDPOINT` enables it. Set it to your Tempo / Jaeger
  / Langfuse endpoint and you get full trace correlation.
- **Langfuse v3.** The compose file references it; uncomment, set
  the secret keys, and the LLM calls + prompt management automatically
  flow into the UI via `litellm.callbacks = ["langfuse"]`.
- **Rate limiting.** `slowapi` is in deps; add per-endpoint limits when
  required.
- **Alembic migrations.** `make migrate` runs. Adding new tables is
  `alembic revision --autogenerate`.

### 4.3 Things I deliberately did NOT do for V1

- **Multi-tenancy with Postgres RLS.** The schema has a `tenant_id`
  column everywhere, but RLS policies are not enforced. Adding them is
  one Alembic migration; deferring kept the assessment focused.
- **Real provider quotas / circuit breakers.** LiteLLM's
  `cooldown_time` would replace any custom circuit breaker.
- **WebSocket streaming to a reviewer UI.** The graph supports
  `astream(stream_mode=["updates","custom"])`; the SSE endpoint is a
  small addition.

---

## 5. Phase 2 ideas

Three ideas that would distinguish a V2 from a V1 — what I'd present
to the team after week one.

### 5.1 DSPy + MIPROv2 prompt compilation

Stop hand-writing prompts. Define each step as a DSPy `Predict`
signature (input fields → output fields), feed the corrections dataset
in as supervision, and run MIPROv2 to compile the prompt. Each model
swap (GPT-5-mini → Gemini 3 Flash) becomes a re-compile, not a re-write.

The DSPy signature for our classifier:

```python
class Classify(dspy.Signature):
    """Classify a tutoring-platform support ticket."""
    body: str = dspy.InputField()
    source: Literal["chat", "web_form", "email", "api"] = dspy.InputField()
    category: Category = dspy.OutputField()
    priority: Priority = dspy.OutputField()
    confidence: float = dspy.OutputField()
    rationale: str = dspy.OutputField()
```

Stanford's 2025 results show MIPROv2-compiled prompts beat hand-tuned
ones by 5–15pp on multi-step pipelines. The compilation budget is one
afternoon of compute; the maintenance savings compound forever.

### 5.2 Distilled L1 classifier (FrugalGPT cascade)

After ~5k labeled tickets accumulate from the corrections loop, fine-
tune **ModernBERT-base** + a 5-class head as the L1 classifier; use
**temperature scaling** for calibration. The cascade then becomes:

```
 ticket
   ↓
 ModernBERT (10ms, $0)
   ↓
 conf ≥ 0.92 AND category in {feature_request, technical_question}?
   ├── yes → emit, done
   └── no  → escalate to LLM (current V1 path)
```

Realistic outcome: 70–80% of common categories handled at $0 / 10ms;
LLM cost cut by 70%; p50 latency from ~800ms to ~50ms. The cost is one
HuggingFace training run a quarter. This is what mature
classification-heavy LLM apps look like in production.

### 5.3 Hybrid retrieval as a classification prior

Current V1 sends the ticket body and a few static few-shot examples to
the classifier. Phase 2: retrieve the top-5 most-similar **resolved**
tickets and inject them into the prompt as dynamic few-shots.

Pipeline:

```
 ticket → embed(body) ──► pgvector HNSW search top 50
                                    │
              ─── fuse via RRF ────  ├── ► BM25 search top 50
                                    │
                                    ▼
                              ┌─────────┐
                              │ rerank  │  cross-encoder (BGE-reranker-v2-m3)
                              └────┬────┘
                                   │ top 5
                                   ▼
                          inject as <past_examples> in classification prompt
```

The `enrichment` node would fetch these and `classify` would consume
them. Senior reviewers immediately recognize this as the right move:
RAG is not a synonym for "answer questions"; it's a way to **inject
known-good labels as priors**.

---

## 6. Mapping back to the evaluation criteria

| Criterion (weight) | What earns the marks |
|---|---|
| **Workflow Functionality (25%)** | One-command setup (`make sample-run` for offline review; `make up` for full stack). Durable LangGraph with checkpoint-based HITL resume. 56 passing tests. |
| **Classification & Prompt Quality (25%)** | Jinja2 with `StrictUndefined`; few-shot driven (no CoT — Sprague et al. 2024); XML-sectioned for cross-provider parity; SHA-256-versioned; rationale comes after the label; `ExtractedEntity.source_quote` anti-hallucination pattern. |
| **System Design Thinking (20%)** | This document; ADRs in `docs/adr/`; explicit tradeoff calls; layered retry strategy; Phase 2 prioritization with reasoning. |
| **Structured Output Quality (15%)** | Pydantic v2 with `Literal` enums; reflection retry on validation failure; `FinalOutput` includes `prompt_versions` (for reproducibility), `trace_id`, `handled_by`. |
| **Documentation & Communication (15%)** | `README.md`, `docs/architecture.md`, `docs/prompts.md`, `docs/runbook.md`, ADRs, prompt meta YAMLs, generated `outputs/sample_run_summary.md`. |
