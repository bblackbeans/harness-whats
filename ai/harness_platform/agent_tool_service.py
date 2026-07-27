"""CRUD de tools editáveis por agente (regras + endpoint)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from harness_platform.models import AgentTool, TenantAgent
from harness_platform.orchestrator_service import ROLE_ORCHESTRATOR, ROLE_SPECIALIST

VALID_KINDS = {"http", "save_field", "send_file", "handoff", "transfer_agent", "instruction"}


def _slugify(text: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "").lower()).strip("_")[:48]
    return base or "tool"


def _normalize_file_ids(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def tool_to_dict(row: AgentTool) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "agent_id": row.agent_id,
        "name": row.name,
        "slug": row.slug,
        "kind": row.kind,
        "rules": row.rules or "",
        "method": row.method or "POST",
        "url": row.url or "",
        "headers": row.headers or {},
        "body_template": row.body_template or "",
        "auth_header": row.auth_header or "",
        "file_ids": _normalize_file_ids(getattr(row, "file_ids", None) or []),
        "active": bool(row.active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_agent_tools(
    db: Session,
    tenant_id: str,
    *,
    agent_id: int | None = None,
    active_only: bool = False,
) -> list[dict]:
    q = db.query(AgentTool).filter(AgentTool.tenant_id == tenant_id)
    if agent_id is not None:
        q = q.filter(AgentTool.agent_id == agent_id)
    if active_only:
        q = q.filter(AgentTool.active.is_(True))
    rows = q.order_by(AgentTool.updated_at.desc(), AgentTool.id.desc()).all()
    return [tool_to_dict(r) for r in rows]


def get_agent_tool(db: Session, tenant_id: str, tool_id: int) -> dict | None:
    row = (
        db.query(AgentTool)
        .filter(AgentTool.tenant_id == tenant_id, AgentTool.id == tool_id)
        .first()
    )
    return tool_to_dict(row) if row else None


def get_agent_tool_by_slug(
    db: Session, tenant_id: str, agent_id: int, slug: str
) -> AgentTool | None:
    return (
        db.query(AgentTool)
        .filter(
            AgentTool.tenant_id == tenant_id,
            AgentTool.agent_id == agent_id,
            AgentTool.slug == slug,
            AgentTool.active.is_(True),
        )
        .first()
    )


def create_agent_tool(db: Session, tenant_id: str, data: dict) -> dict:
    agent_id = int(data.get("agent_id") or 0)
    agent = (
        db.query(TenantAgent)
        .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == agent_id)
        .first()
    )
    if not agent:
        raise ValueError("Agente inválido")
    if getattr(agent, "role", ROLE_SPECIALIST) == ROLE_ORCHESTRATOR:
        raise ValueError("Orquestrador não possui tools de execução")

    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Nome obrigatório")
    kind = str(data.get("kind") or "instruction").strip()
    if kind not in VALID_KINDS:
        raise ValueError(f"kind inválido: {kind}")

    slug = str(data.get("slug") or "").strip() or _slugify(name)
    slug = _slugify(slug)
    clash = (
        db.query(AgentTool)
        .filter(AgentTool.agent_id == agent_id, AgentTool.slug == slug)
        .first()
    )
    if clash:
        slug = f"{slug}_{agent_id}"

    if kind == "http" and not str(data.get("url") or "").strip():
        raise ValueError("Tool HTTP precisa de URL/endpoint")

    row = AgentTool(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=name,
        slug=slug,
        kind=kind,
        rules=str(data.get("rules") or ""),
        method=str(data.get("method") or "POST").upper()[:16],
        url=str(data.get("url") or ""),
        headers=data.get("headers") if isinstance(data.get("headers"), dict) else {},
        body_template=str(data.get("body_template") or ""),
        auth_header=str(data.get("auth_header") or ""),
        file_ids=_normalize_file_ids(data.get("file_ids")) if kind == "send_file" else [],
        active=bool(data.get("active", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return tool_to_dict(row)


def update_agent_tool(db: Session, tenant_id: str, tool_id: int, data: dict) -> dict:
    row = (
        db.query(AgentTool)
        .filter(AgentTool.tenant_id == tenant_id, AgentTool.id == tool_id)
        .first()
    )
    if not row:
        raise LookupError("Tool não encontrada")

    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip()
    if "rules" in data and data["rules"] is not None:
        row.rules = str(data["rules"])
    if "kind" in data and data["kind"] is not None:
        kind = str(data["kind"]).strip()
        if kind not in VALID_KINDS:
            raise ValueError(f"kind inválido: {kind}")
        row.kind = kind
    if "slug" in data and data["slug"] is not None:
        new_slug = _slugify(str(data["slug"]))
        clash = (
            db.query(AgentTool)
            .filter(
                AgentTool.agent_id == row.agent_id,
                AgentTool.slug == new_slug,
                AgentTool.id != row.id,
            )
            .first()
        )
        if clash:
            raise ValueError("Já existe tool com este slug neste agente")
        row.slug = new_slug
    if "method" in data and data["method"] is not None:
        row.method = str(data["method"]).upper()[:16]
    if "url" in data and data["url"] is not None:
        row.url = str(data["url"])
    if "headers" in data and isinstance(data["headers"], dict):
        row.headers = data["headers"]
    if "body_template" in data and data["body_template"] is not None:
        row.body_template = str(data["body_template"])
    if "auth_header" in data and data["auth_header"] is not None:
        row.auth_header = str(data["auth_header"])
    if "file_ids" in data and data["file_ids"] is not None:
        row.file_ids = _normalize_file_ids(data["file_ids"])
    if "active" in data and data["active"] is not None:
        row.active = bool(data["active"])
    if "agent_id" in data and data["agent_id"] is not None:
        new_aid = int(data["agent_id"])
        agent = (
            db.query(TenantAgent)
            .filter(TenantAgent.tenant_id == tenant_id, TenantAgent.id == new_aid)
            .first()
        )
        if not agent or getattr(agent, "role", ROLE_SPECIALIST) == ROLE_ORCHESTRATOR:
            raise ValueError("Agente inválido")
        row.agent_id = new_aid

    if row.kind == "http" and not (row.url or "").strip():
        raise ValueError("Tool HTTP precisa de URL/endpoint")
    if row.kind != "send_file":
        row.file_ids = []

    db.commit()
    db.refresh(row)
    return tool_to_dict(row)


def delete_agent_tool(db: Session, tenant_id: str, tool_id: int) -> None:
    row = (
        db.query(AgentTool)
        .filter(AgentTool.tenant_id == tenant_id, AgentTool.id == tool_id)
        .first()
    )
    if not row:
        raise LookupError("Tool não encontrada")
    db.delete(row)
    db.commit()


def resolve_agent_tools_for_runtime(
    db: Session, tenant_id: str, agent_id: int | None
) -> dict[str, Any]:
    """
    Preferência: agent_tools editáveis.
    Fallback: bindings legados (comportamento anterior).
    """
    if not agent_id:
        return {"tools": [], "builtins": set(), "http_by_slug": {}, "from_defined": False}

    rows = (
        db.query(AgentTool)
        .filter(
            AgentTool.tenant_id == tenant_id,
            AgentTool.agent_id == agent_id,
            AgentTool.active.is_(True),
        )
        .order_by(AgentTool.id)
        .all()
    )
    if rows:
        builtins: set[str] = set()
        http_by_slug: dict[str, AgentTool] = {}
        file_refs: set[str] = set()
        send_file_unrestricted = False
        for r in rows:
            if r.kind in {"save_field", "send_file", "handoff", "transfer_agent"}:
                builtins.add(r.kind)
            if r.kind == "http" and r.slug:
                http_by_slug[r.slug] = r
            if r.kind == "send_file":
                ids = _normalize_file_ids(getattr(r, "file_ids", None) or [])
                if not ids:
                    send_file_unrestricted = True
                else:
                    file_refs.update(str(i) for i in ids)
        if send_file_unrestricted:
            file_refs = {"*"}
        elif "send_file" in builtins and not file_refs:
            file_refs = {"*"}
        return {
            "tools": [tool_to_dict(r) for r in rows],
            "builtins": builtins,
            "http_by_slug": http_by_slug,
            "file_refs": file_refs,
            "from_defined": True,
        }

    # fallback legado
    from harness_platform.orchestrator_service import resolve_allowed_tools

    allowed = resolve_allowed_tools(db, tenant_id, agent_id)
    return {
        "tools": [],
        "builtins": allowed.get("builtins") or set(),
        "http_by_slug": {},
        "http_slugs": allowed.get("http_slugs"),
        "file_refs": allowed.get("file_refs"),
        "from_defined": False,
    }


def agent_tools_prompt_block(tools: list[dict]) -> str:
    if not tools:
        return ""
    lines = [
        "Ferramentas deste agente (use quando as regras abaixo pedirem):",
    ]
    for t in tools:
        kind = t.get("kind") or ""
        slug = t.get("slug") or ""
        name = t.get("name") or slug
        rules = (t.get("rules") or "").strip()
        lines.append(f"\n### {name} [{slug}] ({kind})")
        if rules:
            lines.append(f"Regras: {rules}")
        if kind == "http":
            lines.append(
                f"Endpoint: {t.get('method') or 'POST'} {t.get('url') or '(sem URL)'}"
            )
            lines.append(f'Para executar: inclua "{slug}" em http_tool_calls.')
        elif kind == "save_field":
            lines.append("Ação: preencha field_updates com os dados coletados.")
        elif kind == "send_file":
            ids = t.get("file_ids") or []
            if ids:
                lines.append(
                    f"Ação: preencha files_to_send apenas com estes ids da biblioteca: {', '.join(str(i) for i in ids)}."
                )
            else:
                lines.append("Ação: preencha files_to_send com nomes/ids da biblioteca.")
        elif kind == "handoff":
            lines.append("Ação: handoff_to_human=true.")
        elif kind == "transfer_agent":
            lines.append(
                'Ação: transfer_to_agent={"agent_id":N} ou return_to_orchestrator=true.'
            )
        elif kind == "instruction":
            lines.append("Ação: siga as regras na conversa (sem chamada HTTP).")
    return "\n".join(lines)


async def execute_agent_http_tool(tool: AgentTool, profile: dict) -> dict:
    """Executa HTTP a partir da config da agent_tool (mesmo motor das tenant tools)."""
    from harness_platform.integration_service import execute_http_tool

    # Adaptador duck-typed: execute_http_tool espera TenantHttpTool-like
    class _Adapter:
        pass

    adapter = _Adapter()
    adapter.slug = tool.slug
    adapter.method = tool.method or "POST"
    adapter.url = tool.url or ""
    adapter.headers = tool.headers or {}
    adapter.body_template = tool.body_template or ""
    adapter.auth_header = tool.auth_header or ""
    adapter.include_fields = []
    return await execute_http_tool(adapter, profile)  # type: ignore[arg-type]
