"""Ticket status / final-output endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.repositories import escalation_repo, ticket_repo
from app.schemas.api import TicketStatusResponse
from app.schemas.triage import FinalOutput

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get(
    "/{ticket_id}",
    response_model=TicketStatusResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_ticket(
    ticket_id: uuid.UUID, s: AsyncSession = Depends(get_db)
) -> TicketStatusResponse:
    ticket = await ticket_repo.get_ticket(s, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    pending = await escalation_repo.list_pending_for_ticket(s, ticket_id)
    final_output: FinalOutput | None = None
    if ticket.final_output:
        final_output = FinalOutput.model_validate(ticket.final_output)

    return TicketStatusResponse(
        ticket_id=ticket.id,
        status=ticket.status,
        handled_by=ticket.handled_by,
        summary=ticket.summary,
        has_pending_escalation=bool(pending),
        final_output=final_output,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )
