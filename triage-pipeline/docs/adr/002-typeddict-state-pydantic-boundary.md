# ADR 002 — TypedDict for graph state, Pydantic only at the LLM boundary



## Context

LangGraph supports both `TypedDict` and Pydantic `BaseModel` for
graph state. They have different tradeoffs:

| | TypedDict | Pydantic BaseModel |
|---|---|---|
| Validation | None | Full |
| Serialization speed | Fast (dict) | Slower (model_dump) |
| Reducers (`Annotated[..., add]`) | Native support | Native support |
| Visibility in IDE | Decent | Better |

LangGraph's docs note that Pydantic state slows down checkpointing
because every super-step writes the state, so the cost of
serialization is paid hundreds of times per workflow.

## Decision

**TypedDict for the graph state. Pydantic for LLM input/output
contracts only.**

```python
class TriageState(TypedDict, total=False):
    body: str
    classification: ClassificationResult | None   # Pydantic — validated at LLM boundary
    enrichment: EnrichmentResult | None
    routing: RoutingResult | None
    errors: Annotated[list[str], add]            # reducer
    ...
```

## Why

- **Validation belongs at the LLM boundary, not throughout the graph.**
  The model returns JSON; we validate it once via
  `ClassificationResult.model_validate(parsed_json)`. After that, the
  result is trusted across the rest of the graph — re-validating it
  on every checkpoint write would be wasted work.
- **Checkpointing is hot.** Every super-step persists state. TypedDict
  writes are essentially `json.dumps({...})`; Pydantic writes are
  `model.model_dump_json()` plus model rebuilding on read.
- **Pydantic is still required at the LLM boundary** because the
  models can be coerced into JSON-schema sent to the provider via
  `with_structured_output` or Instructor.

## Tradeoffs

- We give up automatic schema validation across the whole graph.
  Mitigated by treating the LLM nodes as the only "untrusted" inputs;
  everything else is application-level Python.
- IDE completion on TypedDict is slightly weaker than on Pydantic
  models. Mitigated by `total=False` plus `.get(...)` access.

## Consequences

- LLM contracts (`ClassificationResult`, `EnrichmentResult`,
  `RoutingResult`, `EscalationFlag`, `FinalOutput`) live in
  `src/app/schemas/triage.py` and are the canonical types crossing the
  LLM ↔ application boundary.
- Graph state is TypedDict; nodes return `dict | Command(...)`.
