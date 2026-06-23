import logging
from pathlib import Path

from knowledge.chunking import split_text
from knowledge.embeddings import embed_texts
from knowledge.store import (
    _file_hash,
    _relative_source,
    delete_source,
    discover_knowledge_files,
    get_indexed_sources,
    save_chunks,
)
from tenants.config import TenantConfig

logger = logging.getLogger(__name__)


def sync_tenant_index(tenant: TenantConfig) -> dict:
    if not tenant.rag.enabled:
        return {"indexed": 0, "skipped": 0, "errors": 0}

    knowledge_dir = Path(tenant.knowledge_dir())
    files = discover_knowledge_files(knowledge_dir)
    indexed_sources = get_indexed_sources(tenant.id)
    current_sources = set()
    stats = {"indexed": 0, "skipped": 0, "errors": 0, "files": []}

    for file_path in files:
        source_path = _relative_source(knowledge_dir, file_path)
        current_sources.add(source_path)
        try:
            content = file_path.read_text(encoding="utf-8").strip()
            content_hash = _file_hash(content)
            if indexed_sources.get(source_path) == content_hash:
                stats["skipped"] += 1
                continue

            chunks_text = split_text(
                content,
                chunk_size=tenant.rag.chunk_size,
                overlap=tenant.rag.chunk_overlap,
            )
            if not chunks_text:
                stats["skipped"] += 1
                continue

            vectors = embed_texts(tenant, chunks_text)
            if vectors is None:
                logger.warning("RAG: embeddings indisponíveis para tenant %s", tenant.id)
                stats["errors"] += 1
                continue

            chunk_rows = [
                (index, text, vector)
                for index, (text, vector) in enumerate(zip(chunks_text, vectors, strict=True))
            ]
            save_chunks(tenant.id, source_path, content_hash, chunk_rows)
            stats["indexed"] += len(chunk_rows)
            stats["files"].append(source_path)
            logger.info(
                "RAG indexado tenant=%s source=%s chunks=%s",
                tenant.id,
                source_path,
                len(chunk_rows),
            )
        except Exception:
            logger.exception("RAG: falha ao indexar %s", file_path)
            stats["errors"] += 1

    for stale_source in set(indexed_sources) - current_sources:
        delete_source(tenant.id, stale_source)
        logger.info("RAG removido tenant=%s source=%s", tenant.id, stale_source)

    return stats
