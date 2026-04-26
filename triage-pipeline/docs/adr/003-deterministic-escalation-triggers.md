# ADR 003 — Deterministic escalation triggers



## Context

The brief specifies three escalation triggers (Step 6):

1. Confidence < 70%
2. Outage keywords ("outage", "down for all users")
3. Billing tickets with invoices > $500

There are two ways to implement these:

a. **As an LLM judge** — pass the ticket + classification to a model
   and ask "should this escalate? why?"
b. **As pure Python** — apply rules directly on the classification +
   enrichment results.

## Decision

**Pure Python in `src/app/graph/edges.py::evaluate_escalation_triggers`.**

```python
def evaluate_escalation_triggers(*, body, classification, enrichment) -> list[str]:
    triggers = []
    if classification.confidence < settings.escalation_confidence_threshold:
        triggers.append(f"low_confidence={classification.confidence:.2f}")
    matched = [kw for kw in settings.escalation_keywords if kw in body.lower()]
    if matched:
        triggers.append(f"keyword_match={','.join(matched)}")
    # ... and so on
    return triggers
```

## Why

- **Auditability.** "Why was this ticket escalated?" has a one-line
  answer: the trigger reason string, deterministic from the inputs.
- **Cost.** A second LLM call per ticket would roughly double our
  bill for zero quality improvement.
- **Latency.** This adds <0.1ms vs. ~500ms for an LLM call.
- **Testability.** Easily exhaustively unit-tested. `tests/unit/
  test_escalation_triggers.py` has 14 tests covering all four rules,
  edge cases, and combinations.
- **Tunability.** All thresholds and keywords are environment
  variables. Ops can tune them without redeploys (see runbook §4.3).

## What gets the LLM, what doesn't

Use the LLM where its strengths matter:
- Classification (open-ended judgment over noisy text)
- Entity extraction (open-ended, with grounded source quotes)
- Summary writing (natural language generation)

Don't use it for:
- Routing (table lookup)
- SLA assignment (table lookup)
- Threshold checks (arithmetic)
- Keyword detection (substring match)

This is Sprague et al. 2024 in spirit: don't ask the LLM to do tasks
where it's weaker than a 5-line rule.

## Consequences

- The three brief-mandated rules plus a fourth bonus rule
  (`category == incident_outage` always escalates) are encoded in the
  function. New rules go here, with corresponding unit tests.
- The function returns a `list[str]` of human-readable reason
  strings, which flow through to `EscalationFlag.reasons` and onto
  the human reviewer's screen.
