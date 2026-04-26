"""Escalation repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.escalation import Escalation


async def create_pending(
    session: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    thread_id: str,
    reasons: list[str],
    payload: dict[str, Any],
    interrupt_id: str | None = None,
) -> Escalation:
    row = Escalation(
        ticket_id=ticket_id,
        thread_id=thread_id,
        status="pending",
        reasons=reasons,
        payload=payload,
        interrupt_id=interrupt_id,
    )
    session.add(row)
    await session.flush()
    return row


async def get(session: AsyncSession, escalation_id: uuid.UUID) -> Escalation | None:
    return await session.get(Escalation, escalation_id)


async def list_pending(
    session: AsyncSession, *, limit: int = 50
) -> list[Escalation]:
    stmt = (
        select(Escalation)
        .where(Escalation.status == "pending")
        .order_by(Escalation.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_pending_for_ticket(
    session: AsyncSession, ticket_id: uuid.UUID
) -> list[Escalation]:
    stmt = (
        select(Escalation)
        .where(Escalation.ticket_id == ticket_id, Escalation.status == "pending")
        .order_by(Escalation.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def resolve(
    session: AsyncSession,
    *,
    escalation_id: uuid.UUID,
    status: str,
    resolution: dict[str, Any],
    resolver: str,
) -> Escalation | None:
    row = await session.get(Escalation, escalation_id)
    if row is None:
        return None
    row.status = status
    row.resolution = resolution
    row.resolved_by = resolver
    row.resolved_at = datetime.now(timezone.utc)
    return row
