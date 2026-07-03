from datetime import UTC, datetime

from sqlalchemy.orm import Session, joinedload

from harness_platform.models import Plan, TenantSubscription


def list_plans(db: Session, *, active_only: bool = False) -> list[Plan]:
    query = db.query(Plan)
    if active_only:
        query = query.filter(Plan.active.is_(True))
    return query.order_by(Plan.name).all()


def get_plan(db: Session, plan_id: int) -> Plan | None:
    return db.query(Plan).filter(Plan.id == plan_id).first()


def get_plan_by_slug(db: Session, slug: str) -> Plan | None:
    return db.query(Plan).filter(Plan.slug == slug).first()


def create_plan(
    db: Session,
    *,
    slug: str,
    name: str,
    description: str = "",
    limits: dict | None = None,
) -> Plan:
    plan = Plan(
        slug=slug.strip().lower(),
        name=name,
        description=description,
        limits=limits or {},
        active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan(db: Session, plan_id: int, **fields) -> Plan:
    plan = get_plan(db, plan_id)
    if not plan:
        raise LookupError("Plano não encontrado")
    for key, value in fields.items():
        if value is not None and hasattr(plan, key):
            setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    return plan


def get_tenant_subscription(db: Session, tenant_id: str) -> TenantSubscription | None:
    return (
        db.query(TenantSubscription)
        .options(joinedload(TenantSubscription.plan))
        .filter(TenantSubscription.tenant_id == tenant_id, TenantSubscription.active.is_(True))
        .first()
    )


def assign_plan(db: Session, tenant_id: str, plan_id: int) -> TenantSubscription:
    plan = get_plan(db, plan_id)
    if not plan:
        raise LookupError("Plano não encontrado")

    existing = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id).first()
    if existing:
        existing.plan_id = plan_id
        existing.active = True
        existing.started_at = datetime.now(UTC)
        existing.ends_at = None
        db.commit()
        db.refresh(existing)
        return existing

    sub = TenantSubscription(tenant_id=tenant_id, plan_id=plan_id, active=True)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def seed_default_plans(db: Session) -> None:
    if db.query(Plan).first():
        return
    defaults = [
        (
            "starter",
            "Starter",
            "Plano inicial",
            {
                "max_llm_calls_month": 500,
                "max_tokens_month": 200_000,
                "enforce_mode": "soft",
            },
        ),
        (
            "pro",
            "Pro",
            "Plano profissional",
            {
                "max_llm_calls_month": 5000,
                "max_tokens_month": 2_000_000,
                "enforce_mode": "soft",
            },
        ),
        (
            "enterprise",
            "Enterprise",
            "Limites personalizados",
            {
                "max_llm_calls_month": 0,
                "max_tokens_month": 0,
                "enforce_mode": "soft",
            },
        ),
    ]
    for slug, name, desc, limits in defaults:
        create_plan(db, slug=slug, name=name, description=desc, limits=limits)


def plan_to_dict(plan: Plan) -> dict:
    return {
        "id": plan.id,
        "slug": plan.slug,
        "name": plan.name,
        "description": plan.description,
        "limits": plan.limits or {},
        "active": plan.active,
    }
