import re
from typing import Any

from sqlalchemy.orm import Session

from harness_platform.models import ContactProfile, TenantCustomField
from harness_platform.phone_utils import normalize_phone

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _validate_field_key(key: str) -> str:
    clean = (key or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not _KEY_RE.match(clean):
        raise ValueError("Chave inválida. Use letras minúsculas, números e _ (ex.: cpf, empreendimento)")
    if clean in {"phone", "telefone", "nome", "name", "email"}:
        raise ValueError(f"Chave '{clean}' é reservada")
    return clean


def field_to_dict(field: TenantCustomField) -> dict:
    return {
        "id": field.id,
        "tenant_id": field.tenant_id,
        "key": field.key,
        "label": field.label,
        "field_type": field.field_type,
        "required": field.required,
        "sort_order": field.sort_order,
        "created_at": field.created_at.isoformat() if field.created_at else None,
    }


def contact_to_dict(contact: ContactProfile) -> dict:
    return {
        "id": contact.id,
        "tenant_id": contact.tenant_id,
        "phone": contact.phone,
        "name": contact.name or "",
        "email": contact.email or "",
        "fields": contact.fields or {},
        "chatwoot_contact_id": contact.chatwoot_contact_id,
        "last_conversation_id": contact.last_conversation_id,
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }


def list_custom_fields(db: Session, tenant_id: str) -> list[dict]:
    rows = (
        db.query(TenantCustomField)
        .filter(TenantCustomField.tenant_id == tenant_id)
        .order_by(TenantCustomField.sort_order, TenantCustomField.id)
        .all()
    )
    return [field_to_dict(r) for r in rows]


def create_custom_field(
    db: Session,
    tenant_id: str,
    *,
    key: str,
    label: str,
    field_type: str = "text",
    required: bool = False,
    sort_order: int = 0,
) -> dict:
    clean_key = _validate_field_key(key)
    exists = (
        db.query(TenantCustomField)
        .filter(TenantCustomField.tenant_id == tenant_id, TenantCustomField.key == clean_key)
        .first()
    )
    if exists:
        raise ValueError(f"Campo '{clean_key}' já existe")
    row = TenantCustomField(
        tenant_id=tenant_id,
        key=clean_key,
        label=(label or clean_key).strip(),
        field_type=(field_type or "text").strip() or "text",
        required=bool(required),
        sort_order=int(sort_order or 0),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return field_to_dict(row)


def update_custom_field(db: Session, tenant_id: str, field_id: int, data: dict) -> dict:
    row = (
        db.query(TenantCustomField)
        .filter(TenantCustomField.tenant_id == tenant_id, TenantCustomField.id == field_id)
        .first()
    )
    if not row:
        raise LookupError("Campo não encontrado")
    if "label" in data and data["label"] is not None:
        row.label = str(data["label"]).strip()
    if "field_type" in data and data["field_type"] is not None:
        row.field_type = str(data["field_type"]).strip() or "text"
    if "required" in data and data["required"] is not None:
        row.required = bool(data["required"])
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = int(data["sort_order"])
    db.commit()
    db.refresh(row)
    return field_to_dict(row)


def delete_custom_field(db: Session, tenant_id: str, field_id: int) -> None:
    row = (
        db.query(TenantCustomField)
        .filter(TenantCustomField.tenant_id == tenant_id, TenantCustomField.id == field_id)
        .first()
    )
    if not row:
        raise LookupError("Campo não encontrado")
    db.delete(row)
    db.commit()


def list_contacts(db: Session, tenant_id: str, *, q: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
    query = db.query(ContactProfile).filter(ContactProfile.tenant_id == tenant_id)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (ContactProfile.phone.ilike(like))
            | (ContactProfile.name.ilike(like))
            | (ContactProfile.email.ilike(like))
        )
    rows = query.order_by(ContactProfile.updated_at.desc()).offset(offset).limit(min(limit, 500)).all()
    return [contact_to_dict(r) for r in rows]


def get_contact(db: Session, tenant_id: str, contact_id: int) -> dict | None:
    row = (
        db.query(ContactProfile)
        .filter(ContactProfile.tenant_id == tenant_id, ContactProfile.id == contact_id)
        .first()
    )
    return contact_to_dict(row) if row else None


def get_contact_by_phone(db: Session, tenant_id: str, phone: str) -> dict | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    row = (
        db.query(ContactProfile)
        .filter(ContactProfile.tenant_id == tenant_id, ContactProfile.phone == normalized)
        .first()
    )
    return contact_to_dict(row) if row else None


def upsert_contact(
    db: Session,
    tenant_id: str,
    phone: str,
    *,
    name: str | None = None,
    email: str | None = None,
    fields: dict[str, Any] | None = None,
    chatwoot_contact_id: int | None = None,
    last_conversation_id: int | None = None,
    merge_fields: bool = True,
) -> dict:
    normalized = normalize_phone(phone)
    if not normalized:
        raise ValueError("Telefone obrigatório")

    row = (
        db.query(ContactProfile)
        .filter(ContactProfile.tenant_id == tenant_id, ContactProfile.phone == normalized)
        .first()
    )
    if not row:
        row = ContactProfile(tenant_id=tenant_id, phone=normalized, fields={})
        db.add(row)

    if name is not None and str(name).strip():
        row.name = str(name).strip()
    if email is not None and str(email).strip():
        row.email = str(email).strip()
    if chatwoot_contact_id is not None:
        row.chatwoot_contact_id = chatwoot_contact_id
    if last_conversation_id is not None:
        row.last_conversation_id = last_conversation_id

    if fields:
        current = dict(row.fields or {})
        if merge_fields:
            current.update({str(k): v for k, v in fields.items() if v is not None and str(v).strip() != ""})
        else:
            current = {str(k): v for k, v in fields.items()}
        row.fields = current

    db.commit()
    db.refresh(row)
    return contact_to_dict(row)


def update_contact(db: Session, tenant_id: str, contact_id: int, data: dict) -> dict:
    row = (
        db.query(ContactProfile)
        .filter(ContactProfile.tenant_id == tenant_id, ContactProfile.id == contact_id)
        .first()
    )
    if not row:
        raise LookupError("Contato não encontrado")
    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip()
    if "email" in data and data["email"] is not None:
        row.email = str(data["email"]).strip()
    if "fields" in data and isinstance(data["fields"], dict):
        if data.get("replace_fields"):
            row.fields = {str(k): v for k, v in data["fields"].items()}
        else:
            current = dict(row.fields or {})
            for k, v in data["fields"].items():
                if v is None:
                    current.pop(str(k), None)
                else:
                    current[str(k)] = v
            row.fields = current
    if "phone" in data and data["phone"]:
        new_phone = normalize_phone(str(data["phone"]))
        if new_phone and new_phone != row.phone:
            clash = (
                db.query(ContactProfile)
                .filter(
                    ContactProfile.tenant_id == tenant_id,
                    ContactProfile.phone == new_phone,
                    ContactProfile.id != contact_id,
                )
                .first()
            )
            if clash:
                raise ValueError("Já existe contato com este telefone")
            row.phone = new_phone
    db.commit()
    db.refresh(row)
    return contact_to_dict(row)


def delete_contact(db: Session, tenant_id: str, contact_id: int) -> None:
    row = (
        db.query(ContactProfile)
        .filter(ContactProfile.tenant_id == tenant_id, ContactProfile.id == contact_id)
        .first()
    )
    if not row:
        raise LookupError("Contato não encontrado")
    db.delete(row)
    db.commit()


def save_contact_fields(db: Session, tenant_id: str, phone: str, updates: dict[str, Any]) -> dict | None:
    """Persiste campos estruturados a partir da IA (tool save_contact_fields)."""
    if not updates:
        return get_contact_by_phone(db, tenant_id, phone)

    name = updates.pop("nome", None) or updates.pop("name", None)
    email = updates.pop("email", None)
    phone_update = updates.pop("phone", None) or updates.pop("telefone", None)
    target_phone = phone_update or phone
    return upsert_contact(
        db,
        tenant_id,
        target_phone,
        name=name,
        email=email,
        fields=updates or None,
    )
