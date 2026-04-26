"""Tests that run the 5 brief samples and verify the *deterministic* parts of the pipeline.

We mock the LLM with hand-coded "expected" answers per sample, then check that
routing and escalation behave correctly given those classifications. This proves
the graph wiring is right without paying for real LLM calls.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from app.graph import build_graph
from app.graph.nodes import classify, enrich
from app.graph.nodes import output as output_node
from app.schemas.triage import (
    ClassificationResult,
    EnrichmentResult,
    ExtractedEntity,
)


# Hand-labeled "ground truth" responses for the 5 brief samples.
# These are what the LLM SHOULD return for each input.
BRIEF_LABELS = [
    # 1. booking failure — bug, medium
    {
        "category": "bug_report",
        "priority": "medium",
        "confidence": 0.85,
        "queue": "engineering",
        "should_escalate": False,
    },
    # 2. compare tutors — feature request, low
    {
        "category": "feature_request",
        "priority": "low",
        "confidence": 0.93,
        "queue": "product",
        "should_escalate": False,
    },
    # 3. no confirmation email — bug, medium
    {
        "category": "bug_report",
        "priority": "medium",
        "confidence": 0.86,
        "queue": "engineering",
        "should_escalate": False,
    },
    # 4. choosing major — technical question, low
    {
        "category": "technical_question",
        "priority": "low",
        "confidence": 0.81,
        "queue": "product",
        "should_escalate": False,
    },
    # 5. platform not loading, multiple users — incident, HIGH (must escalate)
    {
        "category": "incident_outage",
        "priority": "high",
        "confidence": 0.96,
        "queue": "it_security",
        "should_escalate": True,
    },
]


class _Summary(BaseModel):
    summary: str


def _scripted_gateway(label: dict[str, Any]):
    class G:
        async def complete_structured(self, *, schema, operation, **kw):  # noqa: ARG002
            if operation == "classify":
                return ClassificationResult(
                    category=label["category"],
                    priority=label["priority"],
                    confidence=label["confidence"],
                    rationale="cited words from ticket",
                )
            if operation == "enrich":
                return EnrichmentResult(issue_summary="user issue")
            if operation == "summarize":
                return _Summary(summary=f"Summary for {label['category']}")
            raise AssertionError(f"unexpected op {operation}")

    return G()


@pytest.mark.asyncio
@pytest.mark.parametrize("idx", list(range(5)))
async def test_brief_sample_routing(
    sample_inputs, idx: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = sample_inputs[idx]
    label = BRIEF_LABELS[idx]
    fake = _scripted_gateway(label)
    monkeypatch.setattr(classify, "get_gateway", lambda: fake)
    monkeypatch.setattr(enrich, "get_gateway", lambda: fake)
    monkeypatch.setattr(output_node, "get_gateway", lambda: fake)

    graph = build_graph()
    state = {
        "ticket_id": f"t-{idx}",
        "message_id": f"m-{idx}",
        "body": sample["body"],
        "source": sample["source"],
        "tenant_id": "default",
        "errors": [],
        "prompt_versions": {},
    }
    result = await graph.ainvoke(state)

    if label["should_escalate"]:
        assert "__interrupt__" in result, f"sample {idx + 1} should have escalated"
    else:
        assert result.get("final") is not None, f"sample {idx + 1} should have finalized"
        assert result["final"].routing.queue == label["queue"]
