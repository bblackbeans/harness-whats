from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class HarnessState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    phone: str
    contact_name: str
    conversation_id: int
    account_id: int
    message_id: str
    delivery_id: str
    inbound_text: str
    conversation_summary: str
    semantic_facts: list[str]
    new_semantic_facts: list[str]
    agent_context: str
    intent: str
    should_reply: bool
    outbound_text: str
    lifecycle_status: str
