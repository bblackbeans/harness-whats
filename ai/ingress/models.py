from dataclasses import dataclass, field


@dataclass
class InboundEvent:
    phone: str
    text: str
    conversation_id: int
    account_id: int
    inbox_id: int | None = None
    contact_name: str = ""
    message_id: str = ""
    delivery_id: str = ""
    conversation_status: str = ""
    override_agent_id: int | None = None
    override_flow_id: int | None = None
    raw: dict = field(default_factory=dict)
