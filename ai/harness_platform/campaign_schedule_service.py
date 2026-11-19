"""Disparos recorrentes mensais: cada ciclo cria uma DispatchCampaign e a envia."""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from harness_platform.campaign_service import _resolve_routing, create_campaign, run_campaign
from harness_platform.contact_service import list_contacts
from harness_platform.models import CampaignSchedule, DispatchCampaign

logger = logging.getLogger(__name__)

DEFAULT_TZ = "America/Sao_Paulo"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_next_run(
    day: int, hour: int, minute: int, tz_name: str = DEFAULT_TZ, *, after: datetime | None = None
) -> datetime:
    """Próxima ocorrência estritamente após `after`; dia 29-31 vira o último dia em meses curtos."""
    tz = ZoneInfo(tz_name)
    base = (after or _utc_now()).astimezone(tz)
    year, month = base.year, base.month
    for _ in range(3):
        last = calendar.monthrange(year, month)[1]
        candidate = datetime(year, month, min(day, last), hour, minute, tzinfo=tz)
        if candidate > base:
            return candidate.astimezone(timezone.utc)
        month += 1
        if month > 12:
            month, year = 1, year + 1
    raise RuntimeError("Não foi possível calcular a próxima execução")


def schedule_to_dict(row: CampaignSchedule) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "mode": row.mode,
        "template_name": row.template_name or "",
        "language": row.language or "pt_BR",
        "message": row.message or "",
        "header_image_url": row.header_image_url or "",
        "inbox_id": row.inbox_id,
        "contact_ids": list(row.contact_ids or []),
        "phones": list(row.phones or []),
        "all_contacts": bool(row.all_contacts),
        "recipient_count": len(row.contact_ids or []) + len(row.phones or []),
        "day_of_month": row.day_of_month,
        "hour": row.hour,
        "minute": row.minute,
        "timezone": row.timezone,
        "active": bool(row.active),
        "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "last_campaign_id": row.last_campaign_id,
        "last_error": row.last_error or "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _get(db: Session, tenant_id: str, schedule_id: int) -> CampaignSchedule:
    row = (
        db.query(CampaignSchedule)
        .filter(CampaignSchedule.tenant_id == tenant_id, CampaignSchedule.id == schedule_id)
        .first()
    )
    if not row:
        raise LookupError("Disparo recorrente não encontrado")
    return row


def list_schedules(db: Session, tenant_id: str) -> list[dict]:
    rows = (
        db.query(CampaignSchedule)
        .filter(CampaignSchedule.tenant_id == tenant_id)
        .order_by(CampaignSchedule.id.desc())
        .all()
    )
    return [schedule_to_dict(r) for r in rows]


def create_schedule(db: Session, tenant_id: str, data: dict[str, Any]) -> dict:
    mode = str(data.get("mode") or "template")
    if mode not in {"template", "conversation"}:
        raise ValueError("mode deve ser template ou conversation")
    if mode == "template" and not str(data.get("template_name") or "").strip():
        raise ValueError("template_name obrigatório no modo template")
    if mode == "conversation" and not str(data.get("message") or "").strip():
        raise ValueError("message obrigatório no modo conversation")
    header = str(data.get("header_image_url") or "").strip()
    if header and not header.lower().startswith("https://"):
        raise ValueError("header_image_url precisa começar com https://")
    day = int(data.get("day_of_month") or 1)
    hour = int(data.get("hour") if data.get("hour") is not None else 9)
    minute = int(data.get("minute") or 0)
    if not 1 <= day <= 31 or not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Dia (1-31), hora (0-23) ou minuto (0-59) inválidos")
    contact_ids = [int(x) for x in (data.get("contact_ids") or [])]
    phones = [str(p).strip() for p in (data.get("phones") or []) if str(p).strip()]
    all_contacts = bool(data.get("all_contacts"))
    if not (contact_ids or phones or all_contacts):
        raise ValueError("Informe destinatários ou marque 'todos os contatos do CRM'")
    account_id, inbox_id, _ = _resolve_routing(tenant_id, data.get("account_id"), data.get("inbox_id"))
    tz = DEFAULT_TZ
    row = CampaignSchedule(
        tenant_id=tenant_id,
        name=str(data.get("name") or "Disparo mensal").strip() or "Disparo mensal",
        mode=mode,
        template_name=str(data.get("template_name") or "").strip(),
        language=str(data.get("language") or "pt_BR"),
        message=str(data.get("message") or ""),
        header_image_url=header,
        account_id=account_id,
        inbox_id=inbox_id,
        contact_ids=contact_ids,
        phones=phones,
        all_contacts=all_contacts,
        day_of_month=day,
        hour=hour,
        minute=minute,
        timezone=tz,
        active=True,
        next_run_at=compute_next_run(day, hour, minute, tz),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return schedule_to_dict(row)


def update_schedule(db: Session, tenant_id: str, schedule_id: int, data: dict[str, Any]) -> dict:
    """Edita campos do disparo recorrente (destinatários e caixa de entrada permanecem)."""
    row = _get(db, tenant_id, schedule_id)
    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip() or row.name
    if "template_name" in data and data["template_name"] is not None:
        row.template_name = str(data["template_name"]).strip()
    if "language" in data and data["language"] is not None:
        row.language = str(data["language"]).strip() or "pt_BR"
    if "message" in data and data["message"] is not None:
        row.message = str(data["message"])
    if "header_image_url" in data and data["header_image_url"] is not None:
        header = str(data["header_image_url"]).strip()
        if header and not header.lower().startswith("https://"):
            raise ValueError("header_image_url precisa começar com https://")
        row.header_image_url = header
    if "all_contacts" in data and data["all_contacts"] is not None:
        row.all_contacts = bool(data["all_contacts"])
    if row.mode == "template" and not (row.template_name or "").strip():
        raise ValueError("template_name obrigatório no modo template")
    if row.mode == "conversation" and not (row.message or "").strip():
        raise ValueError("message obrigatório no modo conversation")
    day = int(data["day_of_month"]) if data.get("day_of_month") is not None else row.day_of_month
    hour = int(data["hour"]) if data.get("hour") is not None else row.hour
    minute = int(data["minute"]) if data.get("minute") is not None else row.minute
    if not 1 <= day <= 31 or not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Dia (1-31), hora (0-23) ou minuto (0-59) inválidos")
    if (day, hour, minute) != (row.day_of_month, row.hour, row.minute):
        row.day_of_month, row.hour, row.minute = day, hour, minute
        if row.active:
            row.next_run_at = compute_next_run(day, hour, minute, row.timezone)
    db.commit()
    db.refresh(row)
    return schedule_to_dict(row)


def set_schedule_active(db: Session, tenant_id: str, schedule_id: int, active: bool) -> dict:
    row = _get(db, tenant_id, schedule_id)
    row.active = active
    if active:
        row.next_run_at = compute_next_run(row.day_of_month, row.hour, row.minute, row.timezone)
    db.commit()
    db.refresh(row)
    return schedule_to_dict(row)


def delete_schedule(db: Session, tenant_id: str, schedule_id: int) -> None:
    db.delete(_get(db, tenant_id, schedule_id))
    db.commit()


def list_due_schedules(db: Session, *, limit: int = 10) -> list[CampaignSchedule]:
    return (
        db.query(CampaignSchedule)
        .filter(
            CampaignSchedule.active.is_(True),
            CampaignSchedule.next_run_at.isnot(None),
            CampaignSchedule.next_run_at <= _utc_now(),
        )
        .order_by(CampaignSchedule.next_run_at.asc())
        .limit(limit)
        .all()
    )


async def run_schedule(db: Session, tenant_id: str, schedule_id: int) -> dict:
    """Gera a campanha do ciclo e a envia. Avança next_run_at antes, evitando disparo duplo."""
    row = _get(db, tenant_id, schedule_id)
    now = _utc_now()
    tz = ZoneInfo(row.timezone or DEFAULT_TZ)
    label = now.astimezone(tz).strftime("%m/%Y")
    row.last_run_at = now
    row.next_run_at = compute_next_run(row.day_of_month, row.hour, row.minute, row.timezone, after=now)
    row.last_error = ""
    db.commit()

    contact_ids = list(row.contact_ids or [])
    if row.all_contacts:
        contact_ids = [c["id"] for c in list_contacts(db, tenant_id, limit=500) if c.get("phone")]
    try:
        created = create_campaign(
            db,
            tenant_id,
            {
                "name": f"{row.name} — {label}",
                "mode": row.mode,
                "template_name": row.template_name,
                "language": row.language,
                "message": row.message,
                "header_image_url": row.header_image_url,
                "account_id": row.account_id,
                "inbox_id": row.inbox_id,
                "contact_ids": contact_ids,
                "phones": list(row.phones or []),
            },
        )
        camp = db.query(DispatchCampaign).filter(DispatchCampaign.id == created["id"]).first()
        camp.schedule_id = row.id
        row.last_campaign_id = camp.id
        db.commit()
        return await run_campaign(db, tenant_id, camp.id)
    except Exception as error:
        db.rollback()
        row = _get(db, tenant_id, schedule_id)
        row.last_error = str(error)[:500]
        db.commit()
        raise
