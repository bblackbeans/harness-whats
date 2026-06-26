from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelConfig:
    name: str = "gpt-4o-mini"
    temperature: float = 0.3
    api_key_env: str = "OPENAI_API_KEY"


@dataclass(frozen=True)
class RoutingConfig:
    chatwoot_account_ids: list[int] = field(default_factory=list)
    chatwoot_inbox_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ContextConfig:
    summarize_after: int = 12
    keep_recent: int = 6


@dataclass(frozen=True)
class RagConfig:
    enabled: bool = True
    top_k: int = 5
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 500
    chunk_overlap: int = 50


@dataclass(frozen=True)
class HandoffConfig:
    enabled: bool = True
    message: str = (
        "Vou encaminhar você para um atendente humano. "
        "Aguarde um momento, por favor."
    )
    keywords: list[str] = field(
        default_factory=lambda: [
            "atendente",
            "humano",
            "pessoa",
            "falar com alguém",
            "falar com alguem",
        ]
    )
    on_no_knowledge: bool = True
    private_note_enabled: bool = True
    auto_resume_on_resolved: bool = True


@dataclass(frozen=True)
class TenantConfig:
    id: str
    name: str
    language: str = "pt-BR"
    model: ModelConfig = field(default_factory=ModelConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    rag: RagConfig = field(default_factory=RagConfig)
    handoff: HandoffConfig = field(default_factory=HandoffConfig)
    root_dir: str = ""

    def prompt_path(self, name: str) -> str:
        return f"{self.root_dir}/prompts/{name}.txt"

    def knowledge_dir(self) -> str:
        return f"{self.root_dir}/knowledge"
