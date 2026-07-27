"""CRUD e resolução de agents / flows / flow_runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from harness_platform.models import Flow, FlowRun, TenantAgent, TenantPrompt
from harness_platform.orchestrator_service import (
    ROLE_ORCHESTRATOR,
    ROLE_SPECIALIST,
    ensure_orchestrator,
    seed_default_bindings,
)

_DEFAULT_AGENT_PROMPT = (
    "Você é um assistente virtual de atendimento por mensagem. "
    "Responda em português do Brasil de forma natural e útil."
)


def agent_to_dict(row: TenantAgent) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "name": row.name,
        "description": row.description or "",
        "system_prompt": row.system_prompt or "",
        "role": getattr(row, "role", None) or ROLE_SPECIALIST,
        "is_default": bool(row.is_default),
        "active": bool(row.active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def flow_to_dict(row: Flow, *, include_source: bool = False) -> dict:
    data = {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "agent_id": row.agent_id,
        "name": row.name,
        "description": row.description or "",
        "base_prompt": row.base_prompt or "",
        "status": row.status,
        "is_default": bool(row.is_default),
        "source_filename": row.source_filename or "",
        "import_summary": row.import_summary or {},
        "roteiro": row.roteiro or {},
        "checklist": row.checklist or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_source:
        data["source_raw"] = row.source_raw or ""
    return data


def run_to_dict(row: FlowRun) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "flow_id": row.flow_id,
        "conversation_id": row.conversation_id,
        "phone": row.phone or "",
        "checklist_state": row.checklist_state or {},
        "current_step_id": row.current_step_id or "",
        "variables": row.variables or {},
        "tools_log": row.tools_log or [],
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def ensure_default_agent(db: Session, tenant_id: str) -> TenantAgent:
    ensure_orchestrator(db, tenant_id)
    row = (
        db.query(TenantAgent)
        .filter(
            TenantAgent.tenant_id == tenant_id,
            TenantAgent.is_default.is_(True),
            TenantAgent.role == ROLE_SPECIALIST,
        )
        .first()
    )
    if row:
        return row
    # Fallback: any specialist marked default, or create
    row = (
        db.query(TenantAgent)
        .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.is_default.is_(True))
        .first()
    )
    if row and getattr(row, "role", ROLE_SPECIALIST) != ROLE_ORCHESTRATOR:
        if not getattr(row, "role", None):
            row.role = ROLE_SPECIALIST
            db.commit()
        return row
    prompt_row = (
        db.query(TenantPrompt)
        .filter(TenantPrompt.tenant_id == tenant_id, TenantPrompt.name == "agent_system")
        .first()
    )
    prompt = (prompt_row.content if prompt_row else "") or _DEFAULT_AGENT_PROMPT
    row = TenantAgent(
        tenant_id=tenant_id,
        name="Agente padrão",
        description="Agente principal",
        system_prompt=prompt,
        role=ROLE_SPECIALIST,
        is_default=True,
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    seed_default_bindings(db, tenant_id, row.id)
    return row


def list_agents(db: Session, tenant_id: str, *, role: str | None = None) -> list[dict]:
    ensure_default_agent(db, tenant_id)
    query = db.query(TenantAgent).filter(TenantAgent.tenant_id == tenant_id)
    if role:
        query = query.filter(TenantAgent.role == role)
    rows = query.order_by(TenantAgent.role.asc(), TenantAgent.is_default.desc(), TenantAgent.id).all()
    return [agent_to_dict(r) for r in rows]


def get_agent(db: Session, tenant_id: str, agent_id: int) -> dict | None:
    row = (
        db.query(TenantAgent)
        .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == agent_id)
        .first()
    )
    return agent_to_dict(row) if row else None


def create_agent(db: Session, tenant_id: str, data: dict) -> dict:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Nome obrigatório")
    role = str(data.get("role") or ROLE_SPECIALIST).strip()
    if role not in {ROLE_ORCHESTRATOR, ROLE_SPECIALIST}:
        raise ValueError("role inválido")
    if role == ROLE_ORCHESTRATOR:
        existing = (
            db.query(TenantAgent)
            .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.role == ROLE_ORCHESTRATOR)
            .first()
        )
        if existing:
            raise ValueError("Já existe um orquestrador neste cliente")
    is_default = bool(data.get("is_default", False)) and role == ROLE_SPECIALIST
    if is_default:
        db.query(TenantAgent).filter(
            TenantAgent.tenant_id == tenant_id, TenantAgent.role == ROLE_SPECIALIST
        ).update({"is_default": False})
    row = TenantAgent(
        tenant_id=tenant_id,
        name=name,
        description=str(data.get("description") or ""),
        system_prompt=str(data.get("system_prompt") or _DEFAULT_AGENT_PROMPT),
        role=role,
        is_default=is_default,
        active=bool(data.get("active", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if role == ROLE_SPECIALIST:
        seed_default_bindings(db, tenant_id, row.id)
    return agent_to_dict(row)


def update_agent(db: Session, tenant_id: str, agent_id: int, data: dict) -> dict:
    row = (
        db.query(TenantAgent)
        .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == agent_id)
        .first()
    )
    if not row:
        raise LookupError("Agente não encontrado")
    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip()
    if "description" in data and data["description"] is not None:
        row.description = str(data["description"])
    if "system_prompt" in data and data["system_prompt"] is not None:
        row.system_prompt = str(data["system_prompt"])
    if "active" in data and data["active"] is not None:
        row.active = bool(data["active"])
    if "role" in data and data["role"] is not None:
        new_role = str(data["role"]).strip()
        if new_role not in {ROLE_ORCHESTRATOR, ROLE_SPECIALIST}:
            raise ValueError("role inválido")
        if new_role == ROLE_ORCHESTRATOR and row.role != ROLE_ORCHESTRATOR:
            clash = (
                db.query(TenantAgent)
                .filter(
                    TenantAgent.tenant_id == tenant_id,
                    TenantAgent.role == ROLE_ORCHESTRATOR,
                    TenantAgent.id != row.id,
                )
                .first()
            )
            if clash:
                raise ValueError("Já existe um orquestrador neste cliente")
            row.is_default = False
        row.role = new_role
    if data.get("is_default") and row.role == ROLE_SPECIALIST:
        db.query(TenantAgent).filter(
            TenantAgent.tenant_id == tenant_id, TenantAgent.role == ROLE_SPECIALIST
        ).update({"is_default": False})
        row.is_default = True
    db.commit()
    db.refresh(row)
    # Sync default specialist prompt back to tenant_prompts.agent_system
    if row.is_default and row.role == ROLE_SPECIALIST:
        prompt = (
            db.query(TenantPrompt)
            .filter(TenantPrompt.tenant_id == tenant_id, TenantPrompt.name == "agent_system")
            .first()
        )
        if prompt:
            prompt.content = row.system_prompt
            db.commit()
    return agent_to_dict(row)


def delete_agent(db: Session, tenant_id: str, agent_id: int) -> None:
    row = (
        db.query(TenantAgent)
        .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == agent_id)
        .first()
    )
    if not row:
        raise LookupError("Agente não encontrado")
    if row.role == ROLE_ORCHESTRATOR:
        raise ValueError("Não é possível remover o orquestrador")
    if row.is_default:
        raise ValueError("Não é possível remover o agente padrão")
    db.delete(row)
    db.commit()


def list_flows(db: Session, tenant_id: str, *, agent_id: int | None = None) -> list[dict]:
    query = db.query(Flow).filter(Flow.tenant_id == tenant_id)
    if agent_id is not None:
        query = query.filter(Flow.agent_id == agent_id)
    rows = query.order_by(Flow.updated_at.desc()).all()
    return [flow_to_dict(r) for r in rows]


def get_flow(db: Session, tenant_id: str, flow_id: int, *, include_source: bool = False) -> dict | None:
    row = db.query(Flow).filter(Flow.tenant_id == tenant_id, Flow.id == flow_id).first()
    return flow_to_dict(row, include_source=include_source) if row else None


def create_flow(db: Session, tenant_id: str, data: dict) -> dict:
    ensure_default_agent(db, tenant_id)
    agent_id = data.get("agent_id")
    if not agent_id:
        agent = ensure_default_agent(db, tenant_id)
        agent_id = agent.id
    else:
        agent = (
            db.query(TenantAgent)
            .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == int(agent_id))
            .first()
        )
        if not agent:
            raise ValueError("Agente inválido")
        agent_id = agent.id

    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Nome obrigatório")

    is_default = bool(data.get("is_default", False))
    status = str(data.get("status") or "draft")
    if status not in {"draft", "published"}:
        status = "draft"
    if is_default:
        db.query(Flow).filter(Flow.tenant_id == tenant_id, Flow.agent_id == agent_id).update(
            {"is_default": False}
        )

    row = Flow(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=name,
        description=str(data.get("description") or ""),
        base_prompt=str(data.get("base_prompt") or ""),
        status=status,
        is_default=is_default,
        source_filename=str(data.get("source_filename") or ""),
        source_raw=str(data.get("source_raw") or ""),
        import_summary=data.get("import_summary") or {},
        roteiro=data.get("roteiro") or {},
        checklist=data.get("checklist") or [],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return flow_to_dict(row)


def update_flow(db: Session, tenant_id: str, flow_id: int, data: dict) -> dict:
    row = db.query(Flow).filter(Flow.tenant_id == tenant_id, Flow.id == flow_id).first()
    if not row:
        raise LookupError("Flow não encontrado")
    for key in ("name", "description", "base_prompt", "source_filename", "source_raw"):
        if key in data and data[key] is not None:
            setattr(row, key, str(data[key]))
    if "status" in data and data["status"] in {"draft", "published"}:
        row.status = data["status"]
    if "import_summary" in data and data["import_summary"] is not None:
        row.import_summary = data["import_summary"]
    if "roteiro" in data and data["roteiro"] is not None:
        row.roteiro = data["roteiro"]
    if "checklist" in data and data["checklist"] is not None:
        row.checklist = data["checklist"]
    if "agent_id" in data and data["agent_id"] is not None:
        agent = (
            db.query(TenantAgent)
            .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == int(data["agent_id"]))
            .first()
        )
        if not agent:
            raise ValueError("Agente inválido")
        row.agent_id = agent.id
    if data.get("is_default"):
        db.query(Flow).filter(Flow.tenant_id == tenant_id, Flow.agent_id == row.agent_id).update(
            {"is_default": False}
        )
        row.is_default = True
    elif "is_default" in data and data["is_default"] is False:
        row.is_default = False
    db.commit()
    db.refresh(row)
    return flow_to_dict(row)


def delete_flow(db: Session, tenant_id: str, flow_id: int) -> None:
    row = db.query(Flow).filter(Flow.tenant_id == tenant_id, Flow.id == flow_id).first()
    if not row:
        raise LookupError("Flow não encontrado")
    db.delete(row)
    db.commit()


def publish_flow(db: Session, tenant_id: str, flow_id: int) -> dict:
    return update_flow(db, tenant_id, flow_id, {"status": "published"})


def resolve_agent_and_flow(
    db: Session,
    tenant_id: str,
    *,
    agent_id: int | None = None,
    flow_id: int | None = None,
) -> tuple[TenantAgent | None, Flow | None]:
    """Resolve specialist + published flow com override explícito."""
    ensure_default_agent(db, tenant_id)
    flow: Flow | None = None
    agent: TenantAgent | None = None

    if flow_id:
        flow = (
            db.query(Flow)
            .filter(Flow.tenant_id == tenant_id, Flow.id == flow_id, Flow.status == "published")
            .first()
        )
        if flow:
            agent = (
                db.query(TenantAgent)
                .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == flow.agent_id)
                .first()
            )
            return agent, flow

    if agent_id:
        agent = (
            db.query(TenantAgent)
            .filter(
                TenantAgent.tenant_id == tenant_id,
                TenantAgent.id == agent_id,
                TenantAgent.active.is_(True),
            )
            .first()
        )
        # Não atender com orquestrador como specialist
        if agent and getattr(agent, "role", ROLE_SPECIALIST) == ROLE_ORCHESTRATOR:
            agent = None
    if not agent:
        agent = (
            db.query(TenantAgent)
            .filter(
                TenantAgent.tenant_id == tenant_id,
                TenantAgent.is_default.is_(True),
                TenantAgent.active.is_(True),
                TenantAgent.role == ROLE_SPECIALIST,
            )
            .first()
        )
    if not agent:
        agent = (
            db.query(TenantAgent)
            .filter(
                TenantAgent.tenant_id == tenant_id,
                TenantAgent.active.is_(True),
                TenantAgent.role == ROLE_SPECIALIST,
            )
            .order_by(TenantAgent.id)
            .first()
        )

    if agent:
        flow = (
            db.query(Flow)
            .filter(
                Flow.tenant_id == tenant_id,
                Flow.agent_id == agent.id,
                Flow.status == "published",
                Flow.is_default.is_(True),
            )
            .first()
        )
        if not flow:
            flow = (
                db.query(Flow)
                .filter(
                    Flow.tenant_id == tenant_id,
                    Flow.agent_id == agent.id,
                    Flow.status == "published",
                )
                .order_by(Flow.updated_at.desc())
                .first()
            )

    return agent, flow


def _init_checklist_state(checklist: list) -> dict[str, str]:
    state: dict[str, str] = {}
    for item in checklist or []:
        if isinstance(item, dict):
            sid = str(item.get("id") or item.get("step_id") or "")
            if sid:
                state[sid] = "pending"
        elif isinstance(item, str):
            state[item] = "pending"
    return state


def get_or_create_flow_run(
    db: Session,
    tenant_id: str,
    flow: Flow,
    *,
    conversation_id: int,
    phone: str = "",
) -> FlowRun:
    row = (
        db.query(FlowRun)
        .filter(
            FlowRun.tenant_id == tenant_id,
            FlowRun.flow_id == flow.id,
            FlowRun.conversation_id == conversation_id,
        )
        .first()
    )
    if row:
        return row
    checklist = flow.checklist or []
    # Derive checklist from roteiro etapas if empty
    if not checklist and isinstance(flow.roteiro, dict):
        checklist = [
            {"id": e.get("id"), "titulo": e.get("titulo") or e.get("id")}
            for e in (flow.roteiro.get("etapas") or [])
            if isinstance(e, dict) and e.get("id")
        ]
    row = FlowRun(
        tenant_id=tenant_id,
        flow_id=flow.id,
        conversation_id=conversation_id,
        phone=phone or "",
        checklist_state=_init_checklist_state(checklist),
        current_step_id="",
        variables={},
        tools_log=[],
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def apply_checklist_updates(
    db: Session,
    run: FlowRun,
    updates: dict[str, Any],
    *,
    variables: dict | None = None,
    tools_log_entry: dict | None = None,
    current_step_id: str | None = None,
) -> FlowRun:
    state = dict(run.checklist_state or {})
    for step_id, status in (updates or {}).items():
        if status in {"completed", "pending", "skipped"}:
            state[str(step_id)] = status
    run.checklist_state = state
    if variables:
        merged = dict(run.variables or {})
        merged.update(variables)
        run.variables = merged
    if tools_log_entry:
        log = list(run.tools_log or [])
        log.append(tools_log_entry)
        run.tools_log = log[-100:]
    if current_step_id is not None:
        run.current_step_id = current_step_id
    # Auto-complete run when all required steps done
    if state and all(v in {"completed", "skipped"} for v in state.values()):
        run.status = "completed"
    db.commit()
    db.refresh(run)
    return run


def list_flow_runs(
    db: Session,
    tenant_id: str,
    *,
    flow_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    query = db.query(FlowRun).filter(FlowRun.tenant_id == tenant_id)
    if flow_id is not None:
        query = query.filter(FlowRun.flow_id == flow_id)
    rows = query.order_by(FlowRun.updated_at.desc()).limit(min(limit, 200)).all()
    return [run_to_dict(r) for r in rows]


def get_flow_run(db: Session, tenant_id: str, run_id: int) -> dict | None:
    row = db.query(FlowRun).filter(FlowRun.tenant_id == tenant_id, FlowRun.id == run_id).first()
    return run_to_dict(row) if row else None
