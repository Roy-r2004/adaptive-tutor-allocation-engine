"""LangGraph builder.

Compiles the 6-node triage pipeline. Checkpointer is injected at compile time —
in production it's AsyncPostgresSaver, in tests it's MemorySaver (or omitted).
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.classify import classify
from app.graph.nodes.enrich import enrich
from app.graph.nodes.escalate import escalate
from app.graph.nodes.ingest import ingest
from app.graph.nodes.output import output
from app.graph.nodes.route import route
from app.graph.state import TriageState


def build_graph(checkpointer: Any | None = None) -> Any:
    """Build and compile the triage StateGraph.

    Conditional edges live inside the nodes via Command(goto=...). Static edges
    only handle the entry, the escalate→output continuation, and termination.
    """
    builder = StateGraph(TriageState)

    builder.add_node("ingest", ingest)
    builder.add_node("classify", classify)
    builder.add_node("enrich", enrich)
    builder.add_node("route", route)
    builder.add_node("escalate", escalate)
    builder.add_node("output", output)

    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "classify")
    # classify, enrich, route all return Command(goto=...) — no static edges.
    builder.add_edge("escalate", "output")
    builder.add_edge("output", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()
