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
