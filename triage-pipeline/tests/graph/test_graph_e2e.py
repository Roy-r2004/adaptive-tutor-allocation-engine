"""LangGraph integration tests with a mock LLM gateway.

Verifies the 6-step pipeline end-to-end, including:
  - happy path (auto resolution)
  - low-confidence escalation
  - outage keyword escalation
  - billing > $500 escalation
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from pydantic import BaseModel

from app.graph import build_graph
from app.llm import gateway as gateway_mod
from app.schemas.triage import (
    ClassificationResult,
    EnrichmentResult,
    EscalationFlag,
    ExtractedEntity,
    RoutingResult,
)


# ---------------------------------------------------------------------------
# A tiny in-memory fake gateway. Returns scripted responses keyed by operation.
# ---------------------------------------------------------------------------


class FakeGateway:
    def __init__(self, scripts: dict[str, list[Any]]) -> None:
        self._scripts = {k: list(v) for k, v in scripts.items()}

    async def complete_structured(
        self,
        *,
        prompt: str,
        schema: type,
        operation: str,
        **kwargs: Any,
    ) -> Any:
        bucket = self._scripts.get(operation)
        if not bucket:
            raise AssertionError(f"No scripted response for {operation}")
        next_resp = bucket.pop(0)
        if isinstance(next_resp, schema):
            return next_resp
        if isinstance(next_resp, dict):
            return schema.model_validate(next_resp)
        # For summarization we use an inline BaseModel
        if isinstance(next_resp, BaseModel):
            return next_resp
        raise AssertionError(f"Bad scripted response: {next_resp!r}")


@pytest.fixture
def patch_gateway(monkeypatch: pytest.MonkeyPatch):
    """Returns a function that installs a FakeGateway with given scripts."""

    def _install(scripts: dict[str, list[Any]]) -> FakeGateway:
        fake = FakeGateway(scripts)
        # Bypass LRU cache by patching get_gateway
        monkeypatch.setattr(gateway_mod, "get_gateway", lambda: fake)
        # Also patch the import sites
        from app.graph.nodes import classify, enrich, output as output_node

        monkeypatch.setattr(classify, "get_gateway", lambda: fake)
        monkeypatch.setattr(enrich, "get_gateway", lambda: fake)
        monkeypatch.setattr(output_node, "get_gateway", lambda: fake)
        return fake

    return _install


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------


class _Summary(BaseModel):
    summary: str


def _scripts(
    *,
    category: str = "bug_report",
    priority: str = "medium",
    confidence: float = 0.9,
    amounts: list[float] | None = None,
    summary: str = "Auto-generated summary.",
) -> dict[str, list[Any]]:
    return {
        "classify": [
            ClassificationResult(
                category=category, priority=priority, confidence=confidence,
                rationale="cited words from ticket",
            )
        ],
        "enrich": [
            EnrichmentResult(
                issue_summary="user issue",
                affected_ids=[],
                error_codes=[],
                invoice_amounts_usd=amounts or [],
                urgency_signals=[],
                detected_language="en",
            )
        ],
        "summarize": [_Summary(summary=summary)],
    }


def _initial_state(body: str, source: str = "chat") -> dict[str, Any]:
    return {
        "ticket_id": "t-test",
        "message_id": "m-test",
        "body": body,
        "source": source,
        "tenant_id": "default",
        "errors": [],
        "prompt_versions": {},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_auto_resolution(patch_gateway) -> None:
    patch_gateway(_scripts(category="feature_request", priority="low", confidence=0.95))
    graph = build_graph()
    state = _initial_state("Could we have a dark mode option please?")
    result = await graph.ainvoke(state)
    assert result.get("final") is not None
    assert "__interrupt__" not in result
    final = result["final"]
    assert final.classification.category == "feature_request"
    assert final.routing.queue == "product"
    assert final.escalation.needs_human is False


@pytest.mark.asyncio
async def test_low_confidence_escalates(patch_gateway) -> None:
    patch_gateway(_scripts(confidence=0.55))
    graph = build_graph()
    state = _initial_state("ambiguous message")
    result = await graph.ainvoke(state)
    interrupts = result.get("__interrupt__")
    assert interrupts, "Expected the graph to pause via interrupt()"
    payload = getattr(interrupts[0], "value", {})
    reasons = payload.get("trigger_reasons", [])
    assert any(r.startswith("low_confidence") for r in reasons)


@pytest.mark.asyncio
async def test_outage_keyword_escalates_even_with_high_confidence(patch_gateway) -> None:
    patch_gateway(_scripts(category="incident_outage", priority="high", confidence=0.97))
    graph = build_graph()
    state = _initial_state("The platform is down for all users right now")
    result = await graph.ainvoke(state)
    interrupts = result.get("__interrupt__")
    assert interrupts
    reasons = getattr(interrupts[0], "value", {}).get("trigger_reasons", [])
    assert any("keyword_match" in r for r in reasons)


@pytest.mark.asyncio
async def test_billing_threshold_escalates(patch_gateway) -> None:
    patch_gateway(
        _scripts(category="billing_issue", priority="high", confidence=0.95, amounts=[750.0])
    )
    graph = build_graph()
    state = _initial_state("Charged $750 wrongly")
    result = await graph.ainvoke(state)
    interrupts = result.get("__interrupt__")
    assert interrupts
    reasons = getattr(interrupts[0], "value", {}).get("trigger_reasons", [])
    assert any("billing_amount_exceeded" in r for r in reasons)


@pytest.mark.asyncio
async def test_resume_after_human_accept(patch_gateway) -> None:
    """Resume the paused graph with Command(resume=...)."""
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    patch_gateway(_scripts(confidence=0.55, summary="After review summary"))
    cp = MemorySaver()
    graph = build_graph(checkpointer=cp)
    config = {"configurable": {"thread_id": "t-resume"}}

    # First run pauses
    state = _initial_state("ambiguous")
    result = await graph.ainvoke(state, config=config)
    assert "__interrupt__" in result

    # Reviewer accepts
    final_result = await graph.ainvoke(
        Command(resume={"action": "accept", "reviewer": "alice"}),
        config=config,
    )
    assert final_result.get("final") is not None
    final = final_result["final"]
    assert final.handled_by in ("human", "hybrid")


@pytest.mark.asyncio
async def test_resume_after_human_edit_changes_routing(patch_gateway) -> None:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    patch_gateway(_scripts(confidence=0.55, summary="Edited summary"))
    cp = MemorySaver()
    graph = build_graph(checkpointer=cp)
    config = {"configurable": {"thread_id": "t-edit"}}

    state = _initial_state("ambiguous")
    await graph.ainvoke(state, config=config)

    final_result = await graph.ainvoke(
        Command(
            resume={
                "action": "edit",
                "reviewer": "bob",
                "routing": {
                    "queue": "billing",
                    "sla_minutes": 30,
                    "rationale": "human override",
                },
            }
        ),
        config=config,
    )
    final = final_result["final"]
    assert final.routing.queue == "billing"
    assert final.routing.decided_by == "hitl"
    assert final.handled_by == "hybrid"


@pytest.mark.asyncio
async def test_classification_validation_failure_eventually_escalates(monkeypatch) -> None:
    """If classification keeps failing validation, the graph escalates after MAX_ATTEMPTS."""
    from app.graph.nodes import classify

    class BadGateway:
        async def complete_structured(self, **kw):  # noqa: ARG002
            from app.llm.gateway import LLMValidationError

            raise LLMValidationError("model returned garbage")

    monkeypatch.setattr(classify, "get_gateway", lambda: BadGateway())

    # Patch enrich/output too so they don't crash
    from app.graph.nodes import enrich, output as output_node

    class _GoodGateway:
        async def complete_structured(self, *, schema, operation, **kw):  # noqa: ARG002
            if operation == "enrich":
                return EnrichmentResult(issue_summary="x")
            return _Summary(summary="x")

    monkeypatch.setattr(enrich, "get_gateway", lambda: _GoodGateway())
    monkeypatch.setattr(output_node, "get_gateway", lambda: _GoodGateway())

    graph = build_graph()
    result = await graph.ainvoke(_initial_state("garbage in"))
    interrupts = result.get("__interrupt__")
    assert interrupts
    reasons = getattr(interrupts[0], "value", {}).get("trigger_reasons", [])
    assert any("unparseable_llm_output" in r for r in reasons)
