"""Step 6 — Human-in-the-loop escalation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.core.logging import get_logger
from app.repositories import audit_repo, escalation_repo
from app.schemas.api import (
    EscalationListItem,
    EscalationResolveRequest,
    EscalationResolveResponse,
)
from app.workers.queue import enqueue_resume

router = APIRouter(prefix="/escalations", tags=["escalations"])
logger = get_logger(__name__)


@router.get(
    "",
    response_model=list[EscalationListItem],
    dependencies=[Depends(require_api_key)],
)
async def list_pending(
    s: AsyncSession = Depends(get_db),
) -> list[EscalationListItem]:
    rows = await escalation_repo.list_pending(s)
    return [
        EscalationListItem(
            escalation_id=row.id,
            ticket_id=row.ticket_id,
            status=row.status,
            reasons=list(row.reasons or []),
            payload=row.payload or {},
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post(
    "/{escalation_id}/resolve",
    response_model=EscalationResolveResponse,
    dependencies=[Depends(require_api_key)],
)
async def resolve(
    escalation_id: uuid.UUID,
    payload: EscalationResolveRequest,
    s: AsyncSession = Depends(get_db),
) -> EscalationResolveResponse:
    row = await escalation_repo.get(s, escalation_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found"
        )
    if row.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Escalation already {row.status}",
        )

    decision = {
        "action": payload.action,
        "routing": payload.routing,
        "reason": payload.reason,
        "reviewer": payload.reviewer,
    }
    new_status = {"accept": "accepted", "edit": "edited", "reject": "rejected"}[payload.action]
    await escalation_repo.resolve(
        s,
        escalation_id=escalation_id,
        status=new_status,
        resolution=decision,
        resolver=payload.reviewer,
    )
    await audit_repo.record(
        s,
        ticket_id=row.ticket_id,
        actor=f"user:{payload.reviewer}",
        event=f"escalation_{new_status}",
        extra={"action": payload.action},
    )
    # Enqueue resume so the graph picks up where it paused.
    await enqueue_resume(
        ticket_id=str(row.ticket_id),
        escalation_id=str(escalation_id),
        decision=decision,
    )
    logger.info(
        "escalation_resolved",
        escalation_id=str(escalation_id),
        action=payload.action,
    )
    return EscalationResolveResponse(
        escalation_id=escalation_id,
        ticket_id=row.ticket_id,
        status=new_status,
        resumed=True,
    )
