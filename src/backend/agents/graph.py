"""LangGraph wiring for the Agentic Financial Auditor.

State machine (mirrors DocState):

    preprocess ──► ocr ──► auditor ──┐
                                     ├─► persist ──► END     (valid)
                                     ├─► reconciler ──► auditor  (retry)
                                     └─► persist ──► END     (hitl)

    preprocess ──► persist ──► END (preprocessing failed; tier=hitl)

Retry cap is MAX_RECONCILE_ATTEMPTS. When attempts >= cap OR
`state.tier == "hitl"` (Gemini unavailable / no image), the auditor router
sends the graph to persist with status=FLAGGED.
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from src.backend.agents.nodes import (
    auditor_node,
    ocr_node,
    persist_node,
    preprocess_node,
    reconciler_node,
)
from src.backend.agents.state import AgentState

MAX_RECONCILE_ATTEMPTS = 3


def _route_after_preprocess(state: AgentState) -> Literal["ocr", "persist"]:
    # Pages were produced → continue. Otherwise preprocess failed (tier=hitl);
    # short-circuit to persist so the failure is logged and the DB row closes.
    return "ocr" if state.pages else "persist"


def _route_after_auditor(state: AgentState) -> Literal["valid", "retry", "hitl"]:
    if state.is_valid:
        return "valid"
    # tier=hitl is set by reconciler_node on VLM unavailability / no-image —
    # honor it immediately rather than burning retry budget.
    if state.tier == "hitl":
        return "hitl"
    if state.attempts >= MAX_RECONCILE_ATTEMPTS:
        return "hitl"
    return "retry"


def build_graph(
    preprocess_fn=None,
    ocr_fn=None,
    auditor_fn=None,
    reconciler_fn=None,
    persist_fn=None,
):
    """Build and compile the agentic pipeline graph.

    Each node has an optional override so tests can substitute stubs for the
    external-dependency-heavy nodes (preprocess, persist) without needing a
    live filesystem or database. Production callers pass no arguments.
    """
    g = StateGraph(AgentState)
    g.add_node("preprocess", preprocess_fn or preprocess_node)
    g.add_node("ocr", ocr_fn or ocr_node)
    g.add_node("auditor", auditor_fn or auditor_node)
    g.add_node("reconciler", reconciler_fn or reconciler_node)
    g.add_node("persist", persist_fn or persist_node)

    g.set_entry_point("preprocess")
    g.add_conditional_edges(
        "preprocess",
        _route_after_preprocess,
        {"ocr": "ocr", "persist": "persist"},
    )
    g.add_edge("ocr", "auditor")
    g.add_conditional_edges(
        "auditor",
        _route_after_auditor,
        {"valid": "persist", "retry": "reconciler", "hitl": "persist"},
    )
    g.add_edge("reconciler", "auditor")
    g.add_edge("persist", END)

    return g.compile()


# Module-level compiled graph for production use. Tests should call
# build_graph() with their own stubs rather than mutating this instance.
compiled_graph = build_graph()
