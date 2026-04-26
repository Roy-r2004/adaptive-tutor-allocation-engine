# Architecture Decision Records

Lightweight ADRs documenting the load-bearing decisions in this
codebase. Each one captures *what* was decided, *what was considered*,
and *why*. The decisions themselves are reflected in the code.

| # | Decision |
|---|---|
| [001](./001-langgraph-over-celery.md) | LangGraph for orchestration (not a hand-rolled state machine on Celery) |
| [002](./002-typeddict-state-pydantic-boundary.md) | TypedDict for graph state, Pydantic only at the LLM boundary |
| [003](./003-deterministic-escalation-triggers.md) | Escalation triggers are pure Python, not LLM-judged |
| [004](./004-litellm-over-langchain-fallbacks.md) | LiteLLM for provider routing, not LangChain's `with_fallbacks` |
| [005](./005-arq-over-celery.md) | Arq for the worker queue, not Celery |
