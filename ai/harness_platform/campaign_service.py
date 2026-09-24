"""Campanhas de disparo WhatsApp via Chatwoot (API oficial Meta / templates).

Requisitos do canal:
- Inbox WhatsApp Cloud (Meta) no Chatwoot do tenant
- Templates aprovados no Meta Business Manager para fora da janela de 24h
- CHATWOOT_ADMIN_TOKEN (ou bot com permissão) para criar contato/conversa
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agent.nodes import generate_dispatch_message
from harness_platform.contact_service import get_contact, upsert_contact
from harness_platform.models import ContactProfile, DispatchCampaign, DispatchCampaignRecipient
from harness_platform.phone_utils import normalize_phone
from integrations.chatwoot import (
    default_account_id,
    ensure_contact_conversation,
    send_message,
    send_template,
)
from tenants.registry import get_tenant

logger = logging.getLogger(__name__)

CHANNEL_REQUIREMENTS = (
    "Disparo WhatsApp exige inbox WhatsApp Cloud (API oficial Meta) no Chatwoot "
    "e templates aprovados para iniciar conversa / fora da janela de 24h."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def recipient_to_dict(row: DispatchCampaignRecipient) -> dict:
    return {
        "id": row.id,
        "campaign_id": row.campaign_id,
        "contact_id": row.contact_id,
        "phone": row.phone,
        "name": row.name or "",
        "chatwoot_contact_id": row.chatwoot_contact_id,
        "conversation_id": row.conversation_id,
        "status": row.status,
        "error": row.error or "",
        "variables": row.variables or {},
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
    }


def campaign_to_dict(row: DispatchCampaign, *, include_recipients: bool = False) -> dict:
    recipients = list(row.recipients or [])
    counts = {"pending": 0, "sent": 0, "failed": 0, "skipped": 0}
    for r in recipients:
        counts[r.status] = counts.get(r.status, 0) + 1
    data = {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "name": row.name,
        "mode": row.mode,
        "template_name": row.template_name or "",
        "language": row.language or "pt_BR",
        "message": row.message or "",
        "account_id": row.account_id,
        "inbox_id": row.inbox_id,
        "agent_id": row.agent_id,
        "flow_id": row.flow_id,
        "status": row.status,
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "default_params": row.default_params or {},
        "error": row.error or "",
        "channel_note": CHANNEL_REQUIREMENTS,
        "counts": counts,
        "recipient_count": len(recipients),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_recipients:
        data["recipients"] = [recipient_to_dict(r) for r in recipients]
    return data


def list_campaigns(db: Session, tenant_id: str) -> list[dict]:
    rows = (
        db.query(DispatchCampaign)
        .filter(DispatchCampaign.tenant_id == tenant_id)
        .order_by(DispatchCampaign.id.desc())
        .all()
    )
    return [campaign_to_dict(r) for r in rows]


def get_campaign(db: Session, tenant_id: str, campaign_id: int) -> dict | None:
    row = (
        db.query(DispatchCampaign)
        .filter(DispatchCampaign.tenant_id == tenant_id, DispatchCampaign.id == campaign_id)
        .first()
    )
    return campaign_to_dict(row, include_recipients=True) if row else None


def _resolve_routing(tenant_id: str, account_id: int | None, inbox_id: int | None) -> tuple[int, int, str]:
    tenant = get_tenant(tenant_id)
    accounts = tenant.routing.chatwoot_account_ids or []
    inboxes = tenant.routing.chatwoot_inbox_ids or []
    resolved_account = account_id
    if resolved_account is None:
        if accounts:
            resolved_account = int(accounts[0])
        else:
            resolved_account = default_account_id()
    resolved_inbox = inbox_id if inbox_id is not None else (int(inboxes[0]) if inboxes else None)
    if resolved_inbox is None:
        raise ValueError(
            "inbox_id obrigatório: configure chatwoot_inbox_ids no cliente "
            "(inbox WhatsApp Cloud / Meta) ou informe na campanha."
        )
    return int(resolved_account), int(resolved_inbox), tenant.routing.chatwoot_bot_token or ""


def create_campaign(db: Session, tenant_id: str, data: dict[str, Any]) -> dict:
    mode = str(data.get("mode") or "template")
    if mode not in {"template", "conversation"}:
        raise ValueError("mode deve ser template ou conversation")
    if mode == "template" and not str(data.get("template_name") or "").strip():
        raise ValueError("template_name obrigatório no modo template (template Meta aprovado)")
    if mode == "conversation" and not str(data.get("message") or "").strip():
        raise ValueError("message obrigatório no modo conversation")

    account_id, inbox_id, _token = _resolve_routing(
        tenant_id,
        data.get("account_id"),
        data.get("inbox_id"),
    )

    row = DispatchCampaign(
        tenant_id=tenant_id,
        name=str(data.get("name") or "Campanha").strip() or "Campanha",
        mode=mode,
        template_name=str(data.get("template_name") or "").strip(),
        language=str(data.get("language") or "pt_BR"),
        message=str(data.get("message") or ""),
        account_id=account_id,
        inbox_id=inbox_id,
        agent_id=data.get("agent_id"),
        flow_id=data.get("flow_id"),
        status="draft",
        default_params=dict(data.get("default_params") or {}),
    )
    db.add(row)
    db.flush()

    recipients_in = list(data.get("recipients") or [])
    contact_ids = [int(x) for x in (data.get("contact_ids") or []) if str(x).strip()]
    phones = [str(p) for p in (data.get("phones") or []) if str(p).strip()]

    seen_phones: set[str] = set()

    for cid in contact_ids:
        profile = get_contact(db, tenant_id, cid)
        if not profile:
            continue
        phone = normalize_phone(str(profile.get("phone") or ""))
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        variables = dict(data.get("default_params") or {})
        variables.update(
            {
                "nome": profile.get("name") or "",
                "name": profile.get("name") or "",
                "email": profile.get("email") or "",
                "phone": phone,
                **(profile.get("fields") or {}),
            }
        )
        db.add(
            DispatchCampaignRecipient(
                campaign_id=row.id,
                contact_id=cid,
                phone=phone,
                name=str(profile.get("name") or ""),
                variables=variables,
            )
        )

    for raw_phone in phones:
        phone = normalize_phone(raw_phone)
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        variables = dict(data.get("default_params") or {})
        variables["phone"] = phone
        db.add(
            DispatchCampaignRecipient(
                campaign_id=row.id,
                phone=phone,
                name="",
                variables=variables,
            )
        )

    for item in recipients_in:
        if not isinstance(item, dict):
            continue
        phone = normalize_phone(str(item.get("phone") or ""))
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        variables = dict(data.get("default_params") or {})
        variables.update(dict(item.get("variables") or item.get("processed_params") or {}))
        variables.setdefault("phone", phone)
        if item.get("name"):
            variables.setdefault("nome", item["name"])
            variables.setdefault("name", item["name"])
        contact_id = item.get("contact_id")
        db.add(
            DispatchCampaignRecipient(
                campaign_id=row.id,
                contact_id=int(contact_id) if contact_id is not None else None,
                phone=phone,
                name=str(item.get("name") or ""),
                variables=variables,
            )
        )

    if not seen_phones:
        db.rollback()
        raise ValueError("Informe contact_ids, phones ou recipients com telefone")

    db.commit()
    db.refresh(row)
    return campaign_to_dict(row, include_recipients=True)


def schedule_campaign(db: Session, tenant_id: str, campaign_id: int, scheduled_at: datetime) -> dict:
    row = (
        db.query(DispatchCampaign)
        .filter(DispatchCampaign.tenant_id == tenant_id, DispatchCampaign.id == campaign_id)
        .first()
    )
    if not row:
        raise LookupError("Campanha não encontrada")
    if row.status not in {"draft", "scheduled", "failed"}:
        raise ValueError(f"Não é possível agendar campanha com status={row.status}")
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    if scheduled_at <= _utc_now():
        raise ValueError("scheduled_at deve ser no futuro")
    row.scheduled_at = scheduled_at
    row.status = "scheduled"
    row.error = ""
    db.commit()
    db.refresh(row)
    return campaign_to_dict(row, include_recipients=True)


def cancel_campaign(db: Session, tenant_id: str, campaign_id: int) -> dict:
    row = (
        db.query(DispatchCampaign)
        .filter(DispatchCampaign.tenant_id == tenant_id, DispatchCampaign.id == campaign_id)
        .first()
    )
    if not row:
        raise LookupError("Campanha não encontrada")
    if row.status == "running":
        raise ValueError("Campanha em execução — aguarde terminar")
    if row.status in {"completed", "cancelled"}:
        return campaign_to_dict(row, include_recipients=True)
    row.status = "cancelled"
    db.commit()
    db.refresh(row)
    return campaign_to_dict(row, include_recipients=True)


def delete_campaign(db: Session, tenant_id: str, campaign_id: int) -> None:
    row = (
        db.query(DispatchCampaign)
        .filter(DispatchCampaign.tenant_id == tenant_id, DispatchCampaign.id == campaign_id)
        .first()
    )
    if not row:
        raise LookupError("Campanha não encontrada")
    if row.status == "running":
        raise ValueError("Campanha em execução — aguarde terminar antes de excluir")
    db.delete(row)
    db.commit()


async def _send_one_recipient(
    *,
    tenant_id: str,
    campaign: DispatchCampaign,
    recipient: DispatchCampaignRecipient,
    bot_token: str,
) -> None:
    account_id = int(campaign.account_id or 0)
    inbox_id = int(campaign.inbox_id or 0)
    ensured = await ensure_contact_conversation(
        account_id,
        phone=recipient.phone,
        inbox_id=inbox_id,
        name=recipient.name or "",
        email=str((recipient.variables or {}).get("email") or ""),
        bot_token=bot_token or None,
    )
    if not ensured.get("ok") or not ensured.get("conversation_id"):
        recipient.status = "failed"
        recipient.error = str(ensured.get("error") or "Falha ao criar conversa no Chatwoot")
        return

    conversation_id = int(ensured["conversation_id"])
    recipient.conversation_id = conversation_id
    recipient.chatwoot_contact_id = ensured.get("chatwoot_contact_id")

    # Sync CRM local
    try:
        from harness_platform.db import SessionLocal

        db = SessionLocal()
        try:
            upsert_contact(
                db,
                tenant_id,
                recipient.phone,
                name=recipient.name or None,
                chatwoot_contact_id=recipient.chatwoot_contact_id,
                last_conversation_id=conversation_id,
                fields={
                    k: v
                    for k, v in (recipient.variables or {}).items()
                    if k not in {"nome", "name", "email", "phone", "telefone"}
                }
                or None,
            )
        finally:
            db.close()
    except Exception:
        logger.warning("Falha ao upsert contato local no disparo", exc_info=True)

    params = dict(campaign.default_params or {})
    params.update(dict(recipient.variables or {}))

    if campaign.mode == "template":
        response = await send_template(
            account_id=account_id,
            conversation_id=conversation_id,
            template_name=campaign.template_name,
            language=campaign.language or "pt_BR",
            processed_params=params,
            content=campaign.message or campaign.template_name,
            bot_token=bot_token or None,
        )
    else:
        text = generate_dispatch_message(campaign.message, params, tenant_id=tenant_id)
        response = await send_message(
            account_id,
            conversation_id,
            text,
            bot_token=bot_token or None,
        )

    if response.get("ok"):
        recipient.status = "sent"
        recipient.error = ""
        recipient.sent_at = _utc_now()
        if campaign.agent_id or campaign.flow_id:
            try:
                from harness_platform.contact_service import update_contact
                from harness_platform.db import SessionLocal

                db = SessionLocal()
                try:
                    row = (
                        db.query(ContactProfile)
                        .filter(
                            ContactProfile.tenant_id == tenant_id,
                            ContactProfile.phone == recipient.phone,
                        )
                        .first()
                    )
                    if row:
                        prefs = dict(row.fields or {})
                        if campaign.agent_id:
                            prefs["_preferred_agent_id"] = campaign.agent_id
                        if campaign.flow_id:
                            prefs["_preferred_flow_id"] = campaign.flow_id
                        update_contact(db, tenant_id, row.id, {"fields": prefs})
                finally:
                    db.close()
            except Exception:
                logger.warning("Falha ao gravar preferência pós-disparo", exc_info=True)
    else:
        recipient.status = "failed"
        recipient.error = str(response.get("error") or "Falha no envio")


async def run_campaign(db: Session, tenant_id: str, campaign_id: int) -> dict:
    row = (
        db.query(DispatchCampaign)
        .filter(DispatchCampaign.tenant_id == tenant_id, DispatchCampaign.id == campaign_id)
        .first()
    )
    if not row:
        raise LookupError("Campanha não encontrada")
    if row.status == "running":
        raise ValueError("Campanha já em execução")
    if row.status == "cancelled":
        raise ValueError("Campanha cancelada")

    try:
        account_id, inbox_id, bot_token = _resolve_routing(tenant_id, row.account_id, row.inbox_id)
    except ValueError as error:
        row.status = "failed"
        row.error = str(error)
        db.commit()
        raise

    row.account_id = account_id
    row.inbox_id = inbox_id
    row.status = "running"
    row.started_at = _utc_now()
    row.error = ""
    db.commit()

    recipients = (
        db.query(DispatchCampaignRecipient)
        .filter(
            DispatchCampaignRecipient.campaign_id == row.id,
            DispatchCampaignRecipient.status == "pending",
        )
        .all()
    )

    for recipient in recipients:
        try:
            await _send_one_recipient(
                tenant_id=tenant_id,
                campaign=row,
                recipient=recipient,
                bot_token=bot_token,
            )
        except Exception as error:
            logger.exception("Falha no destinatário campaign=%s phone=%s", row.id, recipient.phone)
            recipient.status = "failed"
            recipient.error = str(error)
        db.commit()

    db.refresh(row)
    failed = sum(1 for r in row.recipients if r.status == "failed")
    sent = sum(1 for r in row.recipients if r.status == "sent")
    row.finished_at = _utc_now()
    row.status = "completed" if sent > 0 or failed == 0 else "failed"
    if failed and not sent:
        row.error = "Todos os envios falharam"
    elif failed:
        row.error = f"{failed} falha(s), {sent} enviado(s)"
    else:
        row.error = ""
    db.commit()
    db.refresh(row)
    return campaign_to_dict(row, include_recipients=True)


def list_due_scheduled_campaigns(db: Session, *, limit: int = 20) -> list[DispatchCampaign]:
    now = _utc_now()
    return (
        db.query(DispatchCampaign)
        .filter(
            DispatchCampaign.status == "scheduled",
            DispatchCampaign.scheduled_at.isnot(None),
            DispatchCampaign.scheduled_at <= now,
        )
        .order_by(DispatchCampaign.scheduled_at.asc())
        .limit(limit)
        .all()
    )
