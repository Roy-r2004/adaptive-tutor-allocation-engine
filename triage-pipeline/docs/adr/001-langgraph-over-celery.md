# ADR 001 — LangGraph for orchestration



## Context

The brief specifies six steps with conditional flow (validation
retries, escalation, human-in-the-loop). We need to choose how to
orchestrate them.

Three options were on the table:

1. **Hand-rolled state machine** persisted in Postgres, with the
   API + workers transitioning rows from one state to the next.
2. **Celery chains** + a `tickets.state` column.
3. **LangGraph** — a state graph compiled to a runnable, with a
   pluggable checkpointer.

## Decision

**LangGraph with `AsyncPostgresSaver` in production, `MemorySaver` in
tests.**

## Why

The deciding factor is **`interrupt()`-based human-in-the-loop**.
Step 6 of the brief requires escalation; "escalation" implies the
graph genuinely pauses, persists, and resumes — not a fire-and-forget
flag stamped on a row.

In LangGraph this is trivial:

```python
async def escalate(state):
    decision = interrupt(payload)   # graph pauses here, state checkpointed
    return {"handled_by": "human", ...}
```

And to resume:

```python
graph.ainvoke(Command(resume=decision), config={"configurable": {"thread_id": ticket_id}})
```

The same primitive supports `accept`, `edit`, and `reject` decisions,
plus surviving deploys and worker crashes (the checkpoint is durable).

In a hand-rolled state machine, this would be a two-week project — and
worse, every node would have to be written as restartable from any
checkpoint. LangGraph gives us that for free.

The other LangGraph wins:

- **Conditional edges via `Command(goto=...)`.** Cleaner than
  middleware hooks.
- **Streaming.** Phase 2 will expose live progress to a reviewer UI
  via `astream`.
- **State reducers.** The `errors: Annotated[list[str], add]` pattern
  is built in.

## Tradeoffs

- LangGraph adds a dependency and a learning curve. Mitigated by
  keeping nodes thin and pure.
- The checkpointer schema is managed by LangGraph itself; we keep our
  app schema separate, so we own the canonical data model.

## Consequences

- We commit to LangGraph 0.2+ APIs (`Command`, `interrupt`,
  `AsyncPostgresSaver`).
- Every node must be **idempotent on resume** because nodes calling
  `interrupt()` re-execute from the top on resume. Side effects must
  come AFTER the interrupt.
