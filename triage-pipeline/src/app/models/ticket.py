"""Ticket and its three child rows: classification, enrichment, routing decision.

The ticket is the canonical entity that's referenced from the audit log and the
final JSON output. One ticket per message; one classification/enrichment/routing per ticket.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.message import JSONBOrJSON, UUIDType

if TYPE_CHECKING:
    from app.models.escalation import Escalation
    from app.models.message import Message


class Ticket(Base):
    """The triage-pipeline view of an inbound message."""

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "received",
            "classified",
            "enriched",
            "routed",
            "awaiting_review",
            "resolved",
            "failed",
            name="ticket_status",
        ),
        nullable=False,
        default="received",
        index=True,
    )
    handled_by: Mapped[str | None] = mapped_column(
        Enum("auto", "human", "hybrid", name="ticket_handled_by"),
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    final_output: Mapped[dict[str, Any] | None] = mapped_column(JSONBOrJSON, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    message: Mapped["Message"] = relationship("Message", back_populates="ticket")
    classification: Mapped["Classification | None"] = relationship(
        "Classification", back_populates="ticket", uselist=False, cascade="all, delete-orphan"
    )
    enrichment: Mapped["Enrichment | None"] = relationship(
        "Enrichment", back_populates="ticket", uselist=False, cascade="all, delete-orphan"
    )
    routing: Mapped["RoutingDecision | None"] = relationship(
        "RoutingDecision",
        back_populates="ticket",
        uselist=False,
        cascade="all, delete-orphan",
    )
    escalations: Mapped[list["Escalation"]] = relationship(
        "Escalation", back_populates="ticket", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} status={self.status}>"


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    category: Mapped[str] = mapped_column(
        Enum(
            "bug_report",
            "feature_request",
            "billing_issue",
            "technical_question",
            "incident_outage",
            name="ticket_category",
        ),
        nullable=False,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", name="ticket_priority"),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("prompt_versions.id"), nullable=True
    )
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(JSONBOrJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="classification")


class Enrichment(Base):
    __tablename__ = "enrichments"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    issue_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    affected_ids: Mapped[list[Any]] = mapped_column(JSONBOrJSON, nullable=False, default=list)
    error_codes: Mapped[list[Any]] = mapped_column(JSONBOrJSON, nullable=False, default=list)
    invoice_amounts_usd: Mapped[list[float]] = mapped_column(
        JSONBOrJSON, nullable=False, default=list
    )
    urgency_signals: Mapped[list[Any]] = mapped_column(JSONBOrJSON, nullable=False, default=list)
    detected_language: Mapped[str | None] = mapped_column(String(8), nullable=True, default="en")
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(JSONBOrJSON, nullable=True)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("prompt_versions.id"), nullable=True
    )
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="enrichment")


class RoutingDecision(Base):
    __tablename__ = "routing_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    queue: Mapped[str] = mapped_column(
        Enum(
            "engineering",
            "billing",
            "product",
            "it_security",
            "fallback",
            name="routing_queue",
        ),
        nullable=False,
        index=True,
    )
    sla_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    decided_by: Mapped[str] = mapped_column(
        Enum("auto", "hitl", name="routing_decided_by"),
        nullable=False,
        default="auto",
    )
    needs_human: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="routing")
