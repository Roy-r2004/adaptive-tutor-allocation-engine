"""Step 5 — Structured output.

Calls the summarization prompt to produce the human_summary, assembles the
FinalOutput, and stores it on state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.graph.state import TriageState
from app.llm.gateway import LLMError, LLMValidationError, get_gateway
from app.prompts.registry import get_registry
from app.schemas.triage import EscalationFlag, FinalOutput
from pydantic import BaseModel

logger = get_logger(__name__)


class _SummaryOnly(BaseModel):
    summary: str


async def output(state: TriageState) -> dict[str, Any]:
    classification = state["classification"]
    enrichment = state.get("enrichment")
    routing = state["routing"]
    escalation = state.get("escalation") or EscalationFlag(needs_human=False)
    if classification is None or routing is None:
        raise RuntimeError("output called with incomplete state")

    summary_text = await _make_summary(state)

    handled_by_value = state.get("handled_by", "auto")
    if handled_by_value not in ("auto", "human", "hybrid"):
        handled_by_value = "auto"

    final = FinalOutput(
        ticket_id=str(state.get("ticket_id", "")),
        message_id=str(state.get("message_id", "")),
        source=str(state.get("source", "chat")),
        received_at=datetime.now(timezone.utc).isoformat(),
        classification=classification,
        enrichment=enrichment
        or _empty_enrichment(state["body"]),
        routing=routing,
        escalation=escalation,
        human_summary=summary_text,
        handled_by=handled_by_value,  # type: ignore[arg-type]
        prompt_versions=state.get("prompt_versions") or {},
        trace_id=state.get("correlation_id"),
    )

    return {
        "final": final,
        "output_dict": final.model_dump(mode="json"),
    }


async def _make_summary(state: TriageState) -> str:
    classification = state["classification"]
    routing = state["routing"]
    enrichment = state.get("enrichment")
    if classification is None or routing is None:
        return state["body"][:300]

    registry = get_registry()
    template = "summarization/summary_v1.j2"
    prompt = registry.render(
        template,
        body=state["body"],
        category=classification.category,
        priority=classification.priority,
        queue=routing.queue,
        issue_summary=(enrichment.issue_summary if enrichment else state["body"][:200]),
        affected_ids=[e.value for e in (enrichment.affected_ids if enrichment else [])],
        invoice_amounts_usd=(enrichment.invoice_amounts_usd if enrichment else []),
    )
    try:
        result = await get_gateway().complete_structured(
            prompt=prompt,
            schema=_SummaryOnly,
            operation="summarize",
            ticket_id=state.get("ticket_id"),
            tenant_id=state.get("tenant_id", "default"),
            max_retries=1,
        )
        return result.summary.strip()
    except (LLMValidationError, LLMError) as e:
        logger.warning("graph_node_summary_failed", error=str(e))
        # Deterministic fallback summary
        return _fallback_summary(state)


def _fallback_summary(state: TriageState) -> str:
    cls = state["classification"]
    routing = state["routing"]
    if cls is None or routing is None:
        return state["body"][:300]
    return (
        f"{cls.category.replace('_', ' ').title()} reported via {state.get('source','chat')}, "
        f"priority {cls.priority}, routed to {routing.queue} "
        f"(SLA {routing.sla_minutes}m). Original message: \"{state['body'][:160]}\""
    )


def _empty_enrichment(body: str) -> Any:
    from app.schemas.triage import EnrichmentResult

    return EnrichmentResult(issue_summary=body[:200])
