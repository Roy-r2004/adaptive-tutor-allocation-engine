"""Step 1 — Ingestion endpoint.

Persists the message + ticket in a single transaction, enqueues the triage
job with a deterministic job_id (so retried webhooks deduplicate), and returns
202 Accepted. Never blocks on LLM calls.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.core.logging import get_logger
from app.repositories import audit_repo, ticket_repo
from app.schemas.api import IngestRequest, IngestResponse
from app.workers.queue import enqueue_triage

router = APIRouter(prefix="/webhook", tags=["ingest"])
logger = get_logger(__name__)


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
)
async def ingest(
    payload: IngestRequest,
    request: Request,
    s: AsyncSession = Depends(get_db),
) -> IngestResponse:
    correlation_id = request.headers.get("X-Request-ID") or request.headers.get(
        "x-correlation-id"
    )
    raw_payload = {
        "source": payload.source,
        "body": payload.body,
        "customer_id": payload.customer_id,
        "tenant_id": payload.tenant_id,
        **payload.extra,
    }
    msg, ticket = await ticket_repo.create_message_and_ticket(
        s,
        source=payload.source,
        body=payload.body,
        raw_payload=raw_payload,
        customer_id=payload.customer_id,
        tenant_id=payload.tenant_id,
        correlation_id=correlation_id,
    )
    await audit_repo.record(
        s,
        ticket_id=ticket.id,
        actor="api",
        event="received",
        correlation_id=correlation_id,
        extra={"source": payload.source},
    )
    job_id = await enqueue_triage(ticket_id=str(ticket.id), message_id=str(msg.id))
    logger.info(
        "ingest_accepted",
        ticket_id=str(ticket.id),
        message_id=str(msg.id),
        job_id=job_id,
    )
    return IngestResponse(message_id=msg.id, ticket_id=ticket.id, job_id=job_id)
