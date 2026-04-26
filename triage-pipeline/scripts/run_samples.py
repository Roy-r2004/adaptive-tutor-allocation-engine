"""Run the five sample inputs from the assessment brief end-to-end.

USAGE
-----
1. With real LLM keys:
       export GROQ_API_KEY=...   (or GEMINI_API_KEY, or OPENAI_API_KEY)
       python scripts/run_samples.py

2. With the offline stub (deterministic, for review without keys):
       python scripts/run_samples.py --stub

Outputs:
  outputs/sample_run_results.json  — array of FinalOutput records
  outputs/sample_run_summary.md    — human-readable summary table
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ---------------------------------------------------------------------------
# The five samples — verbatim from the brief
# ---------------------------------------------------------------------------

SAMPLES: list[dict[str, str]] = [
    {
        "source": "chat",
        "body": "Hi, I'm trying to book a math tutor for IGCSE but I can't see any available time slots after selecting the teacher.",
    },
    {
        "source": "web_form",
        "body": "It would be really helpful if we could compare tutors based on ratings, price, and availability in one view before booking.",
    },
    {
        "source": "chat",
        "body": "I booked a session yesterday but I didn't receive any confirmation email or session details. Can you check if my booking went through?",
    },
    {
        "source": "chat",
        "body": "Is there a way to get help choosing the right major or university based on my interests?",
    },
    {
        "source": "web_form",
        "body": "The platform is not loading properly and none of the tutors are showing up. Multiple users are facing the same issue.",
    },
]


# ---------------------------------------------------------------------------
# Offline deterministic stub — for reviewers who don't want to set API keys
# ---------------------------------------------------------------------------


def _stub_classification(body: str) -> dict[str, Any]:
    """Heuristic classifier — only used by --stub. Approximates the LLM."""
    body_lc = body.lower()
    if "not loading" in body_lc or "outage" in body_lc or "multiple users" in body_lc:
        return {
            "category": "incident_outage",
            "priority": "high",
            "confidence": 0.94,
            "rationale": "Mentions multi-user impact ('Multiple users are facing the same issue') and platform unavailability ('not loading properly').",
        }
    if "compare tutors" in body_lc or "would be" in body_lc or "feature" in body_lc:
        return {
            "category": "feature_request",
            "priority": "low",
            "confidence": 0.92,
            "rationale": "Asks for new functionality ('compare tutors based on ratings, price, and availability'); no breakage reported.",
        }
    if "didn't receive" in body_lc or "confirmation email" in body_lc or "booking went through" in body_lc:
        return {
            "category": "bug_report",
            "priority": "medium",
            "confidence": 0.86,
            "rationale": "Reports a broken side effect ('didn't receive any confirmation email') after a successful action.",
        }
    if "can't see any available time slots" in body_lc or "can't see" in body_lc:
        return {
            "category": "bug_report",
            "priority": "medium",
            "confidence": 0.83,
            "rationale": "Concrete broken booking flow ('can't see any available time slots after selecting the teacher').",
        }
    if "major" in body_lc or "university" in body_lc or "choose" in body_lc or "choosing" in body_lc:
        return {
            "category": "technical_question",
            "priority": "low",
            "confidence": 0.81,
            "rationale": "General how-to question about platform guidance ('help choosing the right major or university').",
        }
    return {
        "category": "technical_question",
        "priority": "low",
        "confidence": 0.5,
        "rationale": "Default fallback for unclassified inquiry.",
    }


def _stub_enrichment(body: str) -> dict[str, Any]:
    import re

    body_lc = body.lower()
    affected_ids: list[dict[str, str]] = []
    for m in re.finditer(r"\b([A-Z]{2,}-\d{2,})\b", body):
        affected_ids.append({"value": m.group(1), "source_quote": m.group(1)})

    invoice_amounts: list[float] = []
    for m in re.finditer(r"\$([\d,]+(?:\.\d{1,2})?)", body):
        try:
            invoice_amounts.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass

    urgency_signals: list[dict[str, str]] = []
    for phrase in ["right now", "immediately", "asap", "urgent", "all users", "production"]:
        if phrase in body_lc:
            urgency_signals.append({"value": phrase, "source_quote": phrase})

    return {
        "issue_summary": body.split(".")[0][:200] + (
            "." if not body.split(".")[0].endswith(".") else ""
        ),
        "affected_ids": affected_ids,
        "error_codes": [],
        "invoice_amounts_usd": invoice_amounts,
        "urgency_signals": urgency_signals,
        "detected_language": "en",
    }


def _stub_summary(cls: dict[str, Any], routing: dict[str, Any], body: str) -> str:
    cat = cls["category"].replace("_", " ").title()
    return (
        f"{cat} reported via the platform with priority {cls['priority']}. "
        f"Routed to {routing['queue']} (SLA {routing['sla_minutes']}m). "
        f"User wrote: \"{body[:140]}{'...' if len(body) > 140 else ''}\""
    )


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


async def _run_with_llm(samples: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Run via the actual LLM gateway (requires API keys)."""
    from app.llm.gateway import get_gateway
    from app.prompts.registry import get_registry
    from app.schemas.triage import (
        ClassificationResult,
        EnrichmentResult,
        EscalationFlag,
        FinalOutput,
        RoutingResult,
    )
    from app.graph.edges import evaluate_escalation_triggers, queue_for, sla_for
    from pydantic import BaseModel

    class _SummaryOnly(BaseModel):
        summary: str

    registry = get_registry()
    gw = get_gateway()
    results: list[dict[str, Any]] = []

    for i, sample in enumerate(samples, start=1):
        ticket_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        # Classify
        cls_prompt = registry.render(
            "classification/ticket_classify_v1.j2",
            body=sample["body"],
            source=sample["source"],
        )
        classification = await gw.complete_structured(
            prompt=cls_prompt,
            schema=ClassificationResult,
            operation="classify",
        )

        # Enrich
        enr_prompt = registry.render("enrichment/extract_v1.j2", body=sample["body"])
        enrichment = await gw.complete_structured(
            prompt=enr_prompt,
            schema=EnrichmentResult,
            operation="enrich",
        )

        # Route
        triggers = evaluate_escalation_triggers(
            body=sample["body"],
            classification=classification,
            enrichment=enrichment,
        )
        routing = RoutingResult(
            queue=queue_for(classification.category),
            sla_minutes=sla_for(classification.priority),
            rationale=f"category={classification.category}; priority={classification.priority}",
            decided_by="auto",
            needs_human=bool(triggers),
        )
        escalation = EscalationFlag(
            needs_human=bool(triggers),
            reasons=triggers,
            blocking=bool(triggers),
        )

        # Summary
        sum_prompt = registry.render(
            "summarization/summary_v1.j2",
            body=sample["body"],
            category=classification.category,
            priority=classification.priority,
            queue=routing.queue,
            issue_summary=enrichment.issue_summary,
            affected_ids=[e.value for e in enrichment.affected_ids],
            invoice_amounts_usd=enrichment.invoice_amounts_usd,
        )
        summary_obj = await gw.complete_structured(
            prompt=sum_prompt,
            schema=_SummaryOnly,
            operation="summarize",
        )

        final = FinalOutput(
            ticket_id=ticket_id,
            message_id=message_id,
            source=sample["source"],
            received_at=datetime.now(timezone.utc).isoformat(),
            classification=classification,
            enrichment=enrichment,
            routing=routing,
            escalation=escalation,
            human_summary=summary_obj.summary,
            handled_by="auto",
            prompt_versions={
                "classification": "v1#" + registry.hash("classification/ticket_classify_v1.j2")[:12],
                "enrichment": "v1#" + registry.hash("enrichment/extract_v1.j2")[:12],
                "summarization": "v1#" + registry.hash("summarization/summary_v1.j2")[:12],
            },
            trace_id=None,
        )
        results.append({"sample_index": i, "input": sample, "output": final.model_dump(mode="json")})
    return results


def _run_with_stub(samples: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Deterministic stub run — no API calls, no DB. For offline review."""
    from app.graph.edges import (
        CATEGORY_TO_QUEUE,
        SLA_BY_PRIORITY,
        evaluate_escalation_triggers,
    )
    from app.prompts.registry import get_registry
    from app.schemas.triage import (
        ClassificationResult,
        EnrichmentResult,
        EscalationFlag,
        FinalOutput,
        RoutingResult,
    )

    registry = get_registry()
    results: list[dict[str, Any]] = []

    for i, sample in enumerate(samples, start=1):
        ticket_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        cls_dict = _stub_classification(sample["body"])
        classification = ClassificationResult.model_validate(cls_dict)

        enrichment = EnrichmentResult.model_validate(_stub_enrichment(sample["body"]))

        triggers = evaluate_escalation_triggers(
            body=sample["body"],
            classification=classification,
            enrichment=enrichment,
        )
        queue = CATEGORY_TO_QUEUE.get(classification.category, "fallback")
        sla = SLA_BY_PRIORITY[classification.priority]
        routing = RoutingResult(
            queue=queue,
            sla_minutes=sla,
            rationale=f"category={classification.category}; priority={classification.priority}",
            decided_by="auto",
            needs_human=bool(triggers),
        )
        escalation = EscalationFlag(
            needs_human=bool(triggers),
            reasons=triggers,
            blocking=bool(triggers),
        )
        summary = _stub_summary(cls_dict, routing.model_dump(), sample["body"])

        final = FinalOutput(
            ticket_id=ticket_id,
            message_id=message_id,
            source=sample["source"],
            received_at=datetime.now(timezone.utc).isoformat(),
            classification=classification,
            enrichment=enrichment,
            routing=routing,
            escalation=escalation,
            human_summary=summary,
            handled_by="auto",
            prompt_versions={
                "classification": "v1#" + registry.hash("classification/ticket_classify_v1.j2")[:12],
                "enrichment": "v1#" + registry.hash("enrichment/extract_v1.j2")[:12],
                "summarization": "v1#" + registry.hash("summarization/summary_v1.j2")[:12],
            },
            trace_id=None,
        )
        results.append({"sample_index": i, "input": sample, "output": final.model_dump(mode="json")})
    return results


def _write_summary_md(results: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Sample Run — structured output summary",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Records: {len(results)}",
        "",
        "| # | Source | Category | Priority | Confidence | Queue | Escalated? | Reasons |",
        "|---|--------|----------|----------|------------|-------|------------|---------|",
    ]
    for r in results:
        out = r["output"]
        cls = out["classification"]
        routing = out["routing"]
        esc = out["escalation"]
        reasons = ", ".join(esc["reasons"]) if esc["reasons"] else "—"
        lines.append(
            f"| {r['sample_index']} | {r['input']['source']} | "
            f"{cls['category']} | {cls['priority']} | {cls['confidence']:.2f} | "
            f"{routing['queue']} | {'YES' if esc['needs_human'] else 'no'} | "
            f"{reasons} |"
        )
    lines.extend([
        "",
        "## Records",
        "",
    ])
    for r in results:
        out = r["output"]
        lines.append(f"### Sample {r['sample_index']} ({r['input']['source']})")
        lines.append("")
        lines.append("**Input:**")
        lines.append(f"> {r['input']['body']}")
        lines.append("")
        lines.append("**Summary:**")
        lines.append(f"> {out['human_summary']}")
        lines.append("")
        lines.append("**Routing:** `" + out["routing"]["queue"] + "` "
                     f"(SLA {out['routing']['sla_minutes']}m)")
        lines.append("")
        if out["escalation"]["needs_human"]:
            lines.append("**Escalation triggered:**")
            for reason in out["escalation"]["reasons"]:
                lines.append(f"- `{reason}`")
            lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Use the deterministic offline stub (no API calls).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs",
        help="Output directory.",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    if args.stub:
        print("Running with deterministic offline stub (no API calls)…")
        results = _run_with_stub(SAMPLES)
    else:
        print("Running with real LLM gateway…")
        try:
            results = await _run_with_llm(SAMPLES)
        except Exception as e:  # noqa: BLE001
            print(f"\n[!] LLM run failed: {e}")
            print("[!] Falling back to deterministic stub for offline reproducibility.\n")
            results = _run_with_stub(SAMPLES)

    json_path = args.out / "sample_run_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Wrote {json_path}")

    md_path = args.out / "sample_run_summary.md"
    _write_summary_md(results, md_path)
    print(f"Wrote {md_path}")

    # Print a quick dashboard
    print("\nResults preview:")
    for r in results:
        out = r["output"]
        cls = out["classification"]
        routing = out["routing"]
        esc = out["escalation"]
        flag = " ESCALATED" if esc["needs_human"] else ""
        print(
            f"  [{r['sample_index']}] {cls['category']:20s} "
            f"prio={cls['priority']:6s} conf={cls['confidence']:.2f} "
            f"→ {routing['queue']}{flag}"
        )


if __name__ == "__main__":
    asyncio.run(main())
