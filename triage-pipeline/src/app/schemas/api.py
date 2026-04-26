"""HTTP API request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.triage import FinalOutput

# ---------------------------------------------------------------------------
# /webhook/ingest
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    source: Literal["chat", "web_form", "email", "api"] = Field(
        description="Inbound channel."
    )
    body: str = Field(min_length=1, max_length=10_000, description="Raw user message.")
    customer_id: str | None = Field(default=None, max_length=64)
    tenant_id: str = Field(default="default", max_length=64)
    extra: dict[str, Any] = Field(default_factory=dict, description="Channel-specific payload.")


class IngestResponse(BaseModel):
    message_id: UUID
    ticket_id: UUID
    job_id: str
    status: str = "queued"


# ---------------------------------------------------------------------------
# /tickets/{id}/status, /tickets/{id}/output
# ---------------------------------------------------------------------------


class TicketStatusResponse(BaseModel):
    ticket_id: UUID
    status: str
    handled_by: str | None = None
    summary: str | None = None
    has_pending_escalation: bool = False
    final_output: FinalOutput | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# /escalations
# ---------------------------------------------------------------------------


class EscalationListItem(BaseModel):
    escalation_id: UUID
    ticket_id: UUID
    status: str
    reasons: list[str]
    payload: dict[str, Any]
    created_at: datetime


class EscalationResolveRequest(BaseModel):
    action: Literal["accept", "edit", "reject"]
    routing: dict[str, Any] | None = None
    reason: str | None = None
    reviewer: str = Field(default="anonymous", max_length=128)


class EscalationResolveResponse(BaseModel):
    escalation_id: UUID
    ticket_id: UUID
    status: str
    resumed: bool
