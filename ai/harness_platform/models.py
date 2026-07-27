from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from harness_platform.db import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="super_admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="pt-BR")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    prompts: Mapped[list["TenantPrompt"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    allowed_models: Mapped[list["TenantAllowedModel"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantPrompt(Base):
    __tablename__ = "tenant_prompts"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_tenant_prompt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")

    tenant: Mapped["Tenant"] = relationship(back_populates="prompts")


class LlmProvider(Base):
    __tablename__ = "llm_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), default="openai")
    encrypted_api_key: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    models: Mapped[list["LlmModel"]] = relationship(back_populates="provider", cascade="all, delete-orphan")


class LlmModel(Base):
    __tablename__ = "llm_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("llm_providers.id", ondelete="CASCADE"))
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cost_per_1m_input: Mapped[float] = mapped_column(Float, default=0.0)
    cost_per_1m_output: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_default: Mapped[float] = mapped_column(Float, default=0.3)

    provider: Mapped["LlmProvider"] = relationship(back_populates="models")


class TenantAllowedModel(Base):
    __tablename__ = "tenant_allowed_models"
    __table_args__ = (UniqueConstraint("tenant_id", "model_id", name="uq_tenant_model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("llm_models.id", ondelete="CASCADE"))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="allowed_models")
    model: Mapped["LlmModel"] = relationship()


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    model_ref: Mapped[str] = mapped_column(String(128), default="")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    limits: Mapped[dict] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("plans.id", ondelete="RESTRICT"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan: Mapped["Plan"] = relationship()


class TenantUser(Base):
    __tablename__ = "tenant_users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_tenant_user_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelChangeRequest(Base):
    __tablename__ = "model_change_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_model_id: Mapped[int] = mapped_column(Integer, ForeignKey("llm_models.id"))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Problema(Base):
    __tablename__ = "problemas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=True
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    passos: Mapped[str] = mapped_column(Text, default="")
    origem: Mapped[str] = mapped_column(String(32), default="feedback")
    status: Mapped[str] = mapped_column(String(32), default="novo")
    url: Mapped[str] = mapped_column(String(2048), default="")
    correlation_id: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()))
    contexto_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    notas_internas: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship()
    usuario: Mapped["TenantUser | None"] = relationship()


class TenantCustomField(Base):
    __tablename__ = "tenant_custom_fields"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_tenant_custom_field_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), default="text")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContactProfile(Base):
    __tablename__ = "contact_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "phone", name="uq_contact_tenant_phone"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    chatwoot_contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantInboundWebhook(Base):
    __tablename__ = "tenant_inbound_webhooks"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_tenant_webhook_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    field_mapping: Mapped[dict] = mapped_column(JSONB, default=dict)
    start_conversation: Mapped[bool] = mapped_column(Boolean, default=False)
    initial_message: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantHttpTool(Base):
    __tablename__ = "tenant_http_tools"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_tenant_http_tool_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    method: Mapped[str] = mapped_column(String(16), default="POST")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    body_template: Mapped[str] = mapped_column(Text, default="")
    include_fields: Mapped[list] = mapped_column(JSONB, default=list)
    auth_header: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantSendableFile(Base):
    __tablename__ = "tenant_sendable_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantAgent(Base):
    __tablename__ = "tenant_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(String(32), default="specialist")  # orchestrator | specialist
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    flows: Mapped[list["Flow"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    tool_bindings: Mapped[list["AgentToolBinding"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    tools: Mapped[list["AgentTool"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class AgentToolBinding(Base):
    __tablename__ = "agent_tool_bindings"
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_kind", "tool_ref", name="uq_agent_tool_binding"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant_agents.id", ondelete="CASCADE"))
    tool_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_ref: Mapped[str] = mapped_column(String(128), default="*")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped["TenantAgent"] = relationship(back_populates="tool_bindings")


class AgentTool(Base):
    """Tool editável por agente: regras + endpoint (quando HTTP)."""

    __tablename__ = "agent_tools"
    __table_args__ = (UniqueConstraint("agent_id", "slug", name="uq_agent_tool_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant_agents.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="http")
    rules: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str] = mapped_column(String(16), default="POST")
    url: Mapped[str] = mapped_column(Text, default="")
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    body_template: Mapped[str] = mapped_column(Text, default="")
    auth_header: Mapped[str] = mapped_column(String(512), default="")
    # Para kind=send_file: lista de TenantSendableFile.id; vazio = todos os arquivos do tenant
    file_ids: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent: Mapped["TenantAgent"] = relationship(back_populates="tools")


class Flow(Base):
    __tablename__ = "flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant_agents.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    base_prompt: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    source_filename: Mapped[str] = mapped_column(String(255), default="")
    source_raw: Mapped[str] = mapped_column(Text, default="")
    import_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    roteiro: Mapped[dict] = mapped_column(JSONB, default=dict)
    checklist: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent: Mapped["TenantAgent"] = relationship(back_populates="flows")
    runs: Mapped[list["FlowRun"]] = relationship(back_populates="flow", cascade="all, delete-orphan")


class FlowRun(Base):
    __tablename__ = "flow_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "conversation_id", "flow_id", name="uq_flow_run_conversation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"))
    flow_id: Mapped[int] = mapped_column(Integer, ForeignKey("flows.id", ondelete="CASCADE"))
    conversation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), default="")
    checklist_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    current_step_id: Mapped[str] = mapped_column(String(128), default="")
    variables: Mapped[dict] = mapped_column(JSONB, default=dict)
    tools_log: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    flow: Mapped["Flow"] = relationship(back_populates="runs")
