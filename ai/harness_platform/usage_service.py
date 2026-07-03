from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from harness_platform.models import LlmModel, UsageEvent
from harness_platform.plan_service import get_tenant_subscription


def record_usage(
    db: Session,
    *,
    tenant_id: str | None,
    model_ref: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_estimate: float = 0.0,
) -> None:
    db.add(
        UsageEvent(
            tenant_id=tenant_id,
            model_ref=model_ref,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_estimate=cost_estimate,
        )
    )
    db.commit()


def estimate_cost(model: LlmModel | None, tokens_in: int, tokens_out: int) -> float:
    if not model:
        return 0.0
    return (tokens_in / 1_000_000) * model.cost_per_1m_input + (
        tokens_out / 1_000_000
    ) * model.cost_per_1m_output


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def tenant_usage_month(db: Session, tenant_id: str) -> dict:
    since = _month_start()
    row = (
        db.query(
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.tokens_in), 0),
            func.coalesce(func.sum(UsageEvent.tokens_out), 0),
            func.coalesce(func.sum(UsageEvent.cost_estimate), 0),
        )
        .filter(UsageEvent.tenant_id == tenant_id, UsageEvent.created_at >= since)
        .one()
    )
    calls, tin, tout, cost = row
    return {
        "calls": int(calls or 0),
        "tokens_in": int(tin or 0),
        "tokens_out": int(tout or 0),
        "tokens_total": int(tin or 0) + int(tout or 0),
        "cost_estimate": float(cost or 0),
        "period": "month",
        "since": since.isoformat(),
    }


def usage_summary_by_tenant(db: Session, *, tenant_id: str | None = None) -> list[dict]:
    since = _month_start()
    query = (
        db.query(
            UsageEvent.tenant_id,
            func.count(UsageEvent.id),
            func.sum(UsageEvent.tokens_in),
            func.sum(UsageEvent.tokens_out),
            func.sum(UsageEvent.cost_estimate),
        )
        .filter(UsageEvent.created_at >= since)
    )
    if tenant_id:
        query = query.filter(UsageEvent.tenant_id == tenant_id)
    rows = query.group_by(UsageEvent.tenant_id).all()
    return [
        {
            "tenant_id": tenant_id,
            "calls": calls or 0,
            "tokens_in": int(tokens_in or 0),
            "tokens_out": int(tokens_out or 0),
            "tokens_total": int(tokens_in or 0) + int(tokens_out or 0),
            "cost_estimate": float(cost or 0),
        }
        for tenant_id, calls, tokens_in, tokens_out, cost in rows
    ]


def usage_by_model(db: Session, *, tenant_id: str | None = None) -> list[dict]:
    since = _month_start()
    query = db.query(
        UsageEvent.model_ref,
        func.count(UsageEvent.id),
        func.sum(UsageEvent.tokens_in),
        func.sum(UsageEvent.tokens_out),
        func.sum(UsageEvent.cost_estimate),
    ).filter(UsageEvent.created_at >= since)
    if tenant_id:
        query = query.filter(UsageEvent.tenant_id == tenant_id)
    rows = query.group_by(UsageEvent.model_ref).all()
    return [
        {
            "model_ref": model_ref or "unknown",
            "calls": calls or 0,
            "tokens_total": int(tokens_in or 0) + int(tokens_out or 0),
            "cost_estimate": float(cost or 0),
        }
        for model_ref, calls, tokens_in, tokens_out, cost in rows
    ]


def usage_daily(db: Session, *, tenant_id: str | None = None, days: int = 30) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=days)
    query = db.query(
        func.date_trunc("day", UsageEvent.created_at).label("day"),
        func.count(UsageEvent.id),
        func.sum(UsageEvent.cost_estimate),
    ).filter(UsageEvent.created_at >= since)
    if tenant_id:
        query = query.filter(UsageEvent.tenant_id == tenant_id)
    rows = query.group_by("day").order_by("day").all()
    return [
        {
            "date": day.date().isoformat() if day else None,
            "calls": calls or 0,
            "cost_estimate": float(cost or 0),
        }
        for day, calls, cost in rows
    ]


def check_tenant_limits(db: Session, tenant_id: str) -> dict:
    usage = tenant_usage_month(db, tenant_id)
    sub = get_tenant_subscription(db, tenant_id)
    if not sub or not sub.plan:
        return {"allowed": True, "mode": "none", "usage": usage, "limits": {}}

    limits = sub.plan.limits or {}
    max_calls = int(limits.get("max_llm_calls_month") or 0)
    max_tokens = int(limits.get("max_tokens_month") or 0)
    mode = str(limits.get("enforce_mode") or "soft")

    over_calls = max_calls > 0 and usage["calls"] >= max_calls
    over_tokens = max_tokens > 0 and usage["tokens_total"] >= max_tokens
    exceeded = over_calls or over_tokens

    return {
        "allowed": not exceeded or mode == "soft",
        "blocked": exceeded and mode == "hard",
        "exceeded": exceeded,
        "mode": mode,
        "plan": {"id": sub.plan.id, "slug": sub.plan.slug, "name": sub.plan.name},
        "usage": usage,
        "limits": limits,
    }
