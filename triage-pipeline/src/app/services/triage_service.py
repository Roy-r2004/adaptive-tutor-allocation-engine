"""Triage service — runs the LangGraph and persists results.

Called by:
  - The Arq worker for normal ingest (graph.ainvoke from a fresh state)
  - The Arq worker for resume after escalation (graph.ainvoke with Command(resume=...))

Persists classification, enrichment, routing, and final output in a single
transaction per super-step boundary.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.logging import get_logger
from app.graph import build_graph
from app.repositories import audit_repo, escalation_repo, ticket_repo
from app.schemas.triage import FinalOutput

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Graph + checkpointer lifecycle
# ---------------------------------------------------------------------------

# In production we use AsyncPostgresSaver; in dev/test, MemorySaver is sufficient.
# This keeps the test suite trivial to set up while documenting the prod path.

_compiled_graph: Any | None = None
_checkpointer: Any | None = None
_lock = asyncio.Lock()


@asynccontextmanager
async def _ensure_graph() -> AsyncIterator[Any]:
    """Lazily build the graph + checkpointer the first time it's needed.

    The Postgres checkpointer is backed by an ``AsyncConnectionPool`` rather
    than a single long-lived connection, so idle/dropped connections recycle
    transparently — without this the worker would die on the first stale
    connection and every subsequent job would fail with
    ``psycopg.OperationalError: the connection is closed``.
    """
    global _compiled_graph, _checkpointer
    async with _lock:
        if _compiled_graph is None:
            settings = get_settings()
            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                from psycopg.rows import dict_row
                from psycopg_pool import AsyncConnectionPool

                pg_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
                pool = AsyncConnectionPool(
                    conninfo=pg_dsn,
                    max_size=10,
                    min_size=1,
                    open=False,
                    kwargs={
                        "autocommit": True,
                        "prepare_threshold": 0,
                        "row_factory": dict_row,
                    },
                )
                await pool.open(wait=True)
                _checkpointer = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
                await _checkpointer.setup()
                logger.info("checkpointer_ready", backend="postgres-pool")
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "postgres_checkpointer_unavailable_using_memory",
                    error=str(e),
                )
                _checkpointer = MemorySaver()
            _compiled_graph = build_graph(checkpointer=_checkpointer)
    try:
        yield _compiled_graph
    finally:
        # Long-lived graph; nothing to do per-request.
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_triage(*, ticket_id: uuid.UUID, message_id: uuid.UUID) -> dict[str, Any]:
    """Execute the graph for a freshly-ingested ticket. May pause on interrupt()."""
    async with session_scope() as s:
        ticket = await ticket_repo.get_ticket(s, ticket_id)
        if ticket is None:
            raise RuntimeError(f"Ticket {ticket_id} not found")
        msg = ticket.message
        body = msg.body
        source = msg.source
        tenant_id = ticket.tenant_id
        correlation_id = msg.correlation_id

    initial_state: dict[str, Any] = {
        "ticket_id": str(ticket_id),
        "message_id": str(message_id),
        "body": body,
        "source": source,
        "tenant_id": tenant_id,
        "correlation_id": correlation_id,
        "errors": [],
        "prompt_versions": {},
    }

    config = {"configurable": {"thread_id": str(ticket_id)}}

    async with _ensure_graph() as graph:
        result = await graph.ainvoke(initial_state, config=config)

    return await _post_run(result=result, ticket_id=ticket_id, thread_id=str(ticket_id))


async def resume_triage(
    *, ticket_id: uuid.UUID, escalation_id: uuid.UUID, decision: dict[str, Any]
) -> dict[str, Any]:
    """Resume a paused graph after a human resolves an escalation."""
    config = {"configurable": {"thread_id": str(ticket_id)}}
    async with _ensure_graph() as graph:
        result = await graph.ainvoke(Command(resume=decision), config=config)

    return await _post_run(result=result, ticket_id=ticket_id, thread_id=str(ticket_id))


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


async def _post_run(
    *, result: dict[str, Any], ticket_id: uuid.UUID, thread_id: str
) -> dict[str, Any]:
    """Persist results from a graph run. Detects pause-on-interrupt."""
    # When an interrupt occurs, LangGraph's ainvoke returns the partial state
    # and includes "__interrupt__" in the result with the payload.
    interrupts = result.get("__interrupt__")
    if interrupts:
        await _persist_interrupt(result, ticket_id, thread_id, interrupts)
        return {
            "status": "awaiting_review",
            "interrupts": [getattr(i, "value", i) for i in interrupts],
        }

    # Normal completion
    await _persist_completion(result, ticket_id)
    final = result.get("final")
    return {
        "status": "resolved",
        "final": final.model_dump(mode="json") if final else None,
    }


async def _persist_interrupt(
    result: dict[str, Any],
    ticket_id: uuid.UUID,
    thread_id: str,
    interrupts: list[Any],
) -> None:
    interrupt_obj = interrupts[0]
    payload = getattr(interrupt_obj, "value", {}) or {}
    interrupt_id = getattr(interrupt_obj, "id", None)

    classification = result.get("classification")
    enrichment = result.get("enrichment")
    routing = result.get("routing")
    escalation = result.get("escalation")

    async with session_scope() as s:
        if classification is not None:
            await ticket_repo.upsert_classification(
                s,
                ticket_id=ticket_id,
                result=classification,
                model_used=None,
            )
        if enrichment is not None:
            await ticket_repo.upsert_enrichment(
                s, ticket_id=ticket_id, result=enrichment, model_used=None
            )
        if routing is not None:
            await ticket_repo.upsert_routing(s, ticket_id=ticket_id, result=routing)

        await escalation_repo.create_pending(
            s,
            ticket_id=ticket_id,
            thread_id=thread_id,
            reasons=(escalation.reasons if escalation else []),
            payload=payload,
            interrupt_id=str(interrupt_id) if interrupt_id else None,
        )
        await ticket_repo.update_ticket_status(s, ticket_id, "awaiting_review")
        await audit_repo.record(
            s,
            ticket_id=ticket_id,
            actor="system",
            event="awaiting_review",
            extra={"reasons": payload.get("trigger_reasons", [])},
        )


async def _persist_completion(result: dict[str, Any], ticket_id: uuid.UUID) -> None:
    classification = result.get("classification")
    enrichment = result.get("enrichment")
    routing = result.get("routing")
    final: FinalOutput | None = result.get("final")

    async with session_scope() as s:
        if classification is not None:
            await ticket_repo.upsert_classification(
                s,
                ticket_id=ticket_id,
                result=classification,
                model_used=None,
            )
        if enrichment is not None:
            await ticket_repo.upsert_enrichment(
                s, ticket_id=ticket_id, result=enrichment, model_used=None
            )
        if routing is not None:
            await ticket_repo.upsert_routing(s, ticket_id=ticket_id, result=routing)

        if final is not None:
            await ticket_repo.update_final(
                s,
                ticket_id=ticket_id,
                summary=final.human_summary,
                final_output=final.model_dump(mode="json"),
                handled_by=final.handled_by,
                trace_id=final.trace_id,
                status="resolved",
            )

        await audit_repo.record(
            s,
            ticket_id=ticket_id,
            actor="system",
            event="resolved",
            extra={"handled_by": final.handled_by if final else "auto"},
        )
