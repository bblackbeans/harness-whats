import os

from langchain_openai import ChatOpenAI

from tenants.config import TenantConfig


def get_llm(tenant: TenantConfig | None = None) -> ChatOpenAI | None:
    model = tenant.model if tenant else None
    api_key_env = model.api_key_env if model else "OPENAI_API_KEY"
    api_key = os.getenv(api_key_env) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    return ChatOpenAI(
        model=model.name if model else os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=model.temperature if model else 0.3,
        api_key=api_key,
    )
