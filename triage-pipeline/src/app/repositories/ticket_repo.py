"""Ticket repository — read/write tickets and their child rows."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.message import Message
from app.models.ticket import Classification, Enrichment, RoutingDecision, Ticket
from app.schemas.triage import (
    ClassificationResult,
    EnrichmentResult,
    RoutingResult,
)


async def create_message_and_ticket(
    session: AsyncSession,
    *,
    source: str,
    body: str,
    raw_payload: dict[str, Any],
    customer_id: str | None,
    tenant_id: str,
    correlation_id: str | None,
) -> tuple[Message, Ticket]:
    msg = Message(
        source=source,
        body=body,
        raw_payload=raw_payload,
        customer_id=customer_id,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
    )
    session.add(msg)
    await session.flush()

    ticket = Ticket(message_id=msg.id, tenant_id=tenant_id, status="received")
    session.add(ticket)
    await session.flush()
    return msg, ticket


async def get_ticket(session: AsyncSession, ticket_id: uuid.UUID) -> Ticket | None:
    stmt = (
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.message),
            selectinload(Ticket.classification),
            selectinload(Ticket.enrichment),
            selectinload(Ticket.routing),
            selectinload(Ticket.escalations),
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_ticket_status(
    session: AsyncSession, ticket_id: uuid.UUID, status: str
) -> None:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is not None:
        ticket.status = status


async def upsert_classification(
    session: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    result: ClassificationResult,
    model_used: str | None,
    raw_output: dict[str, Any] | None = None,
) -> None:
    existing = await session.scalar(
        select(Classification).where(Classification.ticket_id == ticket_id)
    )
    if existing is None:
        existing = Classification(ticket_id=ticket_id)
        session.add(existing)
    existing.category = result.category
    existing.priority = result.priority
    existing.confidence = result.confidence
    existing.rationale = result.rationale
    existing.model_used = model_used
    existing.raw_output = raw_output


async def upsert_enrichment(
    session: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    result: EnrichmentResult,
    model_used: str | None,
) -> None:
    existing = await session.scalar(select(Enrichment).where(Enrichment.ticket_id == ticket_id))
    if existing is None:
        existing = Enrichment(ticket_id=ticket_id)
        session.add(existing)
    existing.issue_summary = result.issue_summary
    existing.affected_ids = [e.model_dump() for e in result.affected_ids]
    existing.error_codes = [e.model_dump() for e in result.error_codes]
    existing.invoice_amounts_usd = list(result.invoice_amounts_usd)
    existing.urgency_signals = [e.model_dump() for e in result.urgency_signals]
    existing.detected_language = result.detected_language
    existing.model_used = model_used


async def upsert_routing(
    session: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    result: RoutingResult,
) -> None:
    existing = await session.scalar(
        select(RoutingDecision).where(RoutingDecision.ticket_id == ticket_id)
    )
    if existing is None:
        existing = RoutingDecision(ticket_id=ticket_id)
        session.add(existing)
    existing.queue = result.queue
    existing.sla_minutes = result.sla_minutes
    existing.rationale = result.rationale
    existing.decided_by = result.decided_by
    existing.needs_human = result.needs_human


async def update_final(
    session: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    summary: str,
    final_output: dict[str, Any],
    handled_by: str,
    trace_id: str | None,
    status: str,
) -> None:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        return
    ticket.summary = summary
    ticket.final_output = final_output
    ticket.handled_by = handled_by
    ticket.trace_id = trace_id
    ticket.status = status
