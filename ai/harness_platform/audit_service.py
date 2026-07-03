from sqlalchemy.orm import Session

from harness_platform.audit import AuditEvent


def log_audit(
    db: Session,
    *,
    admin_email: str,
    action: str,
    tenant_id: str | None = None,
    detail: str = "",
) -> None:
    db.add(
        AuditEvent(
            admin_email=admin_email,
            action=action,
            tenant_id=tenant_id,
            detail=detail[:2000],
        )
    )
    db.commit()


def list_audit_events(db: Session, *, limit: int = 100) -> list[AuditEvent]:
    return db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).all()
