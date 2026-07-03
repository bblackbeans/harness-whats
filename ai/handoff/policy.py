from tenants.config import TenantConfig

# Handoff por FAQ vazio só para assuntos comerciais sensíveis — não para qualquer pergunta.
_COMMERCIAL_SIGNALS = (
    "quanto",
    "preço",
    "preco",
    "valor",
    "custa",
    "prazo",
    "orçamento",
    "orcamento",
    "contrato",
    "proposta",
    "cotação",
    "cotacao",
    "plano ",
)

# Perguntas que o bot deve responder sem FAQ e sem handoff.
_GENERAL_REPLY_SIGNALS = (
    "que dia",
    "qual dia",
    "que data",
    "qual data",
    "que horas",
    "qual hora",
    "que hora",
    "bom dia",
    "boa tarde",
    "boa noite",
    "tudo bem",
    "como vai",
    "quem é você",
    "quem e voce",
    "o que você é",
    "o que voce e",
)


def _normalize(text: str) -> str:
    return text.lower().strip()


def matches_handoff_keywords(text: str, tenant: TenantConfig) -> bool:
    if not tenant.handoff.enabled:
        return False
    normalized = _normalize(text)
    return any(keyword.lower() in normalized for keyword in tenant.handoff.keywords)


def is_general_assistant_question(text: str) -> bool:
    normalized = _normalize(text)
    return any(signal in normalized for signal in _GENERAL_REPLY_SIGNALS)


# Perguntas informativas da empresa — não são comerciais.
_INFORMATIONAL_SIGNALS = (
    "contato",
    "e-mail",
    "email",
    "telefone",
    "whatsapp",
    "site",
    "endereço",
    "endereco",
    "falar com",
)


def is_informational_question(text: str) -> bool:
    normalized = _normalize(text)
    return any(signal in normalized for signal in _INFORMATIONAL_SIGNALS)


def is_commercial_question(text: str) -> bool:
    normalized = _normalize(text)
    return any(signal in normalized for signal in _COMMERCIAL_SIGNALS)


def should_handoff_no_knowledge(
    *,
    inbound_text: str,
    retrieved_knowledge: list[str],
    tenant: TenantConfig,
) -> bool:
    if not tenant.handoff.enabled or not tenant.handoff.on_no_knowledge:
        return False

    normalized = _normalize(inbound_text)
    if is_general_assistant_question(normalized):
        return False

    if not is_commercial_question(normalized):
        return False

    if retrieved_knowledge:
        return False

    return True


def resolve_handoff(
    *,
    inbound_text: str,
    retrieved_knowledge: list[str],
    tenant: TenantConfig,
    llm_handoff: bool,
    bot_reply: str = "",
) -> tuple[bool, str]:
    if not tenant.handoff.enabled:
        return False, ""

    if matches_handoff_keywords(inbound_text, tenant):
        return True, "keyword"

    if is_general_assistant_question(inbound_text) or is_informational_question(inbound_text):
        return False, ""

    if llm_handoff and is_commercial_question(inbound_text):
        return True, "agent"

    if should_handoff_no_knowledge(
        inbound_text=inbound_text,
        retrieved_knowledge=retrieved_knowledge,
        tenant=tenant,
    ):
        # Se o bot já respondeu com conteúdo, não faz handoff no mesmo turno.
        if bot_reply.strip():
            return False, ""
        return True, "no_knowledge"

    return False, ""
