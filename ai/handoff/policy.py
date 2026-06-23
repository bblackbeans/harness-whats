from tenants.config import TenantConfig


def _normalize(text: str) -> str:
    return text.lower().strip()


def matches_handoff_keywords(text: str, tenant: TenantConfig) -> bool:
    if not tenant.handoff.enabled:
        return False
    normalized = _normalize(text)
    return any(keyword.lower() in normalized for keyword in tenant.handoff.keywords)


def should_handoff_no_knowledge(
    *,
    inbound_text: str,
    retrieved_knowledge: list[str],
    tenant: TenantConfig,
) -> bool:
    if not tenant.handoff.enabled or not tenant.handoff.on_no_knowledge:
        return False
    if retrieved_knowledge:
        return False

    normalized = _normalize(inbound_text)
    question_signals = ("?", "quanto", "preço", "preco", "valor", "custa", "prazo", "orçamento", "orcamento")
    return any(signal in normalized for signal in question_signals)


def resolve_handoff(
    *,
    inbound_text: str,
    retrieved_knowledge: list[str],
    tenant: TenantConfig,
    llm_handoff: bool,
) -> tuple[bool, str]:
    if not tenant.handoff.enabled:
        return False, ""

    if matches_handoff_keywords(inbound_text, tenant):
        return True, "keyword"

    if llm_handoff:
        return True, "agent"

    if should_handoff_no_knowledge(
        inbound_text=inbound_text,
        retrieved_knowledge=retrieved_knowledge,
        tenant=tenant,
    ):
        return True, "no_knowledge"

    return False, ""
