"""Pydantic models that LLM outputs must conform to.

These are the single source of truth for the JSON schema sent to providers via
`with_structured_output` / Instructor. Keep `Literal` enums; field descriptions
end up in the JSON schema and steer the model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums (Literals)
# ---------------------------------------------------------------------------

Category = Literal[
    "bug_report",
    "feature_request",
    "billing_issue",
    "technical_question",
    "incident_outage",
]

Priority = Literal["low", "medium", "high"]

Queue = Literal["engineering", "billing", "product", "it_security", "fallback"]


# ---------------------------------------------------------------------------
# Step 2: classification
# ---------------------------------------------------------------------------


class ClassificationResult(BaseModel):
    """The classifier's output. Maps directly to the brief's Step 2."""

    category: Category = Field(
        description="One of bug_report, feature_request, billing_issue, technical_question, incident_outage."
    )
    priority: Priority = Field(description="Operational urgency: low, medium, or high.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Self-reported confidence 0..1. Treat as ordinal hint, not probability.",
    )
    rationale: str = Field(
        max_length=400,
        description="<=2 sentences citing concrete words from the ticket. Comes AFTER the label.",
    )

    @field_validator("rationale")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


# ---------------------------------------------------------------------------
# Step 3: enrichment
# ---------------------------------------------------------------------------


class ExtractedEntity(BaseModel):
    """Anti-hallucination wrapper: every entity carries the literal source quote."""

    value: str = Field(description="Normalized value (e.g. 'ORD-12345', 'ERR_CONN_REFUSED').")
    source_quote: str = Field(
        description="Verbatim span from the ticket where this entity was found.",
        max_length=300,
    )


class EnrichmentResult(BaseModel):
    """Step 3: extract structured signals from the unstructured message."""

    issue_summary: str = Field(
        max_length=300, description="Single-sentence statement of what the user wants or hit."
    )
    affected_ids: list[ExtractedEntity] = Field(
        default_factory=list,
        description="IDs mentioned: order, account, session, ticket, etc.",
    )
    error_codes: list[ExtractedEntity] = Field(
        default_factory=list,
        description="Stack-trace tokens, HTTP error codes, system-emitted error strings.",
    )
    invoice_amounts_usd: list[float] = Field(
        default_factory=list,
        description="Dollar amounts mentioned in a billing context. Normalized to USD floats.",
    )
    urgency_signals: list[ExtractedEntity] = Field(
        default_factory=list,
        description="Phrases conveying urgency: 'right now', 'production', 'all users', etc.",
    )
    detected_language: str = Field(default="en", description="ISO 639-1 code.")


# ---------------------------------------------------------------------------
# Step 4: routing
# ---------------------------------------------------------------------------


class RoutingResult(BaseModel):
    queue: Queue
    sla_minutes: int = Field(ge=1, description="Time to first human response based on priority.")
    rationale: str = Field(max_length=400)
    decided_by: Literal["auto", "hitl"] = "auto"
    needs_human: bool = False


# ---------------------------------------------------------------------------
# Step 6: escalation flag
# ---------------------------------------------------------------------------


class EscalationFlag(BaseModel):
    needs_human: bool = False
    reasons: list[str] = Field(default_factory=list, description="Trigger reasons, e.g. 'low_confidence=0.62'.")
    blocking: bool = True
    proposed_reviewer: str | None = None


# ---------------------------------------------------------------------------
# Step 5: final structured output (the deliverable JSON)
# ---------------------------------------------------------------------------


class FinalOutput(BaseModel):
    """The single JSON record that gets exported per the brief."""

    ticket_id: str
    message_id: str
    source: str
    received_at: str
    classification: ClassificationResult
    enrichment: EnrichmentResult
    routing: RoutingResult
    escalation: EscalationFlag
    human_summary: str = Field(
        max_length=600,
        description="2–3 sentence summary suitable for a triage agent at-a-glance.",
    )
    handled_by: Literal["auto", "human", "hybrid"] = "auto"
    prompt_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Map of step name → prompt version hash, for reproducibility.",
    )
    trace_id: str | None = None
