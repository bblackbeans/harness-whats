"""Verifica limites de plano antes de processar mensagens."""

import logging

from harness_platform.db import SessionLocal, is_db_configured
from harness_platform.usage_service import check_tenant_limits
from ingress.models import InboundEvent
from tenants.registry import resolve_tenant

logger = logging.getLogger(__name__)


def is_tenant_blocked(event: InboundEvent) -> dict | None:
    if not is_db_configured():
        return None

    tenant = resolve_tenant(event)
    try:
        with SessionLocal() as db:
            result = check_tenant_limits(db, tenant.id)
    except Exception:
        logger.warning("Falha ao verificar limites do tenant %s", tenant.id, exc_info=True)
        return None

    if result.get("blocked"):
        logger.warning(
            "Tenant %s bloqueado por limite do plano %s",
            tenant.id,
            result.get("plan", {}).get("slug"),
        )
        return result

    if result.get("exceeded") and result.get("mode") == "soft":
        logger.info("Tenant %s acima do limite (modo soft)", tenant.id)

    return None
