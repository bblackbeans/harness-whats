from typing import Any

from pydantic import BaseModel, Field


class RoutingSettings(BaseModel):
    chatwoot_account_ids: list[int] = Field(default_factory=list)
    chatwoot_inbox_ids: list[int] = Field(default_factory=list)
    chatwoot_bot_token: str | None = None


class ModelSettings(BaseModel):
    name: str = "gpt-4o-mini"
    temperature: float = 0.3
    llm_model_id: int | None = None


class ContextSettings(BaseModel):
    summarize_after: int = 12
    keep_recent: int = 6


class RagSettings(BaseModel):
    enabled: bool = True
    top_k: int = 5
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 500
    chunk_overlap: int = 50


class HandoffSettings(BaseModel):
    enabled: bool = True
    message: str = (
        "Vou encaminhar você para um atendente humano. Aguarde um momento, por favor."
    )
    keywords: list[str] = Field(
        default_factory=lambda: ["atendente", "humano", "pessoa", "falar com alguém", "falar com alguem"]
    )
    on_no_knowledge: bool = True
    private_note_enabled: bool = True
    resume_bot_on_resolve: bool = True
    handoff_label: str = "humano"


class TenantSettings(BaseModel):
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    rag: RagSettings = Field(default_factory=RagSettings)
    handoff: HandoffSettings = Field(default_factory=HandoffSettings)


class PortalUserOnCreate(BaseModel):
    email: str
    password: str
    name: str = ""


class TenantCreate(BaseModel):
    id: str
    name: str
    language: str = "pt-BR"
    active: bool = True
    settings: TenantSettings = Field(default_factory=TenantSettings)
    prompts: dict[str, str] = Field(default_factory=dict)
    portal_user: PortalUserOnCreate | None = None


class TenantUpdate(BaseModel):
    name: str | None = None
    language: str | None = None
    active: bool | None = None
    settings: TenantSettings | None = None
    prompts: dict[str, str] | None = None


class TenantResponse(BaseModel):
    id: str
    name: str
    language: str
    active: bool
    settings: dict[str, Any]
    prompts: dict[str, str]

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PromptUpdate(BaseModel):
    content: str


class LlmProviderCreate(BaseModel):
    name: str
    provider_type: str = "openai"
    api_key: str


class LlmModelCreate(BaseModel):
    provider_id: int
    model_id: str
    display_name: str
    cost_per_1m_input: float = 0.15
    cost_per_1m_output: float = 0.60
    temperature_default: float = 0.3


class LlmProviderUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    active: bool | None = None


class LlmModelUpdate(BaseModel):
    provider_id: int | None = None
    display_name: str | None = None
    model_id: str | None = None
    cost_per_1m_input: float | None = None
    cost_per_1m_output: float | None = None
    temperature_default: float | None = None


class TenantModelsUpdate(BaseModel):
    model_ids: list[int]
    default_model_id: int | None = None


class PlanCreate(BaseModel):
    slug: str
    name: str
    description: str = ""
    limits: dict = Field(default_factory=dict)


class PlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    limits: dict | None = None
    active: bool | None = None


class AssignPlanRequest(BaseModel):
    plan_id: int


class TenantUserCreate(BaseModel):
    email: str
    password: str
    name: str = ""


class ModelChangeRequestCreate(BaseModel):
    requested_model_id: int
    reason: str = ""


class ProblemaFeedbackCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field(..., min_length=1, max_length=8000)
    passos: str = Field(default="", max_length=8000)
    correlation_id: str | None = None
    contexto: dict[str, Any] = Field(default_factory=dict)


class ProblemaUpdate(BaseModel):
    status: str | None = None
    notas_internas: str | None = None


class ProblemaResponse(BaseModel):
    id: str
    tenant_id: str
    tenant_name: str = ""
    usuario_id: int | None = None
    usuario_email: str = ""
    usuario_name: str = ""
    titulo: str
    descricao: str
    passos: str
    origem: str
    status: str
    url: str
    correlation_id: str
    contexto_json: dict[str, Any]
    notas_internas: str
    criado_em: str
    atualizado_em: str
    tem_screenshot: bool = False
    tem_gravacao: bool = False

    model_config = {"from_attributes": True}


class ProblemaFeedbackResponse(BaseModel):
    id: str
    correlation_id: str


class CustomFieldCreate(BaseModel):
    key: str
    label: str
    field_type: str = "text"
    required: bool = False
    sort_order: int = 0


class CustomFieldUpdate(BaseModel):
    label: str | None = None
    field_type: str | None = None
    required: bool | None = None
    sort_order: int | None = None


class ContactUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    fields: dict[str, Any] | None = None


class ContactCreate(BaseModel):
    phone: str
    name: str = ""
    email: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class InboundWebhookCreate(BaseModel):
    name: str
    slug: str | None = None
    field_mapping: dict[str, str] = Field(default_factory=dict)
    start_conversation: bool = False
    initial_message: str = ""
    active: bool = True


class InboundWebhookUpdate(BaseModel):
    name: str | None = None
    field_mapping: dict[str, str] | None = None
    start_conversation: bool | None = None
    initial_message: str | None = None
    active: bool | None = None


class HttpToolCreate(BaseModel):
    name: str
    slug: str | None = None
    method: str = "POST"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    body_template: str = ""
    include_fields: list[str] = Field(default_factory=list)
    auth_header: str = ""
    description: str = ""
    active: bool = True


class HttpToolUpdate(BaseModel):
    name: str | None = None
    method: str | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    body_template: str | None = None
    include_fields: list[str] | None = None
    auth_header: str | None = None
    description: str | None = None
    active: bool | None = None


class SendableFileUpdate(BaseModel):
    description: str = ""


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    role: str = "specialist"
    is_default: bool = False
    active: bool = True


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    role: str | None = None
    is_default: bool | None = None
    active: bool | None = None


class AgentToolBindingItem(BaseModel):
    tool_kind: str
    tool_ref: str = "*"


class AgentToolBindingsUpdate(BaseModel):
    bindings: list[AgentToolBindingItem] = Field(default_factory=list)


class AgentToolCreate(BaseModel):
    agent_id: int
    name: str
    slug: str = ""
    kind: str = "instruction"
    rules: str = ""
    method: str = "POST"
    url: str = ""
    headers: dict[str, Any] = Field(default_factory=dict)
    body_template: str = ""
    auth_header: str = ""
    file_ids: list[int] = Field(default_factory=list)
    active: bool = True


class AgentToolUpdate(BaseModel):
    agent_id: int | None = None
    name: str | None = None
    slug: str | None = None
    kind: str | None = None
    rules: str | None = None
    method: str | None = None
    url: str | None = None
    headers: dict[str, Any] | None = None
    body_template: str | None = None
    auth_header: str | None = None
    file_ids: list[int] | None = None
    active: bool | None = None


class FlowCreate(BaseModel):
    name: str
    agent_id: int | None = None
    description: str = ""
    base_prompt: str = ""
    status: str = "draft"
    is_default: bool = False


class FlowUpdate(BaseModel):
    name: str | None = None
    agent_id: int | None = None
    description: str | None = None
    base_prompt: str | None = None
    status: str | None = None
    is_default: bool | None = None
    roteiro: dict[str, Any] | None = None
    checklist: list[Any] | None = None
    import_summary: dict[str, Any] | None = None

