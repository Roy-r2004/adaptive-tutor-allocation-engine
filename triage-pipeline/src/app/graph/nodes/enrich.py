"""Step 3 — Enrichment.

Pure extraction: core issue, identifiers, error codes, urgency signals.
Empty result is acceptable; failure routes to escalate.
"""

from __future__ import annotations

from typing import Literal

from langgraph.types import Command

from app.core.logging import get_logger
from app.graph.state import TriageState
from app.llm.gateway import LLMError, LLMValidationError, get_gateway
from app.prompts.registry import get_registry
from app.schemas.triage import EnrichmentResult

logger = get_logger(__name__)

TEMPLATE = "enrichment/extract_v1.j2"


async def enrich(state: TriageState) -> Command[Literal["route", "escalate"]]:
    registry = get_registry()
    prompt = registry.render(TEMPLATE, body=state["body"])
    template_hash = registry.hash(TEMPLATE)

    try:
        result = await get_gateway().complete_structured(
            prompt=prompt,
            schema=EnrichmentResult,
            operation="enrich",
            ticket_id=state.get("ticket_id"),
            tenant_id=state.get("tenant_id", "default"),
            max_retries=1,
        )
        logger.info(
            "graph_node_enrich_ok",
            ticket_id=state.get("ticket_id"),
            ids=len(result.affected_ids),
            errors=len(result.error_codes),
            amounts=result.invoice_amounts_usd,
        )
        prompt_versions = dict(state.get("prompt_versions") or {})
        prompt_versions["enrichment"] = f"v1#sha256:{template_hash[:12]}"
        return Command(
            update={"enrichment": result, "prompt_versions": prompt_versions},
            goto="route",
        )
    except (LLMValidationError, LLMError) as e:
        logger.warning("graph_node_enrich_failed", error=str(e))
        # Enrichment is non-critical: fall through with an empty result rather than escalate.
        empty = EnrichmentResult(issue_summary=state["body"][:200])
        return Command(
            update={
                "enrichment": empty,
                "errors": [f"enrich soft-failed: {e}"],
            },
            goto="route",
        )
