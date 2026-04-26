"""Helper that records every LLM call to the llm_calls table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.llm_call import LLMCall

logger = get_logger(__name__)


async def record_llm_call(
    session: AsyncSession,
    *,
    ticket_id: uuid.UUID | None,
    tenant_id: str,
    operation: str,
    provider: str,
    model: str,
    prompt_version_id: uuid.UUID | None,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float,
    latency_ms: int,
    outcome: str,
    error: str | None,
    request: dict[str, Any] | None,
    response: dict[str, Any] | None,
    trace_id: str | None = None,
) -> None:
    row = LLMCall(
        ticket_id=ticket_id,
        tenant_id=tenant_id,
        operation=operation,
        provider=provider,
        model=model,
        prompt_version_id=prompt_version_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        outcome=outcome,
        error=error,
        request=request,
        response=response,
        trace_id=trace_id,
    )
    session.add(row)
    # Caller's session_scope will commit
