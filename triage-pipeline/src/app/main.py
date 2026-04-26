"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.health import router as health_router
from app.api.v1.escalations import router as escalations_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.tickets import router as tickets_router
from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.logging import configure_logging, get_logger
from app.observability.metrics import (
    HTTP_REQUESTS,
    HTTP_REQUEST_DURATION,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks."""
    configure_logging()
    logger = get_logger(__name__)
    logger.info("application_startup", env=get_settings().env)
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Triage Pipeline",
        version="0.1.0",
        description="AI-powered intake & triage pipeline — Apex AI assessment.",
        lifespan=lifespan,
    )

    # Middleware order matters. Onion model executes LIFO, so add outer-most last.
    app.add_middleware(GZipMiddleware, minimum_size=512)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")

    # Routers
    app.include_router(health_router)
    app.include_router(ingest_router, prefix=settings.api_v1_prefix)
    app.include_router(tickets_router, prefix=settings.api_v1_prefix)
    app.include_router(escalations_router, prefix=settings.api_v1_prefix)

    # Prometheus
    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Lightweight HTTP metrics middleware (no OTel hard dep)
    @app.middleware("http")
    async def _track_metrics(request, call_next):  # type: ignore[no-untyped-def]
        import time as _t

        start = _t.perf_counter()
        response = await call_next(request)
        elapsed = _t.perf_counter() - start
        try:
            HTTP_REQUESTS.labels(
                method=request.method,
                path=request.url.path,
                status=str(response.status_code),
            ).inc()
            HTTP_REQUEST_DURATION.labels(
                method=request.method, path=request.url.path
            ).observe(elapsed)
        except Exception:  # noqa: BLE001
            pass
        return response

    # Optional: OTel auto-instrumentation if endpoint configured
    if settings.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception:  # noqa: BLE001
            pass

    return app


app = create_app()
