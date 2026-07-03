import os

from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from harness_platform.crypto import decrypt_value
from harness_platform.db import SessionLocal, is_db_configured
from harness_platform.models import LlmModel, LlmProvider, TenantAllowedModel
from harness_platform.usage_service import estimate_cost, record_usage
from tenants.config import TenantConfig


def _fallback_openai(tenant: TenantConfig | None) -> ChatOpenAI | None:
    model = tenant.model if tenant else None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return ChatOpenAI(
        model=model.name if model else os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=model.temperature if model else 0.3,
        api_key=api_key,
    )


def _resolve_model_row(db: Session, tenant: TenantConfig) -> LlmModel | None:
    model_id = tenant.model.llm_model_id
    if model_id:
        return db.query(LlmModel).filter(LlmModel.id == model_id).first()

    allowed = (
        db.query(TenantAllowedModel)
        .filter(TenantAllowedModel.tenant_id == tenant.id, TenantAllowedModel.is_default.is_(True))
        .first()
    )
    if allowed:
        return db.query(LlmModel).filter(LlmModel.id == allowed.model_id).first()

    return (
        db.query(LlmModel)
        .join(LlmProvider)
        .filter(LlmModel.model_id == tenant.model.name, LlmProvider.active.is_(True))
        .first()
    )


def get_llm(tenant: TenantConfig | None = None) -> ChatOpenAI | None:
    if not tenant or not is_db_configured():
        return _fallback_openai(tenant)

    try:
        with SessionLocal() as db:
            row = _resolve_model_row(db, tenant)
            if not row:
                return _fallback_openai(tenant)

            provider = db.query(LlmProvider).filter(LlmProvider.id == row.provider_id).first()
            if not provider or not provider.active:
                return _fallback_openai(tenant)

            api_key = decrypt_value(provider.encrypted_api_key) or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None

            if provider.provider_type != "openai":
                return _fallback_openai(tenant)

            return ChatOpenAI(
                model=row.model_id,
                temperature=tenant.model.temperature,
                api_key=api_key,
            )
    except Exception:
        return _fallback_openai(tenant)


def log_llm_usage(tenant: TenantConfig | None, model_ref: str, tokens_in: int, tokens_out: int) -> None:
    if not is_db_configured() or not tenant:
        return
    try:
        with SessionLocal() as db:
            row = _resolve_model_row(db, tenant)
            cost = estimate_cost(row, tokens_in, tokens_out)
            record_usage(
                db,
                tenant_id=tenant.id,
                model_ref=model_ref,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_estimate=cost,
            )
    except Exception:
        pass
