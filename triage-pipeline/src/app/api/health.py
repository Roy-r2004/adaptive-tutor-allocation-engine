"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness — no dependencies, just confirms the process is up."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(s: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness — confirms DB is reachable."""
    await s.execute(text("SELECT 1"))
    return {"status": "ready"}
