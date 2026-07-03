from sqlalchemy.orm import Session

from harness_platform.crypto import encrypt_value, mask_secret
from harness_platform.models import LlmModel, LlmProvider, TenantAllowedModel


def list_providers(db: Session) -> list[LlmProvider]:
    return db.query(LlmProvider).order_by(LlmProvider.name).all()


def provider_api_key_preview(provider: LlmProvider) -> str:
    return mask_secret(provider.encrypted_api_key or "")


def create_provider(db: Session, *, name: str, provider_type: str, api_key: str) -> LlmProvider:
    provider = LlmProvider(
        name=name,
        provider_type=provider_type,
        encrypted_api_key=encrypt_value(api_key),
        active=True,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def list_models(db: Session, provider_id: int | None = None) -> list[LlmModel]:
    query = db.query(LlmModel)
    if provider_id is not None:
        query = query.filter(LlmModel.provider_id == provider_id)
    return query.order_by(LlmModel.display_name).all()


def create_model(
    db: Session,
    *,
    provider_id: int,
    model_id: str,
    display_name: str,
    cost_per_1m_input: float = 0.15,
    cost_per_1m_output: float = 0.60,
    temperature_default: float = 0.3,
) -> LlmModel:
    model = LlmModel(
        provider_id=provider_id,
        model_id=model_id,
        display_name=display_name,
        cost_per_1m_input=cost_per_1m_input,
        cost_per_1m_output=cost_per_1m_output,
        temperature_default=temperature_default,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def update_provider(
    db: Session,
    provider_id: int,
    *,
    name: str | None = None,
    api_key: str | None = None,
    active: bool | None = None,
) -> LlmProvider:
    provider = db.query(LlmProvider).filter(LlmProvider.id == provider_id).first()
    if not provider:
        raise LookupError("Provedor não encontrado")
    if name is not None:
        provider.name = name
    if api_key is not None and api_key.strip():
        provider.encrypted_api_key = encrypt_value(api_key.strip())
    if active is not None:
        provider.active = active
    db.commit()
    db.refresh(provider)
    return provider


def update_model(
    db: Session,
    model_id: int,
    *,
    provider_id: int | None = None,
    display_name: str | None = None,
    model_ref: str | None = None,
    cost_per_1m_input: float | None = None,
    cost_per_1m_output: float | None = None,
    temperature_default: float | None = None,
) -> LlmModel:
    model = db.query(LlmModel).filter(LlmModel.id == model_id).first()
    if not model:
        raise LookupError("Modelo não encontrado")
    if provider_id is not None:
        provider = db.query(LlmProvider).filter(LlmProvider.id == provider_id).first()
        if not provider:
            raise LookupError("Provedor não encontrado")
        model.provider_id = provider_id
    if display_name is not None:
        model.display_name = display_name
    if model_ref is not None:
        model.model_id = model_ref
    if cost_per_1m_input is not None:
        model.cost_per_1m_input = cost_per_1m_input
    if cost_per_1m_output is not None:
        model.cost_per_1m_output = cost_per_1m_output
    if temperature_default is not None:
        model.temperature_default = temperature_default
    db.commit()
    db.refresh(model)
    return model


def set_tenant_models(db: Session, tenant_id: str, model_ids: list[int], default_id: int | None) -> None:
    db.query(TenantAllowedModel).filter(TenantAllowedModel.tenant_id == tenant_id).delete()
    for mid in model_ids:
        db.add(
            TenantAllowedModel(
                tenant_id=tenant_id,
                model_id=mid,
                is_default=mid == default_id,
            )
        )
    db.commit()


def get_tenant_allowed_models(db: Session, tenant_id: str) -> list[dict]:
    rows = (
        db.query(TenantAllowedModel, LlmModel)
        .join(LlmModel, TenantAllowedModel.model_id == LlmModel.id)
        .filter(TenantAllowedModel.tenant_id == tenant_id)
        .all()
    )
    return [
        {
            "id": model.id,
            "model_id": model.model_id,
            "display_name": model.display_name,
            "is_default": allowed.is_default,
        }
        for allowed, model in rows
    ]


def seed_default_openai(db: Session) -> None:
    if db.query(LlmProvider).first():
        return
    import os

    api_key = os.getenv("OPENAI_API_KEY", "")
    provider = create_provider(db, name="OpenAI", provider_type="openai", api_key=api_key)
    defaults = [
        ("gpt-4o-mini", "GPT-4o Mini", 0.15, 0.60),
        ("gpt-4o", "GPT-4o", 2.50, 10.00),
        ("gpt-4.1-mini", "GPT-4.1 Mini", 0.40, 1.60),
        ("gpt-4.1", "GPT-4.1", 2.00, 8.00),
    ]
    for model_id, display_name, cin, cout in defaults:
        create_model(
            db,
            provider_id=provider.id,
            model_id=model_id,
            display_name=display_name,
            cost_per_1m_input=cin,
            cost_per_1m_output=cout,
        )
