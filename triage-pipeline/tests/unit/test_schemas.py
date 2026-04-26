"""Unit tests for the Pydantic LLM-output contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.triage import (
    ClassificationResult,
    EnrichmentResult,
    EscalationFlag,
    ExtractedEntity,
    FinalOutput,
    RoutingResult,
)


def test_classification_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        ClassificationResult(
            category="totally_made_up",  # type: ignore[arg-type]
            priority="high",
            confidence=0.9,
            rationale="x",
        )


def test_classification_rejects_confidence_out_of_range() -> None:
    with pytest.raises(ValidationError):
        ClassificationResult(
            category="bug_report", priority="high", confidence=1.5, rationale="x"
        )
    with pytest.raises(ValidationError):
        ClassificationResult(
            category="bug_report", priority="high", confidence=-0.1, rationale="x"
        )


def test_classification_rationale_strip_whitespace() -> None:
    c = ClassificationResult(
        category="bug_report", priority="medium", confidence=0.9,
        rationale="   has whitespace   ",
    )
    assert c.rationale == "has whitespace"


def test_extracted_entity_requires_source_quote() -> None:
    """The anti-hallucination contract: every entity must carry the literal source quote."""
    with pytest.raises(ValidationError):
        ExtractedEntity(value="ORD-1")  # type: ignore[call-arg]


def test_routing_rejects_invalid_queue() -> None:
    with pytest.raises(ValidationError):
        RoutingResult(
            queue="not_a_queue",  # type: ignore[arg-type]
            sla_minutes=10, rationale="x",
        )


def test_routing_sla_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        RoutingResult(queue="engineering", sla_minutes=0, rationale="x")


def test_final_output_round_trip() -> None:
    final = FinalOutput(
        ticket_id="t1",
        message_id="m1",
        source="chat",
        received_at="2026-04-26T00:00:00Z",
        classification=ClassificationResult(
            category="bug_report", priority="medium", confidence=0.9, rationale="x"
        ),
        enrichment=EnrichmentResult(issue_summary="x"),
        routing=RoutingResult(queue="engineering", sla_minutes=60, rationale="x"),
        escalation=EscalationFlag(needs_human=False),
        human_summary="hello",
        handled_by="auto",
        prompt_versions={"classification": "v1#abcd"},
    )
    blob = final.model_dump(mode="json")
    reconstructed = FinalOutput.model_validate(blob)
    assert reconstructed == final


def test_escalation_default_blocking() -> None:
    f = EscalationFlag(needs_human=True, reasons=["low_confidence=0.5"])
    assert f.blocking is True


def test_enrichment_empty_defaults() -> None:
    e = EnrichmentResult(issue_summary="hello")
    assert e.affected_ids == []
    assert e.error_codes == []
    assert e.invoice_amounts_usd == []
    assert e.detected_language == "en"
