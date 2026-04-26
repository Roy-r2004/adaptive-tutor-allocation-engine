"""Inbound message — the raw payload as it arrived on the webhook."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class JSONBOrJSON(TypeDecorator):  # type: ignore[type-arg]
    """JSONB on Postgres, JSON elsewhere — keeps tests on SQLite working."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class UUIDType(TypeDecorator):  # type: ignore[type-arg]
    """Postgres UUID column that falls back to CHAR(36) on SQLite for tests."""

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class Message(Base):
    """An inbound message awaiting (or finished) triage."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(
        Enum("chat", "web_form", "email", "api", name="message_source"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(String, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONBOrJSON, nullable=False, default=dict)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped["Ticket | None"] = relationship(
        "Ticket", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} source={self.source}>"
