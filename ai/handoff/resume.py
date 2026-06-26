import logging

from integrations.chatwoot import resume_bot_conversation
from ingress.models import InboundEvent
from tenants import get_tenant, resolve_tenant

logger = logging.getLogger(__name__)


async def ensure_bot_controls_conversation(event: InboundEvent) -> dict:
    """Reativa o bot na mesma conversa quando o cliente escreve após Resolver."""
    tenant = resolve_tenant(event)
    if not tenant.handoff.enabled or not tenant.handoff.auto_resume_on_resolved:
        return {"ok": True, "skipped": True, "reason": "auto_resume_disabled"}

    status = (event.conversation_status or "").lower()
    if status != "resolved":
        return {"ok": True, "skipped": True, "reason": f"status_{status or 'unknown'}"}

    result = await resume_bot_conversation(event.account_id, event.conversation_id)
    if result.get("ok"):
        logger.info(
            "Bot reativado na conversa %s (resolved → pending)",
            event.conversation_id,
        )
    else:
        logger.error(
            "Falha ao reativar bot na conversa %s: %s",
            event.conversation_id,
            result.get("error"),
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

    result = await resume_bot_conversation(account_id, conversation_id)
    if result.get("ok"):
        logger.info("Bot reativado manualmente na conversa %s", conversation_id)
    return result
