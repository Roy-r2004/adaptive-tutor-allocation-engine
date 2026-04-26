"""Arq queue helpers and the WorkerSettings entry point.

Two tasks:
  - triage_message(ticket_id, message_id) — initial run of the graph
  - resume_graph(ticket_id, escalation_id, decision) — resume after HITL

Job IDs are deterministic so retried webhooks dedupe.
"""

from __future__ import annotations

import uuid
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Enqueue helpers
# ---------------------------------------------------------------------------


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(str(get_settings().redis_url))


async def enqueue_triage(*, ticket_id: str, message_id: str) -> str:
    """Submit an initial triage job. Idempotent on ticket_id."""
    pool = await create_pool(_redis_settings())
    try:
        job = await pool.enqueue_job(
            "triage_message",
            ticket_id,
            message_id,
            _job_id=f"triage:{ticket_id}",
        )
        return job.job_id if job else f"triage:{ticket_id}"
    finally:
        await pool.close()


async def enqueue_resume(
    *, ticket_id: str, escalation_id: str, decision: dict[str, Any]
) -> str:
    pool = await create_pool(_redis_settings())
    try:
        job = await pool.enqueue_job(
            "resume_graph",
            ticket_id,
            escalation_id,
            decision,
            _job_id=f"resume:{escalation_id}",
        )
        return job.job_id if job else f"resume:{escalation_id}"
    finally:
        await pool.close()


# ---------------------------------------------------------------------------
# Worker tasks
# ---------------------------------------------------------------------------


async def triage_message(ctx: dict[str, Any], ticket_id: str, message_id: str) -> dict[str, Any]:
    from app.services.triage_service import run_triage

    logger.info("worker_triage_start", ticket_id=ticket_id, message_id=message_id)
    result = await run_triage(
        ticket_id=uuid.UUID(ticket_id),
        message_id=uuid.UUID(message_id),
    )
    logger.info("worker_triage_done", ticket_id=ticket_id, status=result.get("status"))
    return result


async def resume_graph(
    ctx: dict[str, Any],
    ticket_id: str,
    escalation_id: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    from app.services.triage_service import resume_triage

    logger.info("worker_resume_start", ticket_id=ticket_id, escalation_id=escalation_id)
    result = await resume_triage(
        ticket_id=uuid.UUID(ticket_id),
        escalation_id=uuid.UUID(escalation_id),
        decision=decision,
    )
    logger.info("worker_resume_done", ticket_id=ticket_id, status=result.get("status"))
    return result


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------


async def on_startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    logger.info("worker_startup", env=get_settings().env)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    from app.core.db import dispose_engine

    await dispose_engine()
    logger.info("worker_shutdown")


class WorkerSettings:
    """Arq worker entry point. Run with: arq app.workers.queue.WorkerSettings"""

    # arq reads ``WorkerSettings.redis_settings`` directly off the class, so it
    # has to be a concrete ``RedisSettings`` instance — a ``property`` returns
    # the descriptor object, not the value, which crashes the worker.
    redis_settings = _redis_settings()
    functions = [triage_message, resume_graph]
    on_startup = on_startup  # type: ignore[assignment]
    on_shutdown = on_shutdown  # type: ignore[assignment]
    max_jobs = get_settings().worker_max_jobs
    job_timeout = get_settings().worker_job_timeout
    max_tries = get_settings().worker_max_tries
    health_check_interval = 30
