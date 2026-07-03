import json
import logging
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from admin.auth import ensure_seed_admin
from admin.routes import router as admin_router
from portal.routes import router as portal_router
from harness_platform.db import SessionLocal

from agent.nodes import generate_dispatch_message
from handoff.constants import HANDOFF_LABEL
from handoff.resume import handle_conversation_status_webhook
from ingress.dedupe import is_duplicate
from ingress.models import InboundEvent
from ingress.processor import process_inbound
from integrations.chatwoot import (
    default_account_id,
    extract_inbound_message,
    ignore_reason,
    is_configured,
    is_conversation_status_webhook,
    send_message,
    send_template,
    verify_webhook_signature,
    webhook_account_id,
    webhook_conversation_id,
    webhook_inbox_id,
    webhook_message_id,
)
from knowledge import chunks_by_tenant, is_rag_enabled, sync_tenant_index
from ops.lifecycle import Lifecycle, list_events, recent_events, record_event
from tenants.registry import get_tenant, list_tenants, resolve_tenant_by_routing

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Harness (LangGraph + Chatwoot)")

_cors_origins = os.getenv("ADMIN_CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_router)
app.include_router(portal_router)


@app.on_event("startup")
def startup_seed_admin():
    try:
        with SessionLocal() as db:
            ensure_seed_admin(db)
            from harness_platform.llm_service import seed_default_openai
            from harness_platform.plan_service import seed_default_plans

            seed_default_openai(db)
            seed_default_plans(db)
            from harness_platform.portal_service import seed_demo_tenant_user

            seed_demo_tenant_user(db)
    except Exception:
        logger.warning("Não foi possível seed admin/LLM (DB indisponível?)", exc_info=True)


class DispatchContact(BaseModel):
    conversation_id: int
    variables: dict = Field(default_factory=dict)
    processed_params: dict = Field(default_factory=dict)


class DispatchRequest(BaseModel):
    mode: Literal["template", "conversation"] = "conversation"
    message: str = ""
    template_name: str | None = None
    language: str = "pt_BR"
    tenant_id: str | None = None
    account_id: int | None = None
    contacts: list[DispatchContact]

    @model_validator(mode="after")
    def validate_mode(self):
        if not self.contacts:
            raise ValueError("Lista de contatos vazia")
        if self.mode == "template" and not self.template_name:
            raise ValueError("template_name é obrigatório no modo template")
        if self.mode == "conversation" and not self.message:
            raise ValueError("message é obrigatório no modo conversation")
        return self


class DispatchResult(BaseModel):
    conversation_id: int
    ok: bool
    error: str | None = None


@app.get("/health")
def health():
    tenant_list = list_tenants()
    tenants = [
        {
            "id": tenant.id,
            "name": tenant.name,
            "model": tenant.model.name,
            "inbox_ids": tenant.routing.chatwoot_inbox_ids,
            "rag_enabled": tenant.rag.enabled,
            "rag_chunks": chunks_by_tenant([tenant.id])[tenant.id],
            "handoff_enabled": tenant.handoff.enabled,
        }
        for tenant in tenant_list
    ]
    return {
        "status": "ok",
        "tenant_id": os.getenv("TENANT_ID") or None,
        "tenants": tenants,
        "chatwoot_configured": is_configured(),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "rag": {
            "enabled": is_rag_enabled(),
            "chunks_by_tenant": chunks_by_tenant([tenant.id for tenant in tenant_list]),
        },
        "architecture": {
            "ingress": "async_webhook_with_dedupe_and_retries",
            "context": "summarization_policy",
            "memory": "semantic_sqlite_per_tenant",
            "knowledge": "rag_sqlite_per_tenant",
            "handoff": "chatwoot_label",
            "agent": "langgraph_component",
            "channel": "chatwoot_multichannel",
            "tenants": "config_per_client_db_or_filesystem",
            "admin_api": "jwt_crud_tenants",
            "portal_api": "tenant_self_service",
        },
    }


@app.post("/ops/reindex")
def ops_reindex(tenant_id: str | None = None):
    targets = [get_tenant(tenant_id)] if tenant_id else list_tenants()
    results = []
    for tenant in targets:
        stats = sync_tenant_index(tenant)
        results.append({"tenant_id": tenant.id, **stats})
    return {"reindexed": results}


@app.post("/ops/resume-bot")
async def ops_resume_bot(
    conversation_id: int,
    account_id: int | None = None,
    tenant_id: str | None = None,
):
    """Devolve a conversa ao bot (open/resolved → pending) na mesma thread."""
    try:
        resolved_account_id = account_id or default_account_id()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    from handoff.resume import resume_conversation_for_tenant

    result = await resume_conversation_for_tenant(
        account_id=resolved_account_id,
        conversation_id=conversation_id,
        tenant_id=tenant_id,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "falha ao reativar bot"))
    return {"ok": True, "conversation_id": conversation_id, "status": "pending"}


@app.get("/ops/recent")
def ops_recent(limit: int = 50):
    return {"events": recent_events(limit)}


@app.post("/webhooks/chatwoot")
async def chatwoot_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Chatwoot-Signature")
    timestamp = request.headers.get("X-Chatwoot-Timestamp")
    delivery_id = request.headers.get("X-Chatwoot-Delivery", "")

    if not verify_webhook_signature(body, signature, timestamp):
        raise HTTPException(status_code=401, detail="Assinatura do webhook inválida")

    payload = json.loads(body)
    event_name = str(payload.get("event", "")).lower()

    if is_conversation_status_webhook(payload):
        if is_duplicate(delivery_id or f"{event_name}:{webhook_conversation_id(payload) or 0}"):
            return {"duplicate": True}
        background_tasks.add_task(_safe_handle_conversation_status, payload, delivery_id)
        return JSONResponse(
            status_code=202,
            content={
                "accepted": True,
                "event": event_name,
                "conversation_id": webhook_conversation_id(payload),
            },
        )

    inbound = None
    account_id = webhook_account_id(payload)
    inbox_id = webhook_inbox_id(payload)
    handoff_label = HANDOFF_LABEL
    tenant_id = ""
    if account_id is not None:
        tenant = resolve_tenant_by_routing(account_id=account_id, inbox_id=inbox_id)
        tenant_id = tenant.id

    inbound = extract_inbound_message(payload, handoff_label=handoff_label)

    if not inbound:
        reason = ignore_reason(payload, handoff_label=handoff_label) or "ignored"
        conversation_id = webhook_conversation_id(payload) or 0
        if conversation_id or reason != "not_message_created":
            record_event(
                delivery_id=delivery_id,
                message_id=webhook_message_id(payload),
                conversation_id=conversation_id,
                status=Lifecycle.WEBHOOK_IGNORED,
                detail=reason,
                tenant_id=tenant_id,
                account_id=account_id,
                inbox_id=inbox_id,
            )
        return {"ignored": True, "reason": reason}

    if is_duplicate(delivery_id or inbound.get("message_id", "")):
        tenant = resolve_tenant_by_routing(
            account_id=inbound["account_id"],
            inbox_id=inbound.get("inbox_id"),
        )
        record_event(
            delivery_id=delivery_id,
            message_id=inbound.get("message_id", ""),
            conversation_id=inbound["conversation_id"],
            status=Lifecycle.DUPLICATE,
            tenant_id=tenant.id,
            account_id=inbound["account_id"],
            inbox_id=inbound.get("inbox_id"),
        )
        return {"duplicate": True}

    event = InboundEvent(
        phone=inbound["phone"],
        text=inbound["text"],
        conversation_id=inbound["conversation_id"],
        account_id=inbound["account_id"],
        inbox_id=inbound.get("inbox_id"),
        contact_name=inbound.get("contact_name", ""),
        message_id=inbound.get("message_id", ""),
        delivery_id=delivery_id,
        conversation_status=inbound.get("conversation_status", ""),
        raw=inbound.get("raw", payload),
    )

    background_tasks.add_task(_safe_process, event)

    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "conversation_id": event.conversation_id,
            "delivery_id": delivery_id or None,
        },
    )


async def _safe_handle_conversation_status(payload: dict, delivery_id: str) -> None:
    try:
        await handle_conversation_status_webhook(payload, delivery_id)
    except Exception:
        logger.exception("Falha ao processar evento de status da conversa")


async def _safe_process(event: InboundEvent) -> None:
    try:
        await process_inbound(event)
    except Exception:
        logger.exception("Processamento em background falhou")


@app.post("/dispatch", response_model=list[DispatchResult])
async def dispatch_messages(body: DispatchRequest):
    try:
        account_id = body.account_id or default_account_id()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    results: list[DispatchResult] = []
    bot_token = ""
    if body.tenant_id:
        bot_token = get_tenant(body.tenant_id).routing.chatwoot_bot_token

    for contact in body.contacts:
        try:
            if body.mode == "template":
                response = await send_template(
                    account_id=account_id,
                    conversation_id=contact.conversation_id,
                    template_name=body.template_name or "",
                    language=body.language,
                    processed_params=contact.processed_params or contact.variables,
                    content=body.message,
                    bot_token=bot_token or None,
                )
            else:
                text = generate_dispatch_message(
                    body.message,
                    contact.variables,
                    tenant_id=body.tenant_id,
                )
                response = await send_message(
                    account_id,
                    contact.conversation_id,
                    text,
                    bot_token=bot_token or None,
                )

            ok = bool(response.get("ok"))
            results.append(
                DispatchResult(
                    conversation_id=contact.conversation_id,
                    ok=ok,
                    error=None if ok else str(response.get("error")),
                )
            )
        except Exception as error:
            results.append(
                DispatchResult(
                    conversation_id=contact.conversation_id,
                    ok=False,
                    error=str(error),
                )
            )

    return results
