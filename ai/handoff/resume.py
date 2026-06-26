import logging

from integrations.chatwoot import (
    resume_bot_conversation,
    should_resume_bot_on_resolve,
    webhook_account_id,
    webhook_conversation_id,
    webhook_inbox_id,
)
from ingress.models import InboundEvent
from ops.lifecycle import Lifecycle, record_event
from tenants import get_tenant, resolve_tenant
from tenants.registry import resolve_tenant_by_routing

logger = logging.getLogger(__name__)


async def ensure_bot_controls_conversation(event: InboundEvent) -> dict:
    """Reativa o bot na mesma conversa quando o cliente escreve após Resolver."""
    tenant = resolve_tenant(event)
    if not tenant.handoff.enabled or not tenant.handoff.auto_resume_on_resolved:
        return {"ok": True, "skipped": True, "reason": "auto_resume_disabled"}

    status = (event.conversation_status or "").lower()
    if status != "resolved":
        return {"ok": True, "skipped": True, "reason": f"status_{status or 'unknown'}"}

    return await _resume_same_conversation(
        tenant_id=tenant.id,
        account_id=event.account_id,
        conversation_id=event.conversation_id,
        source="customer_message_on_resolved",
    )


async def handle_conversation_status_webhook(payload: dict, delivery_id: str = "") -> dict:
    """Quando o agente clica Resolver no Chatwoot, devolve a conversa ao bot."""
    if not should_resume_bot_on_resolve(payload):
        return {"ok": True, "skipped": True, "reason": "not_resolve_event"}

    conversation_id = webhook_conversation_id(payload)
    account_id = webhook_account_id(payload)
    inbox_id = webhook_inbox_id(payload)
    if conversation_id is None or account_id is None:
        return {"ok": False, "error": "payload sem conversation_id ou account_id"}

    tenant = resolve_tenant_by_routing(account_id=account_id, inbox_id=inbox_id)
    if not tenant.handoff.enabled or not tenant.handoff.resume_bot_on_resolve:
        record_event(
            delivery_id=delivery_id,
            message_id="",
            conversation_id=conversation_id,
            status=Lifecycle.IGNORED,
            detail="resume_bot_on_resolve_disabled",
        )
        return {"ok": True, "skipped": True, "reason": "resume_bot_on_resolve_disabled"}

    result = await _resume_same_conversation(
        tenant_id=tenant.id,
        account_id=account_id,
        conversation_id=conversation_id,
        source="chatwoot_resolve",
    )

    if result.get("ok"):
        record_event(
            delivery_id=delivery_id,
            message_id="",
            conversation_id=conversation_id,
            status=Lifecycle.BOT_RESUMED,
            detail=result.get("source", "chatwoot_resolve"),
        )
    else:
        record_event(
            delivery_id=delivery_id,
            message_id="",
            conversation_id=conversation_id,
            status=Lifecycle.FAILED,
            detail=str(result.get("error", "resume_failed")),
        )

    return result


async def resume_conversation_for_tenant(
    *,
    account_id: int,
    conversation_id: int,
    tenant_id: str | None = None,
) -> dict:
    tenant = get_tenant(tenant_id)
    if not tenant.handoff.enabled:
        return {"ok": False, "error": "handoff desabilitado para o tenant"}

    return await _resume_same_conversation(
        tenant_id=tenant.id,
        account_id=account_id,
        conversation_id=conversation_id,
        source="ops_resume_bot",
    )


async def _resume_same_conversation(
    *,
    tenant_id: str,
    account_id: int,
    conversation_id: int,
    source: str,
) -> dict:
    result = await resume_bot_conversation(account_id, conversation_id)
    if result.get("ok"):
        logger.info(
            "Bot reativado tenant=%s conversa=%s origem=%s",
            tenant_id,
            conversation_id,
            source,
        )
        return {**result, "source": source}

    logger.error(
        "Falha ao reativar bot tenant=%s conversa=%s: %s",
        tenant_id,
        conversation_id,
        result.get("error"),
    )
    return result
