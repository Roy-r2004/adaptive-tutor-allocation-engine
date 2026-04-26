"""Unit tests for the deterministic escalation triggers (Step 6 of the brief)."""

from __future__ import annotations

import pytest

from app.graph.edges import (
    CATEGORY_TO_QUEUE,
    SLA_BY_PRIORITY,
    evaluate_escalation_triggers,
    queue_for,
    sla_for,
)
from app.schemas.triage import (
    ClassificationResult,
    EnrichmentResult,
    ExtractedEntity,
)


def _cls(category="bug_report", priority="medium", confidence=0.85, rationale="ok") -> ClassificationResult:
    return ClassificationResult(
        category=category, priority=priority, confidence=confidence, rationale=rationale
    )


def _enr(amounts: list[float] | None = None) -> EnrichmentResult:
    return EnrichmentResult(
        issue_summary="x",
        invoice_amounts_usd=amounts or [],
    )


# --- Trigger 1: low confidence -------------------------------------------------


def test_low_confidence_triggers_escalation() -> None:
    triggers = evaluate_escalation_triggers(
        body="some message",
        classification=_cls(confidence=0.55),
        enrichment=_enr(),
    )
    assert any(t.startswith("low_confidence") for t in triggers)


def test_high_confidence_no_escalation() -> None:
    triggers = evaluate_escalation_triggers(
        body="some message",
        classification=_cls(confidence=0.95),
        enrichment=_enr(),
    )
    assert not any(t.startswith("low_confidence") for t in triggers)


def test_confidence_at_threshold_does_not_trigger() -> None:
    """Strictly less-than 0.70 — exactly 0.70 is allowed."""
    triggers = evaluate_escalation_triggers(
        body="some message",
        classification=_cls(confidence=0.70),
        enrichment=_enr(),
    )
    assert not any(t.startswith("low_confidence") for t in triggers)


# --- Trigger 2: keyword matches ------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "we have an outage",
        "platform is down for all users",
        "production down right now",
        "data loss event in progress",
        "looks like a security breach",
    ],
)
def test_keyword_triggers_escalation(phrase: str) -> None:
    triggers = evaluate_escalation_triggers(
        body=phrase,
        classification=_cls(confidence=0.99),
        enrichment=_enr(),
    )
    assert any("keyword_match" in t for t in triggers)


def test_no_keyword_no_escalation() -> None:
    triggers = evaluate_escalation_triggers(
        body="just wondering about pricing",
        classification=_cls(confidence=0.99),
        enrichment=_enr(),
    )
    assert not any("keyword_match" in t for t in triggers)


# --- Trigger 3: billing > $500 -------------------------------------------------


def test_billing_under_threshold_no_escalation() -> None:
    triggers = evaluate_escalation_triggers(
        body="charge of $200",
        classification=_cls(category="billing_issue", confidence=0.99),
        enrichment=_enr(amounts=[200.0]),
    )
    assert not any("billing_amount_exceeded" in t for t in triggers)


def test_billing_over_threshold_triggers() -> None:
    triggers = evaluate_escalation_triggers(
        body="charged $750",
        classification=_cls(category="billing_issue", confidence=0.99),
        enrichment=_enr(amounts=[750.0]),
    )
    assert any("billing_amount_exceeded" in t for t in triggers)


def test_billing_threshold_only_for_billing_category() -> None:
    """A high amount in a non-billing category should not trigger billing rule."""
    triggers = evaluate_escalation_triggers(
        body="something about $750 unrelated",
        classification=_cls(category="bug_report", confidence=0.99),
        enrichment=_enr(amounts=[750.0]),
    )
    assert not any("billing_amount_exceeded" in t for t in triggers)


# --- Bonus: incident_outage always escalates ----------------------------------


def test_incident_category_always_escalates() -> None:
    triggers = evaluate_escalation_triggers(
        body="weird thing happening",
        classification=_cls(category="incident_outage", confidence=0.99),
        enrichment=_enr(),
    )
    assert "category_incident_outage" in triggers


# --- Mappings ------------------------------------------------------------------


def test_category_to_queue_map_complete() -> None:
    """Every category in the schema must have a queue mapping."""
    expected = {"bug_report", "feature_request", "billing_issue", "technical_question", "incident_outage"}
    assert set(CATEGORY_TO_QUEUE.keys()) >= expected


def test_sla_priority_ordering() -> None:
    """high < medium < low (more urgent = lower SLA minutes)."""
    assert SLA_BY_PRIORITY["high"] < SLA_BY_PRIORITY["medium"] < SLA_BY_PRIORITY["low"]


@pytest.mark.parametrize(
    "category,expected_queue",
    [
        ("bug_report", "engineering"),
        ("billing_issue", "billing"),
        ("feature_request", "product"),
        ("technical_question", "product"),
        ("incident_outage", "it_security"),
    ],
)
def test_queue_for_each_category(category: str, expected_queue: str) -> None:
    assert queue_for(category) == expected_queue


def test_sla_for_priority() -> None:
    assert sla_for("high") == 15
    assert sla_for("medium") == 60
    assert sla_for("low") == 240


# --- Multiple triggers stack ---------------------------------------------------


def test_multiple_triggers_all_recorded() -> None:
    triggers = evaluate_escalation_triggers(
        body="production down with $1500 charge",
        classification=_cls(category="billing_issue", confidence=0.55),
        enrichment=_enr(amounts=[1500.0]),
    )
    assert any(t.startswith("low_confidence") for t in triggers)
    assert any("keyword_match" in t for t in triggers)
    assert any("billing_amount_exceeded" in t for t in triggers)
    assert len(triggers) >= 3
