"""Pydantic v2 schemas — API I/O and the LLM-output contracts."""

from app.schemas.api import (
    EscalationListItem,
    EscalationResolveRequest,
    EscalationResolveResponse,
    IngestRequest,
    IngestResponse,
    TicketStatusResponse,
)
from app.schemas.triage import (
    Category,
    ClassificationResult,
    EnrichmentResult,
    EscalationFlag,
    ExtractedEntity,
    FinalOutput,
    Priority,
    Queue,
    RoutingResult,
)

__all__ = [
    "Category",
    "ClassificationResult",
    "EnrichmentResult",
    "EscalationFlag",
    "EscalationListItem",
    "EscalationResolveRequest",
    "EscalationResolveResponse",
    "ExtractedEntity",
    "FinalOutput",
    "IngestRequest",
    "IngestResponse",
    "Priority",
    "Queue",
    "RoutingResult",
    "TicketStatusResponse",
]
