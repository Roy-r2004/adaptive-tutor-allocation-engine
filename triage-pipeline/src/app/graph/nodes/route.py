"""Step 4 — Routing decision.

Deterministic mapping of (category, priority) to queue + SLA, plus the three
escalation triggers. Sends to `escalate` if any trigger fires, otherwise `output`.
"""

from __future__ import annotations

from typing import Literal

from langgraph.types import Command

from app.core.logging import get_logger
from app.graph.edges import evaluate_escalation_triggers, queue_for, sla_for
from app.graph.state import TriageState
from app.schemas.triage import EscalationFlag, RoutingResult

logger = get_logger(__name__)


async def route(state: TriageState) -> Command[Literal["escalate", "output"]]:
    classification = state["classification"]
    enrichment = state.get("enrichment")
    if classification is None:
        # Defensive: classify should have set this or routed to escalate.
        return Command(
            update={
                "errors": ["route called without classification"],
                "escalation": EscalationFlag(needs_human=True, reasons=["missing_classification"]),
            },
            goto="escalate",
        )

    queue = queue_for(classification.category)
    sla = sla_for(classification.priority)
    triggers = evaluate_escalation_triggers(
        body=state["body"],
        classification=classification,
        enrichment=enrichment,
    )

    decision = RoutingResult(
        queue=queue,
        sla_minutes=sla,
        rationale=f"category={classification.category}; priority={classification.priority}",
        decided_by="auto",
        needs_human=bool(triggers),
    )

    if triggers:
        logger.info(
            "graph_node_route_escalating",
            ticket_id=state.get("ticket_id"),
            queue=queue,
            triggers=triggers,
        )
        return Command(
            update={
                "routing": decision,
                "escalation": EscalationFlag(
                    needs_human=True, reasons=triggers, blocking=True
                ),
            },
            goto="escalate",
        )

    logger.info(
        "graph_node_route_auto",
        ticket_id=state.get("ticket_id"),
        queue=queue,
        sla_minutes=sla,
    )
    return Command(update={"routing": decision}, goto="output")
