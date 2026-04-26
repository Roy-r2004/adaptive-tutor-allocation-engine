"""Step 1 — Ingestion.

The HTTP layer has already persisted the message and ticket. This node simply
seeds the graph state with the right fields. Splitting it out keeps the graph
self-explanatory: 6 nodes for 6 steps.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.graph.state import TriageState

logger = get_logger(__name__)


async def ingest(state: TriageState) -> dict[str, object]:
    logger.info(
        "graph_node_ingest",
        ticket_id=state.get("ticket_id"),
        source=state.get("source"),
        body_len=len(state.get("body", "")),
    )
    return {
        "classify_attempts": 0,
        "enrich_attempts": 0,
        "errors": [],
        "prompt_versions": {},
        "handled_by": "auto",
    }
