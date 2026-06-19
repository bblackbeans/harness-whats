from dataclasses import dataclass, field


@dataclass
class InboundEvent:
    phone: str
    text: str
    conversation_id: int
    account_id: int
    contact_name: str = ""
    message_id: str = ""
    delivery_id: str = ""
    raw: dict = field(default_factory=dict)
