import asyncio
import logging
import os

from handoff.resume import ensure_bot_controls_conversation
from harness_platform.limit_enforcement import is_tenant_blocked
from harness.runner import run_conversation_turn
from ingress.models import InboundEvent
from ops.lifecycle import Lifecycle, record_event
from tenants import resolve_tenant

logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.getenv("INGRESS_MAX_RETRIES", "3"))
RETRY_BASE_SECONDS = float(os.getenv("INGRESS_RETRY_BASE_SECONDS", "1.5"))


async def process_inbound(event: InboundEvent) -> dict:
    tenant = resolve_tenant(event)
    log_ctx = {
        "tenant_id": tenant.id,
        "account_id": event.account_id,
        "inbox_id": event.inbox_id,
    }

    record_event(
        delivery_id=event.delivery_id,
        message_id=event.message_id,
        conversation_id=event.conversation_id,
        status=Lifecycle.RECEIVED,
        detail=event.text[:120],
        **log_ctx,
    )

    block = is_tenant_blocked(event)
    if block:
        record_event(
            delivery_id=event.delivery_id,
            message_id=event.message_id,
            conversation_id=event.conversation_id,
            status=Lifecycle.IGNORED,
            detail="plan_limit_exceeded",
            **log_ctx,
        )
        return {"lifecycle_status": "limit_exceeded", "plan": block.get("plan")}

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            record_event(
                delivery_id=event.delivery_id,
                message_id=event.message_id,
                conversation_id=event.conversation_id,
                status=Lifecycle.PROCESSING,
                detail=f"attempt={attempt}",
                **log_ctx,
            )

            resume_result = await ensure_bot_controls_conversation(event)
            if not resume_result.get("ok") and not resume_result.get("skipped"):
                raise RuntimeError(
                    f"falha ao reativar bot: {resume_result.get('error', 'unknown')}"
                )

            result = await run_conversation_turn(event)

            lifecycle = result.get("lifecycle_status", "")
            if lifecycle == "handed_off":
                status = Lifecycle.HANDED_OFF
                detail = result.get("outbound_text") or result.get("handoff_reason") or "handed_off"
            elif lifecycle == "handoff_failed":
                status = Lifecycle.FAILED
                detail = result.get("handoff_reason") or "handoff_failed"
            elif lifecycle == "send_failed":
                status = Lifecycle.FAILED
                detail = result.get("handoff_reason") or "send_failed"
            elif lifecycle == "replied" or result.get("outbound_text"):
                status = Lifecycle.REPLIED
                detail = (result.get("outbound_text") or result.get("intent") or "")[:120]
            else:
                status = Lifecycle.IGNORED
                detail = result.get("handoff_reason") or result.get("intent", "") or lifecycle

            record_event(
                delivery_id=event.delivery_id,
                message_id=event.message_id,
                conversation_id=event.conversation_id,
                status=status,
                detail=detail,
                **log_ctx,
            )

            return {
                "processed": True,
                "conversation_id": event.conversation_id,
                "phone": event.phone,
                "intent": result.get("intent"),
                "replied": bool(result.get("outbound_text")),
                "handoff": bool(result.get("handoff_to_human")),
            }
        except Exception as error:
            last_error = error
            logger.exception("Falha ao processar mensagem (tentativa %s)", attempt)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BASE_SECONDS * attempt)

    record_event(
        delivery_id=event.delivery_id,
        message_id=event.message_id,
        conversation_id=event.conversation_id,
        status=Lifecycle.FAILED,
        detail=str(last_error),
        **log_ctx,
    )
    raise last_error or RuntimeError("processamento falhou")
