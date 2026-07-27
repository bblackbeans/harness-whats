import json
import logging
import secrets
from typing import Any

import httpx
from sqlalchemy.orm import Session

from harness_platform.models import TenantHttpTool, TenantInboundWebhook
from harness_platform.template_vars import apply_field_mapping, profile_variables, render_template

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:64] or secrets.token_hex(4)


# --- Inbound webhooks ---


def webhook_to_dict(row: TenantInboundWebhook, *, public_base: str = "") -> dict:
    path = f"/webhooks/inbound/{row.tenant_id}/{row.slug}"
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "name": row.name,
        "slug": row.slug,
        "secret": row.secret,
        "field_mapping": row.field_mapping or {},
        "start_conversation": row.start_conversation,
        "initial_message": row.initial_message or "",
        "active": row.active,
        "url_path": path,
        "url": f"{public_base.rstrip('/')}{path}" if public_base else path,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_inbound_webhooks(db: Session, tenant_id: str, *, public_base: str = "") -> list[dict]:
    rows = (
        db.query(TenantInboundWebhook)
        .filter(TenantInboundWebhook.tenant_id == tenant_id)
        .order_by(TenantInboundWebhook.id.desc())
        .all()
    )
    return [webhook_to_dict(r, public_base=public_base) for r in rows]


def create_inbound_webhook(db: Session, tenant_id: str, data: dict, *, public_base: str = "") -> dict:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Nome obrigatório")
    slug = _slugify(str(data.get("slug") or name))
    exists = (
        db.query(TenantInboundWebhook)
        .filter(TenantInboundWebhook.tenant_id == tenant_id, TenantInboundWebhook.slug == slug)
        .first()
    )
    if exists:
        raise ValueError(f"Slug '{slug}' já existe")
    row = TenantInboundWebhook(
        tenant_id=tenant_id,
        name=name,
        slug=slug,
        secret=secrets.token_urlsafe(24),
        field_mapping=data.get("field_mapping") or {},
        start_conversation=bool(data.get("start_conversation", False)),
        initial_message=str(data.get("initial_message") or ""),
        active=bool(data.get("active", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return webhook_to_dict(row, public_base=public_base)


def update_inbound_webhook(
    db: Session, tenant_id: str, webhook_id: int, data: dict, *, public_base: str = ""
) -> dict:
    row = (
        db.query(TenantInboundWebhook)
        .filter(TenantInboundWebhook.tenant_id == tenant_id, TenantInboundWebhook.id == webhook_id)
        .first()
    )
    if not row:
        raise LookupError("Webhook não encontrado")
    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip()
    if "field_mapping" in data and data["field_mapping"] is not None:
        row.field_mapping = data["field_mapping"]
    if "start_conversation" in data and data["start_conversation"] is not None:
        row.start_conversation = bool(data["start_conversation"])
    if "initial_message" in data and data["initial_message"] is not None:
        row.initial_message = str(data["initial_message"])
    if "active" in data and data["active"] is not None:
        row.active = bool(data["active"])
    db.commit()
    db.refresh(row)
    return webhook_to_dict(row, public_base=public_base)


def regenerate_webhook_secret(db: Session, tenant_id: str, webhook_id: int, *, public_base: str = "") -> dict:
    row = (
        db.query(TenantInboundWebhook)
        .filter(TenantInboundWebhook.tenant_id == tenant_id, TenantInboundWebhook.id == webhook_id)
        .first()
    )
    if not row:
        raise LookupError("Webhook não encontrado")
    row.secret = secrets.token_urlsafe(24)
    db.commit()
    db.refresh(row)
    return webhook_to_dict(row, public_base=public_base)


def delete_inbound_webhook(db: Session, tenant_id: str, webhook_id: int) -> None:
    row = (
        db.query(TenantInboundWebhook)
        .filter(TenantInboundWebhook.tenant_id == tenant_id, TenantInboundWebhook.id == webhook_id)
        .first()
    )
    if not row:
        raise LookupError("Webhook não encontrado")
    db.delete(row)
    db.commit()


def get_inbound_webhook_by_slug(db: Session, tenant_id: str, slug: str) -> TenantInboundWebhook | None:
    return (
        db.query(TenantInboundWebhook)
        .filter(
            TenantInboundWebhook.tenant_id == tenant_id,
            TenantInboundWebhook.slug == slug,
            TenantInboundWebhook.active.is_(True),
        )
        .first()
    )


def map_inbound_payload(webhook: TenantInboundWebhook, payload: dict) -> dict[str, Any]:
    return apply_field_mapping(payload, webhook.field_mapping or {})


# --- HTTP tools (outbound) ---


def http_tool_to_dict(row: TenantHttpTool) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "name": row.name,
        "slug": row.slug,
        "method": row.method,
        "url": row.url,
        "headers": row.headers or {},
        "body_template": row.body_template or "",
        "include_fields": row.include_fields or [],
        "auth_header": row.auth_header or "",
        "description": row.description or "",
        "active": row.active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_http_tools(db: Session, tenant_id: str, *, active_only: bool = False) -> list[dict]:
    query = db.query(TenantHttpTool).filter(TenantHttpTool.tenant_id == tenant_id)
    if active_only:
        query = query.filter(TenantHttpTool.active.is_(True))
    rows = query.order_by(TenantHttpTool.id.desc()).all()
    return [http_tool_to_dict(r) for r in rows]


def create_http_tool(db: Session, tenant_id: str, data: dict) -> dict:
    name = str(data.get("name") or "").strip()
    url = str(data.get("url") or "").strip()
    if not name or not url:
        raise ValueError("Nome e URL são obrigatórios")
    slug = _slugify(str(data.get("slug") or name))
    exists = (
        db.query(TenantHttpTool)
        .filter(TenantHttpTool.tenant_id == tenant_id, TenantHttpTool.slug == slug)
        .first()
    )
    if exists:
        raise ValueError(f"Slug '{slug}' já existe")
    row = TenantHttpTool(
        tenant_id=tenant_id,
        name=name,
        slug=slug,
        method=str(data.get("method") or "POST").upper(),
        url=url,
        headers=data.get("headers") or {},
        body_template=str(data.get("body_template") or ""),
        include_fields=data.get("include_fields") or [],
        auth_header=str(data.get("auth_header") or ""),
        description=str(data.get("description") or ""),
        active=bool(data.get("active", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return http_tool_to_dict(row)


def update_http_tool(db: Session, tenant_id: str, tool_id: int, data: dict) -> dict:
    row = (
        db.query(TenantHttpTool)
        .filter(TenantHttpTool.tenant_id == tenant_id, TenantHttpTool.id == tool_id)
        .first()
    )
    if not row:
        raise LookupError("API tool não encontrada")
    for key in ("name", "url", "body_template", "auth_header", "description"):
        if key in data and data[key] is not None:
            setattr(row, key, str(data[key]))
    if "method" in data and data["method"] is not None:
        row.method = str(data["method"]).upper()
    if "headers" in data and data["headers"] is not None:
        row.headers = data["headers"]
    if "include_fields" in data and data["include_fields"] is not None:
        row.include_fields = data["include_fields"]
    if "active" in data and data["active"] is not None:
        row.active = bool(data["active"])
    db.commit()
    db.refresh(row)
    return http_tool_to_dict(row)


def delete_http_tool(db: Session, tenant_id: str, tool_id: int) -> None:
    row = (
        db.query(TenantHttpTool)
        .filter(TenantHttpTool.tenant_id == tenant_id, TenantHttpTool.id == tool_id)
        .first()
    )
    if not row:
        raise LookupError("API tool não encontrada")
    db.delete(row)
    db.commit()


def get_http_tool_by_slug(db: Session, tenant_id: str, slug: str) -> TenantHttpTool | None:
    return (
        db.query(TenantHttpTool)
        .filter(
            TenantHttpTool.tenant_id == tenant_id,
            TenantHttpTool.slug == slug,
            TenantHttpTool.active.is_(True),
        )
        .first()
    )


def build_http_payload(tool: TenantHttpTool, profile: dict | None, extra_vars: dict | None = None) -> tuple[str, dict, str | None]:
    variables = profile_variables(profile)
    if extra_vars:
        variables.update(extra_vars)

    url = render_template(tool.url, variables)
    headers = {
        str(k): render_template(str(v), variables) for k, v in (tool.headers or {}).items()
    }
    if tool.auth_header:
        headers.setdefault("Authorization", render_template(tool.auth_header, variables))

    body: str | None = None
    if tool.body_template and tool.body_template.strip():
        body = render_template(tool.body_template, variables)
    elif tool.include_fields:
        selected: dict[str, Any] = {}
        for key in tool.include_fields:
            k = str(key)
            if k in variables:
                selected[k] = variables[k]
        body = json.dumps(selected, ensure_ascii=False)
        headers.setdefault("Content-Type", "application/json")

    return url, headers, body


async def execute_http_tool(
    tool: TenantHttpTool,
    profile: dict | None = None,
    extra_vars: dict | None = None,
) -> dict:
    url, headers, body = build_http_payload(tool, profile, extra_vars)
    method = (tool.method or "POST").upper()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, url, headers=headers, content=body)
        return {
            "ok": response.status_code < 400,
            "status": response.status_code,
            "body": response.text[:4000],
            "slug": tool.slug,
        }
    except Exception as error:
        logger.exception("Falha HTTP tool %s", tool.slug)
        return {"ok": False, "error": str(error), "slug": tool.slug}


def tools_prompt_block(tools: list[dict]) -> str:
    if not tools:
        return ""
    lines = ["APIs disponíveis (chame via http_tool_calls com o slug):"]
    for t in tools:
        lines.append(f"- {t['slug']}: {t['name']} — {t.get('description') or t['method'] + ' ' + t['url']}")
    return "\n".join(lines)
