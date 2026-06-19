import json
import logging
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from agent.nodes import generate_dispatch_message
from ingress.dedupe import is_duplicate
from ingress.models import InboundEvent
from ingress.processor import process_inbound
from integrations.chatwoot import (
    default_account_id,
    extract_inbound_message,
    is_configured,
    send_message,
    send_template,
    verify_webhook_signature,
)
from ops.lifecycle import Lifecycle, recent_events, record_event

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Harness (LangGraph + Chatwoot)")


class DispatchContact(BaseModel):
    conversation_id: int
    variables: dict = Field(default_factory=dict)
    processed_params: dict = Field(default_factory=dict)


class DispatchRequest(BaseModel):
    mode: Literal["template", "conversation"] = "conversation"
    message: str = ""
    template_name: str | None = None
    language: str = "pt_BR"
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
    return {
        "status": "ok",
        "chatwoot_configured": is_configured(),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "architecture": {
            "ingress": "async_webhook_with_dedupe_and_retries",
            "context": "summarization_policy",
            "memory": "semantic_sqlite",
            "agent": "langgraph_component",
            "channel": "chatwoot_whatsapp_cloud",
        },
    }


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
    inbound = extract_inbound_message(payload)

    if not inbound:
        return {"ignored": True}

    if is_duplicate(delivery_id or inbound.get("message_id", "")):
        record_event(
            delivery_id=delivery_id,
            message_id=inbound.get("message_id", ""),
            conversation_id=inbound["conversation_id"],
            status=Lifecycle.DUPLICATE,
        )
        return {"duplicate": True}

    event = InboundEvent(
        phone=inbound["phone"],
        text=inbound["text"],
        conversation_id=inbound["conversation_id"],
        account_id=inbound["account_id"],
        contact_name=inbound.get("contact_name", ""),
        message_id=inbound.get("message_id", ""),
        delivery_id=delivery_id,
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
                )
            else:
                text = generate_dispatch_message(body.message, contact.variables)
                response = await send_message(account_id, contact.conversation_id, text)

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
