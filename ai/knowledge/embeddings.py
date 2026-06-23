import os

from langchain_openai import OpenAIEmbeddings

from tenants.config import TenantConfig


def get_embeddings(tenant: TenantConfig | None = None) -> OpenAIEmbeddings | None:
    rag = tenant.rag if tenant else None
    api_key_env = tenant.model.api_key_env if tenant else "OPENAI_API_KEY"
    api_key = os.getenv(api_key_env) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = (
        rag.embedding_model
        if rag
        else os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    return OpenAIEmbeddings(model=model, api_key=api_key)


def embed_texts(tenant: TenantConfig | None, texts: list[str]) -> list[list[float]] | None:
    if not texts:
        return []
    embeddings = get_embeddings(tenant)
    if not embeddings:
        return None
    return embeddings.embed_documents(texts)


def embed_query(tenant: TenantConfig | None, text: str) -> list[float] | None:
    embeddings = get_embeddings(tenant)
    if not embeddings:
        return None
    return embeddings.embed_query(text)
