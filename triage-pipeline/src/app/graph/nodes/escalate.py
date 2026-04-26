"""Step 6 — Human escalation.

Calls `interrupt()` to pause the graph mid-execution. The state is checkpointed
to Postgres; the graph resumes only when the API receives an escalation
resolution (POST /escalations/{id}/resolve).

Crucial: side effects must come AFTER `interrupt()`. On resume the entire node
re-executes from the top until it hits the interrupt again.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.core.logging import get_logger
from app.graph.state import TriageState
from app.schemas.triage import RoutingResult

logger = get_logger(__name__)


async def escalate(state: TriageState) -> dict[str, Any]:
    classification = state.get("classification")
    routing = state.get("routing")
    escalation = state.get("escalation")

    payload: dict[str, Any] = {
        "type": "review_required",
        "ticket_id": state.get("ticket_id"),
        "body": state.get("body"),
        "source": state.get("source"),
        "classification": classification.model_dump() if classification else None,
        "routing": routing.model_dump() if routing else None,
        "trigger_reasons": (escalation.reasons if escalation else []),
        "actions_allowed": ["accept", "edit", "reject"],
    }

    logger.info(
        "graph_node_escalate_interrupt",
        ticket_id=state.get("ticket_id"),
        reasons=payload["trigger_reasons"],
    )

    # The graph pauses here. On resume, `decision` is the value supplied to Command(resume=...).
    decision: dict[str, Any] = interrupt(payload)

    action = (decision or {}).get("action", "accept")
    logger.info(
        "graph_node_escalate_resumed",
        ticket_id=state.get("ticket_id"),
        action=action,
    )

    update: dict[str, Any] = {"handled_by": "human"}

    if action == "accept":
        # Human approved the auto-routing — keep it as-is, mark non-blocking.
        if state.get("escalation") is not None:
            ec = state["escalation"].model_copy(update={"blocking": False})  # type: ignore[union-attr]
            update["escalation"] = ec
    elif action == "edit":
        # Human supplied a new routing payload.
        new_routing = decision.get("routing") or {}
        if routing is not None:
            merged = {**routing.model_dump(), **new_routing, "decided_by": "hitl"}
        else:
            merged = {**new_routing, "decided_by": "hitl"}
        update["routing"] = RoutingResult.model_validate(merged)
        if state.get("escalation") is not None:
            update["escalation"] = state["escalation"].model_copy(  # type: ignore[union-attr]
                update={"blocking": False}
            )
        update["handled_by"] = "hybrid"
    elif action == "reject":
        # Human rejects auto-handling: leave blocking=True so output node knows.
        if state.get("escalation") is not None:
            reasons = list(state["escalation"].reasons)  # type: ignore[union-attr]
            reasons.append(f"hitl_rejected:{decision.get('reason', 'no_reason')}")
            update["escalation"] = state["escalation"].model_copy(  # type: ignore[union-attr]
                update={"blocking": True, "reasons": reasons}
            )

    return update
