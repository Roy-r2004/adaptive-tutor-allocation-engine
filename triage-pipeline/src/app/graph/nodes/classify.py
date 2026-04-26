"""Step 2 — Classification.

Calls the LLM gateway with the classification schema. Retries on
ValidationError up to 3 times via a self-loop, then routes to escalate.
"""

from __future__ import annotations

from typing import Literal

from langgraph.types import Command

from app.core.logging import get_logger
from app.graph.state import TriageState
from app.llm.gateway import LLMError, LLMValidationError, get_gateway
from app.prompts.registry import get_registry
from app.schemas.triage import ClassificationResult, EscalationFlag

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
TEMPLATE = "classification/ticket_classify_v1.j2"


async def classify(
    state: TriageState,
) -> Command[Literal["enrich", "escalate", "classify"]]:
    attempts = state.get("classify_attempts", 0)
    registry = get_registry()
    prompt = registry.render(
        TEMPLATE,
        body=state["body"],
        source=state.get("source", "chat"),
    )
    template_hash = registry.hash(TEMPLATE)

    try:
        result = await get_gateway().complete_structured(
            prompt=prompt,
            schema=ClassificationResult,
            operation="classify",
            ticket_id=state.get("ticket_id"),
            tenant_id=state.get("tenant_id", "default"),
            max_retries=1,
        )
        logger.info(
            "graph_node_classify_ok",
            ticket_id=state.get("ticket_id"),
            category=result.category,
            priority=result.priority,
            confidence=result.confidence,
        )
        prompt_versions = dict(state.get("prompt_versions") or {})
        prompt_versions["classification"] = f"v1#sha256:{template_hash[:12]}"
        return Command(
            update={
                "classification": result,
                "prompt_versions": prompt_versions,
            },
            goto="enrich",
        )
    except LLMValidationError as ve:
        attempts += 1
        logger.warning(
            "graph_node_classify_validation_error",
            attempts=attempts,
            error=str(ve),
        )
        if attempts >= MAX_ATTEMPTS:
            return Command(
                update={
                    "errors": [f"classify validation failed after {attempts} attempts: {ve}"],
                    "escalation": EscalationFlag(
                        needs_human=True,
                        reasons=["unparseable_llm_output"],
                        blocking=True,
                    ),
                },
                goto="escalate",
            )
        return Command(update={"classify_attempts": attempts}, goto="classify")
    except LLMError as e:
        logger.error("graph_node_classify_llm_error", error=str(e))
        return Command(
            update={
                "errors": [f"classify LLM error: {e}"],
                "escalation": EscalationFlag(
                    needs_human=True,
                    reasons=["llm_provider_unavailable"],
                    blocking=True,
                ),
            },
            goto="escalate",
        )
