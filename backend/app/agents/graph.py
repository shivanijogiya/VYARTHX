"""Graph abstraction: uses LangGraph when installed, otherwise a tiny built-in state-graph with the same API.
`GRAPH_ENGINE` tells the UI which one is running (shown honestly in the Agent Activity Centre)."""
from __future__ import annotations

from typing import Any, Callable

try:  # pragma: no cover - exercised implicitly
    from langgraph.graph import END, START, StateGraph  # type: ignore

    GRAPH_ENGINE = "langgraph"
except Exception:  # pragma: no cover
    GRAPH_ENGINE = "builtin-fallback"
    START, END = "__start__", "__end__"

    class _Compiled:
        def __init__(self, nodes, edges, cond, entry):
            self.nodes, self.edges, self.cond, self.entry = nodes, edges, cond, entry

        def invoke(self, state: dict) -> dict:
            cur, guard = self.entry, 0
            while cur != END and guard < 50:
                upd = self.nodes[cur](state) or {}
                state = {**state, **upd}
                if cur in self.cond:
                    cur = self.cond[cur](state)
                else:
                    cur = self.edges.get(cur, END)
                guard += 1
            return state

    class StateGraph:  # type: ignore
        def __init__(self, _schema: Any = None):
            self.nodes: dict[str, Callable] = {}
            self.edges: dict[str, str] = {}
            self.cond: dict[str, Callable] = {}
            self.entry: str | None = None

        def add_node(self, name: str, fn: Callable) -> None:
            self.nodes[name] = fn

        def add_edge(self, a: str, b: str) -> None:
            if a == START:
                self.entry = b
            else:
                self.edges[a] = b

        def add_conditional_edges(self, a: str, fn: Callable, _mapping: Any = None) -> None:
            self.cond[a] = fn

        def compile(self) -> _Compiled:
            return _Compiled(self.nodes, self.edges, self.cond, self.entry)

__all__ = ["StateGraph", "START", "END", "GRAPH_ENGINE"]
