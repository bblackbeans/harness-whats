from knowledge.embeddings import embed_query
from knowledge.indexer import sync_tenant_index
from knowledge.store import cosine_similarity, is_rag_enabled, load_all_chunks
from tenants.config import TenantConfig


def retrieve_knowledge_chunks(
    tenant: TenantConfig,
    query: str,
    *,
    sync_index: bool = True,
) -> list[dict[str, str]]:
    if not is_rag_enabled() or not tenant.rag.enabled or not query.strip():
        return []

    if sync_index:
        sync_tenant_index(tenant)

    query_vector = embed_query(tenant, query)
    if not query_vector:
        return []

    scored: list[tuple[float, str, str]] = []
    for source_path, text, embedding in load_all_chunks(tenant.id):
        score = cosine_similarity(query_vector, embedding)
        scored.append((score, source_path, text))

    scored.sort(key=lambda item: item[0], reverse=True)

    seen_text: set[str] = set()
    results: list[dict[str, str]] = []
    for _score, source_path, text in scored:
        normalized = text.strip()
        if normalized in seen_text:
            continue
        seen_text.add(normalized)
        results.append({"source": source_path, "text": normalized})
        if len(results) >= tenant.rag.top_k:
            break

    return results


def format_knowledge_block(chunks: list[dict[str, str]]) -> str:
    if not chunks:
        return "Material oficial recuperado: nenhum material indexado."

    lines = ["Material oficial recuperado:"]
    for index, chunk in enumerate(chunks, start=1):
        lines.append(f'{index}. [fonte: {chunk["source"]}] {chunk["text"]}')
    return "\n".join(lines)
