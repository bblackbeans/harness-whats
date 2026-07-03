import asyncio
import logging
import os

from handoff.resume import ensure_bot_controls_conversation
from harness_platform.limit_enforcement import is_tenant_blocked
from harness.runner import run_conversation_turn
from ingress.models import InboundEvent
from ops.lifecycle import Lifecycle, record_event

logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.getenv("INGRESS_MAX_RETRIES", "3"))
RETRY_BASE_SECONDS = float(os.getenv("INGRESS_RETRY_BASE_SECONDS", "1.5"))


async def process_inbound(event: InboundEvent) -> dict:
    record_event(
        delivery_id=event.delivery_id,
        message_id=event.message_id,
        conversation_id=event.conversation_id,
        status=Lifecycle.RECEIVED,
        detail=event.text[:120],
    )

    block = is_tenant_blocked(event)
    if block:
        record_event(
            delivery_id=event.delivery_id,
            message_id=event.message_id,
            conversation_id=event.conversation_id,
            status=Lifecycle.IGNORED,
            detail="plan_limit_exceeded",
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
            elif lifecycle == "send_failed":
                status = Lifecycle.FAILED
            elif lifecycle == "replied" or result.get("outbound_text"):
                status = Lifecycle.REPLIED
            else:
                status = Lifecycle.IGNORED

            record_event(
                delivery_id=event.delivery_id,
                message_id=event.message_id,
                conversation_id=event.conversation_id,
                status=status,
                detail=result.get("handoff_reason") or result.get("intent", ""),
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
    )
    raise last_error or RuntimeError("processamento falhou")
