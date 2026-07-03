from datetime import UTC, datetime

from sqlalchemy.orm import Session

from admin.auth import hash_password
from harness_platform.models import LlmModel, ModelChangeRequest, TenantUser
from harness_platform.schemas import TenantSettings, TenantUpdate
from harness_platform.tenant_service import get_tenant_db, update_tenant


def create_tenant_user(
    db: Session,
    *,
    tenant_id: str,
    email: str,
    password: str,
    name: str = "",
) -> TenantUser:
    if not get_tenant_db(db, tenant_id):
        raise LookupError("Tenant não encontrado")
    existing = (
        db.query(TenantUser)
        .filter(TenantUser.tenant_id == tenant_id, TenantUser.email == email)
        .first()
    )
    if existing:
        raise ValueError("Usuário já existe para este tenant")

    user = TenantUser(
        tenant_id=tenant_id,
        email=email.strip().lower(),
        password_hash=hash_password(password),
        name=name or email,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_tenant_users(db: Session, tenant_id: str) -> list[TenantUser]:
    return db.query(TenantUser).filter(TenantUser.tenant_id == tenant_id).order_by(TenantUser.email).all()


def authenticate_tenant_user(db: Session, email: str, password: str) -> TenantUser | None:
    from admin.auth import verify_password

    user = db.query(TenantUser).filter(TenantUser.email == email.strip().lower(), TenantUser.active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    tenant = get_tenant_db(db, user.tenant_id)
    if not tenant or not tenant.active:
        return None
    return user


def create_model_change_request(
    db: Session,
    *,
    tenant_id: str,
    requested_by: str,
    requested_model_id: int,
    reason: str = "",
) -> ModelChangeRequest:
    model = db.query(LlmModel).filter(LlmModel.id == requested_model_id).first()
    if not model:
        raise ValueError("Modelo não encontrado")

    req = ModelChangeRequest(
        tenant_id=tenant_id,
        requested_by=requested_by,
        requested_model_id=requested_model_id,
        reason=reason,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def list_model_change_requests(db: Session, *, status: str | None = None) -> list[ModelChangeRequest]:
    query = db.query(ModelChangeRequest).order_by(ModelChangeRequest.created_at.desc())
    if status:
        query = query.filter(ModelChangeRequest.status == status)
    return query.limit(100).all()


def approve_model_change_request(db: Session, request_id: int, reviewer_email: str) -> ModelChangeRequest:
    req = db.query(ModelChangeRequest).filter(ModelChangeRequest.id == request_id).first()
    if not req:
        raise LookupError("Solicitação não encontrada")
    if req.status != "pending":
        raise ValueError("Solicitação já processada")

    model = db.query(LlmModel).filter(LlmModel.id == req.requested_model_id).first()
    tenant = get_tenant_db(db, req.tenant_id)
    if not tenant or not model:
        raise LookupError("Tenant ou modelo inválido")

    settings = TenantSettings.model_validate(tenant.settings or {})
    settings.model.llm_model_id = model.id
    settings.model.name = model.model_id
    update_tenant(db, req.tenant_id, TenantUpdate(settings=settings))

    req.status = "approved"
    req.reviewed_by = reviewer_email
    req.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(req)
    return req


def reject_model_change_request(db: Session, request_id: int, reviewer_email: str) -> ModelChangeRequest:
    req = db.query(ModelChangeRequest).filter(ModelChangeRequest.id == request_id).first()
    if not req:
        raise LookupError("Solicitação não encontrada")
    if req.status != "pending":
        raise ValueError("Solicitação já processada")
    req.status = "rejected"
    req.reviewed_by = reviewer_email
    req.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(req)
    return req


def seed_demo_tenant_user(db: Session) -> None:
    import os

    email = os.getenv("TENANT_PORTAL_EMAIL", "").strip()
    password = os.getenv("TENANT_PORTAL_PASSWORD", "").strip()
    tenant_id = os.getenv("TENANT_PORTAL_TENANT_ID", "blackbeans").strip()
    if not email or not password:
        return
    if db.query(TenantUser).filter(TenantUser.email == email).first():
        return
    if get_tenant_db(db, tenant_id):
        create_tenant_user(db, tenant_id=tenant_id, email=email, password=password, name="Cliente Demo")
