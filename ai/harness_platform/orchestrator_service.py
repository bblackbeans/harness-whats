"""Orquestrador sticky + allowlist de tools por agente."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session

from agent.llm import get_llm, log_llm_usage
from harness_platform.contact_service import get_contact_by_phone, update_contact, upsert_contact
from harness_platform.models import AgentToolBinding, TenantAgent
from tenants import get_tenant

logger = logging.getLogger(__name__)

ROLE_ORCHESTRATOR = "orchestrator"
ROLE_SPECIALIST = "specialist"

BUILTIN_KINDS = ("save_field", "send_file", "handoff", "transfer_agent")

_DEFAULT_ORCHESTRATOR_PROMPT = (
    "Você é o orquestrador de atendimento.\n"
    "Analise a mensagem do cliente e escolha o agente especializado mais adequado.\n"
    "Responda APENAS com JSON válido (sem markdown):\n"
    '{"agent_id": <número>, "reason": "<motivo curto>"}\n'
    "Escolha somente entre os agentes listados. Se estiver em dúvida, prefira o agente padrão/geral."
)

ACTIVE_AGENT_KEY = "_active_agent_id"
ACTIVE_CONV_KEY = "_active_agent_conversation_id"


def ensure_orchestrator(db: Session, tenant_id: str) -> TenantAgent:
    row = (
        db.query(TenantAgent)
        .filter(
            TenantAgent.tenant_id == tenant_id,
            TenantAgent.role == ROLE_ORCHESTRATOR,
            TenantAgent.active.is_(True),
        )
        .first()
    )
    if row:
        return row
    row = (
        db.query(TenantAgent)
        .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.role == ROLE_ORCHESTRATOR)
        .first()
    )
    if row:
        row.active = True
        db.commit()
        db.refresh(row)
        return row
    row = TenantAgent(
        tenant_id=tenant_id,
        name="Orquestrador Principal",
        description="Roteia a conversa para o agente especializado",
        system_prompt=_DEFAULT_ORCHESTRATOR_PROMPT,
        role=ROLE_ORCHESTRATOR,
        is_default=False,
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_specialists(db: Session, tenant_id: str, *, active_only: bool = True) -> list[TenantAgent]:
    q = db.query(TenantAgent).filter(
        TenantAgent.tenant_id == tenant_id,
        TenantAgent.role == ROLE_SPECIALIST,
    )
    if active_only:
        q = q.filter(TenantAgent.active.is_(True))
    return q.order_by(TenantAgent.is_default.desc(), TenantAgent.id).all()


def get_agent_row(db: Session, tenant_id: str, agent_id: int) -> TenantAgent | None:
    return (
        db.query(TenantAgent)
        .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == agent_id)
        .first()
    )


def binding_to_dict(row: AgentToolBinding) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "agent_id": row.agent_id,
        "tool_kind": row.tool_kind,
        "tool_ref": row.tool_ref,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_agent_tool_bindings(db: Session, tenant_id: str, agent_id: int) -> list[dict]:
    rows = (
        db.query(AgentToolBinding)
        .filter(AgentToolBinding.tenant_id == tenant_id, AgentToolBinding.agent_id == agent_id)
        .order_by(AgentToolBinding.tool_kind, AgentToolBinding.tool_ref)
        .all()
    )
    return [binding_to_dict(r) for r in rows]


def set_agent_tool_bindings(
    db: Session,
    tenant_id: str,
    agent_id: int,
    bindings: list[dict],
) -> list[dict]:
    agent = get_agent_row(db, tenant_id, agent_id)
    if not agent:
        raise LookupError("Agente não encontrado")
    if getattr(agent, "role", ROLE_SPECIALIST) == ROLE_ORCHESTRATOR:
        raise ValueError("Orquestrador não possui tools de execução")

    db.query(AgentToolBinding).filter(
        AgentToolBinding.tenant_id == tenant_id, AgentToolBinding.agent_id == agent_id
    ).delete()

    seen: set[tuple[str, str]] = set()
    for item in bindings or []:
        kind = str(item.get("tool_kind") or "").strip()
        ref = str(item.get("tool_ref") or "*").strip() or "*"
        if kind not in {"http", *BUILTIN_KINDS}:
            continue
        key = (kind, ref)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            AgentToolBinding(
                tenant_id=tenant_id,
                agent_id=agent_id,
                tool_kind=kind,
                tool_ref=ref,
            )
        )
    db.commit()
    return list_agent_tool_bindings(db, tenant_id, agent_id)


def seed_default_bindings(db: Session, tenant_id: str, agent_id: int) -> None:
    existing = {
        (b.tool_kind, b.tool_ref)
        for b in db.query(AgentToolBinding).filter(AgentToolBinding.agent_id == agent_id).all()
    }
    for kind in BUILTIN_KINDS:
        if (kind, "*") not in existing:
            db.add(
                AgentToolBinding(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    tool_kind=kind,
                    tool_ref="*",
                )
            )
    db.commit()


def resolve_allowed_tools(db: Session, tenant_id: str, agent_id: int | None) -> dict[str, Any]:
    if not agent_id:
        return {"builtins": set(BUILTIN_KINDS), "http_slugs": None, "file_refs": None}

    rows = (
        db.query(AgentToolBinding)
        .filter(AgentToolBinding.tenant_id == tenant_id, AgentToolBinding.agent_id == agent_id)
        .all()
    )
    if not rows:
        return {"builtins": set(BUILTIN_KINDS), "http_slugs": None, "file_refs": None}

    builtins: set[str] = set()
    http_slugs: set[str] = set()
    file_refs: set[str] = set()
    for r in rows:
        if r.tool_kind in BUILTIN_KINDS and r.tool_kind != "send_file":
            builtins.add(r.tool_kind)
        elif r.tool_kind == "send_file":
            builtins.add("send_file")
            file_refs.add(r.tool_ref)
        elif r.tool_kind == "http":
            http_slugs.add(r.tool_ref)

    return {
        "builtins": builtins,
        "http_slugs": http_slugs,
        "file_refs": file_refs if file_refs else {"*"},
    }


def patch_sticky_fields(
    db: Session,
    tenant_id: str,
    phone: str,
    *,
    agent_id: int | None,
    conversation_id: int | None,
    clear: bool = False,
) -> dict:
    profile = get_contact_by_phone(db, tenant_id, phone)
    if not profile:
        try:
            profile = upsert_contact(db, tenant_id, phone, last_conversation_id=conversation_id)
        except ValueError:
            return {}
    fields = dict(profile.get("fields") or {})
    if clear or agent_id is None:
        fields[ACTIVE_AGENT_KEY] = None
        fields[ACTIVE_CONV_KEY] = None
    else:
        fields[ACTIVE_AGENT_KEY] = int(agent_id)
        if conversation_id is not None:
            fields[ACTIVE_CONV_KEY] = int(conversation_id)
    return update_contact(db, tenant_id, int(profile["id"]), {"fields": fields})


def read_sticky_agent_id(profile: dict | None, conversation_id: int | None) -> int | None:
    if not profile:
        return None
    fields = profile.get("fields") or {}
    raw = fields.get(ACTIVE_AGENT_KEY)
    if raw is None or raw == "":
        return None
    try:
        agent_id = int(raw)
    except (TypeError, ValueError):
        return None
    sticky_conv = fields.get(ACTIVE_CONV_KEY)
    if conversation_id is not None and sticky_conv is not None:
        try:
            if int(sticky_conv) != int(conversation_id):
                return None
        except (TypeError, ValueError):
            return None
    return agent_id


def route_with_orchestrator(
    db: Session,
    tenant_id: str,
    *,
    inbound_text: str,
    specialists: list[TenantAgent] | None = None,
) -> TenantAgent | None:
    ensure_orchestrator(db, tenant_id)
    specs = specialists if specialists is not None else list_specialists(db, tenant_id)
    if not specs:
        return None
    if len(specs) == 1:
        return specs[0]

    orch = ensure_orchestrator(db, tenant_id)
    catalog = [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description or "",
            "is_default": bool(a.is_default),
        }
        for a in specs
    ]
    default = next((a for a in specs if a.is_default), specs[0])

    tenant = get_tenant(tenant_id)
    llm = get_llm(tenant)
    if not llm:
        return default

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", (orch.system_prompt or _DEFAULT_ORCHESTRATOR_PROMPT).strip()),
            (
                "human",
                "Agentes disponíveis:\n{catalog}\n\nMensagem do cliente:\n{message}\n\n"
                'Responda só JSON: {{"agent_id": <id>, "reason": "..."}}',
            ),
        ]
    )
    try:
        result = (prompt | llm | JsonOutputParser()).invoke(
            {
                "catalog": json.dumps(catalog, ensure_ascii=False),
                "message": inbound_text or "",
            }
        )
        log_llm_usage(tenant, tenant.model.name, max(1, len(inbound_text) // 4), 64)
        chosen_id = result.get("agent_id") if isinstance(result, dict) else None
        if chosen_id is not None:
            chosen = next((a for a in specs if a.id == int(chosen_id)), None)
            if chosen:
                logger.info(
                    "Orquestrador tenant=%s escolheu agent_id=%s reason=%s",
                    tenant_id,
                    chosen.id,
                    (result or {}).get("reason"),
                )
                return chosen
    except Exception as error:
        logger.warning("Falha no orquestrador tenant=%s: %s", tenant_id, error)

    return default


def builtins_prompt_lines(allowed: dict[str, Any]) -> str:
    builtins = allowed.get("builtins") or set()
    lines: list[str] = []
    if "save_field" in builtins:
        lines.append("- save_field: use field_updates para persistir dados do contato")
    if "send_file" in builtins:
        lines.append("- send_file: use files_to_send com nomes da biblioteca liberada")
    if "handoff" in builtins:
        lines.append("- handoff: use handoff_to_human=true para transferir a um humano")
    if "transfer_agent" in builtins:
        lines.append(
            '- transfer_agent: use "transfer_to_agent" com '
            '{"agent_id": <id>} ou {"name": "<nome>"} para outro especialista; '
            'ou "return_to_orchestrator": true para reclassificar'
        )
    return "\n".join(lines)
