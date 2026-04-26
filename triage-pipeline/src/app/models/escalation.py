"""Escalation — a pending human-in-the-loop review request."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.message import JSONBOrJSON, UUIDType

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Escalation(Base):
    __tablename__ = "escalations"
    __table_args__ = (
        # Partial-style index for the typical query: list pending escalations newest first
        Index("ix_escalations_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "accepted",
            "edited",
            "rejected",
            "expired",
            name="escalation_status",
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    reasons: Mapped[list[str]] = mapped_column(JSONBOrJSON, nullable=False, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONBOrJSON, nullable=False, default=dict)
    interrupt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposed_reviewer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution: Mapped[dict[str, Any] | None] = mapped_column(JSONBOrJSON, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="escalations")
