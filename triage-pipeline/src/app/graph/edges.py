"""Deterministic, auditable escalation triggers.

Pure Python, no LLM. The brief calls out three triggers:
  1. confidence < 0.70
  2. keyword match (outage / down for all users / etc.)
  3. billing issue with invoice > $500

Plus one bonus: category=incident_outage always pages.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.schemas.triage import (
    Category,
    ClassificationResult,
    EnrichmentResult,
    Priority,
    Queue,
)

# ---------------------------------------------------------------------------
# Static maps
# ---------------------------------------------------------------------------

CATEGORY_TO_QUEUE: dict[Category, Queue] = {
    "bug_report": "engineering",
    "feature_request": "product",
    "billing_issue": "billing",
    "technical_question": "product",
    "incident_outage": "it_security",
}

SLA_BY_PRIORITY: dict[Priority, int] = {
    "high": 15,
    "medium": 60,
    "low": 240,
}

# ---------------------------------------------------------------------------
# Trigger evaluation
# ---------------------------------------------------------------------------


def evaluate_escalation_triggers(
    *,
    body: str,
    classification: ClassificationResult,
    enrichment: EnrichmentResult | None,
) -> list[str]:
    """Return a list of triggered reasons; empty means no escalation needed."""
    settings = get_settings()
    triggers: list[str] = []
    body_lc = body.lower()

    # Trigger 1: low confidence
    if classification.confidence < settings.escalation_confidence_threshold:
        triggers.append(f"low_confidence={classification.confidence:.2f}")

    # Trigger 2: outage keywords
    matched = [kw for kw in settings.escalation_keywords if kw in body_lc]
    if matched:
        triggers.append(f"keyword_match={','.join(matched)}")

    # Trigger 3: billing threshold
    if classification.category == "billing_issue" and enrichment is not None:
        large = [a for a in enrichment.invoice_amounts_usd if a > settings.escalation_billing_threshold_usd]
        if large:
            triggers.append(
                f"billing_amount_exceeded={max(large):.2f}>"
                f"{settings.escalation_billing_threshold_usd:.0f}"
            )

    # Bonus: incident_outage always pages
    if classification.category == "incident_outage":
        triggers.append("category_incident_outage")

    return triggers


def queue_for(category: Category) -> Queue:
    return CATEGORY_TO_QUEUE.get(category, "fallback")


def sla_for(priority: Priority) -> int:
    return SLA_BY_PRIORITY[priority]
