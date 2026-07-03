import re
from typing import Any

from sqlalchemy.orm import Session

from harness_platform.cache import invalidate_tenant_cache
from harness_platform.crypto import decrypt_value, encrypt_value, mask_secret
from harness_platform.models import Tenant, TenantPrompt
from harness_platform.schemas import TenantCreate, TenantSettings, TenantUpdate
from tenants.config import (
    ContextConfig,
    HandoffConfig,
    ModelConfig,
    RagConfig,
    RoutingConfig,
    TenantConfig,
)

PROMPT_NAMES = ("agent_system", "facts_system", "summarize_system")
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")


def _default_prompts() -> dict[str, str]:
    return {name: "" for name in PROMPT_NAMES}


def _settings_to_dict(settings: TenantSettings) -> dict[str, Any]:
    data = settings.model_dump()
    routing = dict(data.get("routing") or {})
    token = routing.pop("chatwoot_bot_token", None)
    if token and str(token).strip():
        routing["encrypted_chatwoot_bot_token"] = encrypt_value(str(token).strip())
    data["routing"] = routing
    return data


def _public_routing(routing: dict | None) -> dict[str, Any]:
    routing = dict(routing or {})
    encrypted = routing.pop("encrypted_chatwoot_bot_token", None)
    routing.pop("chatwoot_bot_token", None)
    routing["chatwoot_bot_token_set"] = bool(encrypted)
    routing["chatwoot_bot_token_preview"] = mask_secret(encrypted or "")
    return routing


def _public_settings(raw: dict | None) -> dict[str, Any]:
    if not raw:
        return {}
    result = dict(raw)
    result["routing"] = _public_routing(result.get("routing"))
    return result


def _routing_bot_token(routing: dict | None) -> str:
    encrypted = (routing or {}).get("encrypted_chatwoot_bot_token") or ""
    if not encrypted:
        return ""
    try:
        return decrypt_value(encrypted)
    except Exception:
        return ""


def _merge_settings(current_raw: dict | None, incoming: TenantSettings) -> dict[str, Any]:
    current = _parse_settings(current_raw)
    merged = current.model_dump()
    payload = incoming.model_dump(exclude_unset=True)

    incoming_routing = payload.pop("routing", None)
    if incoming_routing is not None:
        raw_routing = dict((current_raw or {}).get("routing") or {})
        preserved_encrypted = raw_routing.get("encrypted_chatwoot_bot_token")
        current_routing = dict(merged.get("routing") or {})
        new_token = incoming_routing.pop("chatwoot_bot_token", None)
        current_routing.update(incoming_routing)
        current_routing.pop("chatwoot_bot_token", None)
        current_routing.pop("chatwoot_bot_token_set", None)
        current_routing.pop("chatwoot_bot_token_preview", None)
        if new_token is not None:
            if str(new_token).strip():
                current_routing["encrypted_chatwoot_bot_token"] = encrypt_value(str(new_token).strip())
            else:
                current_routing.pop("encrypted_chatwoot_bot_token", None)
        elif preserved_encrypted:
            current_routing["encrypted_chatwoot_bot_token"] = preserved_encrypted
        merged["routing"] = current_routing

    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _parse_settings(raw: dict | None) -> TenantSettings:
    if not raw:
        return TenantSettings()
    return TenantSettings.model_validate(raw)


def tenant_to_response(tenant: Tenant) -> dict[str, Any]:
    prompts = {p.name: p.content for p in tenant.prompts}
    for name in PROMPT_NAMES:
        prompts.setdefault(name, "")
    return {
        "id": tenant.id,
        "name": tenant.name,
        "language": tenant.language,
        "active": tenant.active,
        "settings": _public_settings(tenant.settings),
        "prompts": prompts,
    }


def tenant_to_config(tenant: Tenant) -> TenantConfig:
    settings = _parse_settings(tenant.settings)
    return TenantConfig(
        id=tenant.id,
        name=tenant.name,
        language=tenant.language,
        model=ModelConfig(
            name=settings.model.name,
            temperature=settings.model.temperature,
            api_key_env="OPENAI_API_KEY",
            llm_model_id=settings.model.llm_model_id,
        ),
        routing=RoutingConfig(
            chatwoot_account_ids=settings.routing.chatwoot_account_ids,
            chatwoot_inbox_ids=settings.routing.chatwoot_inbox_ids,
            chatwoot_bot_token=_routing_bot_token((tenant.settings or {}).get("routing")),
        ),
        context=ContextConfig(
            summarize_after=settings.context.summarize_after,
            keep_recent=settings.context.keep_recent,
        ),
        rag=RagConfig(
            enabled=settings.rag.enabled,
            top_k=settings.rag.top_k,
            embedding_model=settings.rag.embedding_model,
            chunk_size=settings.rag.chunk_size,
            chunk_overlap=settings.rag.chunk_overlap,
        ),
        handoff=HandoffConfig(
            enabled=settings.handoff.enabled,
            message=settings.handoff.message,
            keywords=settings.handoff.keywords,
            on_no_knowledge=settings.handoff.on_no_knowledge,
            private_note_enabled=settings.handoff.private_note_enabled,
            resume_bot_on_resolve=settings.handoff.resume_bot_on_resolve,
        ),
        root_dir="",
    )


def list_tenants_db(db: Session, *, active_only: bool = False) -> list[Tenant]:
    query = db.query(Tenant)
    if active_only:
        query = query.filter(Tenant.active.is_(True))
    return query.order_by(Tenant.name).all()


def get_tenant_db(db: Session, tenant_id: str) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def create_tenant(db: Session, payload: TenantCreate) -> Tenant:
    tenant_id = payload.id.strip().lower()
    if not _SLUG_RE.match(tenant_id):
        raise ValueError("ID do tenant deve ser slug lowercase (ex: blackbeans)")

    if get_tenant_db(db, tenant_id):
        raise ValueError(f"Tenant '{tenant_id}' já existe")

    tenant = Tenant(
        id=tenant_id,
        name=payload.name,
        language=payload.language,
        active=payload.active,
        settings=_settings_to_dict(payload.settings),
    )
    db.add(tenant)

    prompts = {**_default_prompts(), **payload.prompts}
    for name, content in prompts.items():
        if name in PROMPT_NAMES:
            db.add(TenantPrompt(tenant_id=tenant_id, name=name, content=content))

    db.commit()
    db.refresh(tenant)
    invalidate_tenant_cache(tenant_id)
    return tenant


def update_tenant(db: Session, tenant_id: str, payload: TenantUpdate) -> Tenant:
    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise LookupError(f"Tenant '{tenant_id}' não encontrado")

    if payload.name is not None:
        tenant.name = payload.name
    if payload.language is not None:
        tenant.language = payload.language
    if payload.active is not None:
        tenant.active = payload.active
    if payload.settings is not None:
        tenant.settings = _merge_settings(tenant.settings, payload.settings)

    if payload.prompts:
        existing = {p.name: p for p in tenant.prompts}
        for name, content in payload.prompts.items():
            if name not in PROMPT_NAMES:
                continue
            if name in existing:
                existing[name].content = content
            else:
                db.add(TenantPrompt(tenant_id=tenant_id, name=name, content=content))

    db.commit()
    db.refresh(tenant)
    invalidate_tenant_cache(tenant_id)
    return tenant


def set_tenant_active(db: Session, tenant_id: str, active: bool) -> Tenant:
    return update_tenant(db, tenant_id, TenantUpdate(active=active))


def delete_tenant(db: Session, tenant_id: str) -> None:
    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise LookupError(f"Tenant '{tenant_id}' não encontrado")
    db.delete(tenant)
    db.commit()
    invalidate_tenant_cache(tenant_id)


def update_prompt(db: Session, tenant_id: str, name: str, content: str) -> None:
    if name not in PROMPT_NAMES:
        raise ValueError(f"Prompt inválido: {name}")

    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise LookupError(f"Tenant '{tenant_id}' não encontrado")

    row = db.query(TenantPrompt).filter(
        TenantPrompt.tenant_id == tenant_id, TenantPrompt.name == name
    ).first()
    if row:
        row.content = content
    else:
        db.add(TenantPrompt(tenant_id=tenant_id, name=name, content=content))
    db.commit()
    invalidate_tenant_cache(tenant_id)
