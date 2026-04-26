"""LangGraph state schema.

TypedDict for the graph state itself (fast serialization into the checkpointer)
and Pydantic for the LLM output contracts (validation where it matters).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any

from typing_extensions import TypedDict

from app.schemas.triage import (
    ClassificationResult,
    EnrichmentResult,
    EscalationFlag,
    FinalOutput,
    RoutingResult,
)


class TriageState(TypedDict, total=False):
    """The graph's working state. Persisted at every super-step by the checkpointer."""

    # ---- input ----
    ticket_id: str
    message_id: str
    body: str
    source: str
    customer_id: str | None
    tenant_id: str
    correlation_id: str | None

    # ---- intermediate ----
    classification: ClassificationResult | None
    enrichment: EnrichmentResult | None
    routing: RoutingResult | None
    escalation: EscalationFlag | None

    # ---- bookkeeping ----
    classify_attempts: int
    enrich_attempts: int
    errors: Annotated[list[str], add]
    prompt_versions: dict[str, str]
    handled_by: str

    # ---- output ----
    final: FinalOutput | None
    output_dict: dict[str, Any] | None
