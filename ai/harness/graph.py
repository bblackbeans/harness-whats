from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    ingest_message,
    load_semantic_memory,
    manage_context,
    persist_semantic_memory,
    run_agent,
)
from harness.outbound import send_reply
from harness.state import HarnessState
from ingress.models import InboundEvent

_checkpointer = MemorySaver()
_graph = None


def _route_after_agent(state: HarnessState) -> str:
    if state.get("should_reply") and state.get("outbound_text"):
        return "send_reply"
    return END


def build_graph():
    builder = StateGraph(HarnessState)

    builder.add_node("load_memory", load_semantic_memory)
    builder.add_node("ingest", ingest_message)
    builder.add_node("manage_context", manage_context)
    builder.add_node("agent", run_agent)
    builder.add_node("persist_memory", persist_semantic_memory)
    builder.add_node("send_reply", send_reply)

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "ingest")
    builder.add_edge("ingest", "manage_context")
    builder.add_edge("manage_context", "agent")
    builder.add_edge("agent", "persist_memory")
    builder.add_conditional_edges(
        "persist_memory",
        _route_after_agent,
        {"send_reply": "send_reply", END: END},
    )
    builder.add_edge("send_reply", END)

    return builder.compile(checkpointer=_checkpointer)


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
