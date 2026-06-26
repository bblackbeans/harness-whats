import json
import os
from pathlib import Path

from tenants.config import ContextConfig, HandoffConfig, ModelConfig, RagConfig, RoutingConfig, TenantConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
TENANTS_DIR = Path(os.getenv("TENANTS_DIR", str(_REPO_ROOT / "tenants")))


def _read_prompt(path: Path, fallback: str) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return fallback


def load_prompt(tenant: TenantConfig, name: str, fallback: str) -> str:
    return _read_prompt(Path(tenant.prompt_path(name)), fallback)


def _parse_tenant_dir(tenant_dir: Path) -> TenantConfig | None:
    config_path = tenant_dir / "tenant.json"
    if not config_path.is_file():
        return None

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    model_raw = raw.get("model", {})
    routing_raw = raw.get("routing", {})
    context_raw = raw.get("context", {})
    rag_raw = raw.get("rag", {})
    handoff_raw = raw.get("handoff", {})

    tenant_id = str(raw.get("id") or tenant_dir.name).strip()
    if not tenant_id or tenant_id.startswith("_"):
        return None

    return TenantConfig(
        id=tenant_id,
        name=str(raw.get("name") or tenant_id),
        language=str(raw.get("language") or "pt-BR"),
        model=ModelConfig(
            name=str(model_raw.get("name") or "gpt-4o-mini"),
            temperature=float(model_raw.get("temperature", 0.3)),
            api_key_env=str(model_raw.get("api_key_env") or "OPENAI_API_KEY"),
        ),
        routing=RoutingConfig(
            chatwoot_account_ids=[
                int(value) for value in routing_raw.get("chatwoot_account_ids", [])
            ],
            chatwoot_inbox_ids=[int(value) for value in routing_raw.get("chatwoot_inbox_ids", [])],
        ),
        context=ContextConfig(
            summarize_after=int(context_raw.get("summarize_after", 12)),
            keep_recent=int(context_raw.get("keep_recent", 6)),
        ),
        rag=RagConfig(
            enabled=bool(rag_raw.get("enabled", os.getenv("RAG_ENABLED", "true").lower() in {"1", "true", "yes"})),
            top_k=int(rag_raw.get("top_k", os.getenv("RAG_TOP_K", "5"))),
            embedding_model=str(
                rag_raw.get("embedding_model", os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small"))
            ),
            chunk_size=int(rag_raw.get("chunk_size", os.getenv("RAG_CHUNK_SIZE", "500"))),
            chunk_overlap=int(rag_raw.get("chunk_overlap", os.getenv("RAG_CHUNK_OVERLAP", "50"))),
        ),
        handoff=HandoffConfig(
            enabled=bool(handoff_raw.get("enabled", True)),
            message=str(
                handoff_raw.get(
                    "message",
                    "Vou encaminhar você para um atendente humano. Aguarde um momento, por favor.",
                )
            ),
            keywords=[str(value) for value in handoff_raw.get("keywords", [])]
            or HandoffConfig().keywords,
            on_no_knowledge=bool(handoff_raw.get("on_no_knowledge", True)),
            private_note_enabled=bool(handoff_raw.get("private_note_enabled", True)),
            auto_resume_on_resolved=bool(handoff_raw.get("auto_resume_on_resolved", True)),
            resume_bot_on_resolve=bool(handoff_raw.get("resume_bot_on_resolve", True)),
        ),
        root_dir=str(tenant_dir),
    )


def load_all_tenants() -> dict[str, TenantConfig]:
    tenants: dict[str, TenantConfig] = {}
    if not TENANTS_DIR.is_dir():
        return tenants

    for entry in sorted(TENANTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_") and entry.name != "_default":
            continue
        tenant = _parse_tenant_dir(entry)
        if tenant:
            tenants[tenant.id] = tenant

    return tenants


def load_default_tenant() -> TenantConfig:
    default_dir = TENANTS_DIR / "_default"
    tenant = _parse_tenant_dir(default_dir)
    if tenant:
        return tenant

    return TenantConfig(
        id="default",
        name="Default",
        root_dir=str(default_dir),
    )
