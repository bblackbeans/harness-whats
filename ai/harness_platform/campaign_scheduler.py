"""Scheduler de campanhas agendadas (poll simples no processo FastAPI)."""

from __future__ import annotations

import asyncio
import logging
import os

from harness_platform.campaign_service import list_due_scheduled_campaigns, run_campaign
from harness_platform.db import SessionLocal

logger = logging.getLogger(__name__)

_POLL_SECONDS = int(os.getenv("CAMPAIGN_SCHEDULER_POLL_SECONDS", "30"))
_task: asyncio.Task | None = None


async def _poll_loop() -> None:
    logger.info("Campaign scheduler iniciado (poll=%ss)", _POLL_SECONDS)
    while True:
        try:
            db = SessionLocal()
            try:
                due = list_due_scheduled_campaigns(db, limit=10)
                items = [(row.tenant_id, row.id) for row in due]
            finally:
                db.close()

            for tenant_id, campaign_id in items:
                db = SessionLocal()
                try:
                    logger.info(
                        "Executando campanha agendada tenant=%s id=%s",
                        tenant_id,
                        campaign_id,
                    )
                    await run_campaign(db, tenant_id, campaign_id)
                except Exception:
                    logger.exception(
                        "Falha na campanha agendada tenant=%s id=%s",
                        tenant_id,
                        campaign_id,
                    )
                finally:
                    db.close()
        except Exception:
            logger.exception("Erro no loop do campaign scheduler")
        await asyncio.sleep(max(5, _POLL_SECONDS))


def start_campaign_scheduler() -> None:
    global _task
    if _task and not _task.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("Sem event loop — scheduler de campanhas não iniciado")
        return
    _task = loop.create_task(_poll_loop())
