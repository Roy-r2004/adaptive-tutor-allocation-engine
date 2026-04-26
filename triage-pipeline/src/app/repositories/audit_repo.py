"""Audit log writer — append-only."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def record(
    session: AsyncSession,
    *,
    ticket_id: uuid.UUID | None,
    actor: str,
    event: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    trace_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    row = AuditLog(
        ticket_id=ticket_id,
        actor=actor,
        event=event,
        before_state=before,
        after_state=after,
        correlation_id=correlation_id,
        trace_id=trace_id,
        extra=extra,
    )
    session.add(row)
