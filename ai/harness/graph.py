from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    ingest_message,
    load_semantic_memory,
    manage_context,
    persist_semantic_memory,
    retrieve_knowledge,
    run_agent,
)
from harness.handoff import execute_handoff
from harness.outbound import send_reply
from harness.state import HarnessState
from ingress.models import InboundEvent

_checkpointer = MemorySaver()
_graph = None


def _route_after_reply(state: HarnessState) -> str:
    if state.get("handoff_to_human"):
        return "execute_handoff"
    return END


def _route_after_persist(state: HarnessState) -> str:
    if state.get("should_reply") and state.get("outbound_text"):
        return "send_reply"
    if state.get("handoff_to_human"):
        return "execute_handoff"
    return END


def build_graph():
    builder = StateGraph(HarnessState)

    builder.add_node("load_memory", load_semantic_memory)
    builder.add_node("ingest", ingest_message)
    builder.add_node("manage_context", manage_context)
    builder.add_node("retrieve_knowledge", retrieve_knowledge)
    builder.add_node("agent", run_agent)
    builder.add_node("persist_memory", persist_semantic_memory)
    builder.add_node("send_reply", send_reply)
    builder.add_node("execute_handoff", execute_handoff)

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "ingest")
    builder.add_edge("ingest", "manage_context")
    builder.add_edge("manage_context", "retrieve_knowledge")
    builder.add_edge("retrieve_knowledge", "agent")
    builder.add_edge("agent", "persist_memory")
    builder.add_conditional_edges(
        "persist_memory",
        _route_after_persist,
        {"send_reply": "send_reply", "execute_handoff": "execute_handoff", END: END},
    )
    builder.add_conditional_edges(
        "send_reply",
        _route_after_reply,
        {"execute_handoff": "execute_handoff", END: END},
    )
    builder.add_edge("execute_handoff", END)

    return builder.compile(checkpointer=_checkpointer)


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
