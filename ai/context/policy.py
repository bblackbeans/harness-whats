import os

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm
from tenants import load_prompt
from tenants.config import TenantConfig

SUMMARIZE_AFTER = int(os.getenv("CONTEXT_SUMMARIZE_AFTER", "12"))
KEEP_RECENT = int(os.getenv("CONTEXT_KEEP_RECENT", "6"))

_DEFAULT_SUMMARIZE_PROMPT = (
    "Resuma a conversa mantendo fatos, pedidos e decisões relevantes. "
    "Descarte cumprimentos repetidos e ruído. Máximo 8 frases."
)


def _summarize_after(tenant: TenantConfig | None) -> int:
    return tenant.context.summarize_after if tenant else SUMMARIZE_AFTER


def _keep_recent(tenant: TenantConfig | None) -> int:
    return tenant.context.keep_recent if tenant else KEEP_RECENT


def should_summarize(messages: list[BaseMessage], tenant: TenantConfig | None = None) -> bool:
    return len(messages) >= _summarize_after(tenant)


def summarize_messages(
    messages: list[BaseMessage],
    existing_summary: str,
    tenant: TenantConfig | None = None,
) -> str:
    llm = get_llm(tenant)
    if not llm:
        return existing_summary or "Resumo indisponível."

    keep_recent = _keep_recent(tenant)
    transcript = "\n".join(
        f"{'user' if isinstance(m, HumanMessage) else 'assistant'}: {m.content}"
        for m in messages[:-keep_recent]
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                load_prompt(tenant, "summarize_system", _DEFAULT_SUMMARIZE_PROMPT)
                if tenant
                else _DEFAULT_SUMMARIZE_PROMPT,
            ),
            (
                "human",
                "Resumo anterior:\n{existing_summary}\n\nNovas mensagens:\n{transcript}",
            ),
        ]
    )
    chain = prompt | llm
    return str(
        chain.invoke(
            {"existing_summary": existing_summary or "nenhum", "transcript": transcript}
        ).content
    )


def trim_messages(
    messages: list[BaseMessage],
    tenant: TenantConfig | None = None,
) -> list[BaseMessage]:
    keep_recent = _keep_recent(tenant)
    if len(messages) <= keep_recent:
        return messages
    return messages[-keep_recent:]


def build_agent_context(
    *,
    inbound_text: str,
    contact_name: str,
    conversation_summary: str,
    semantic_facts: list[str],
    recent_messages: list[BaseMessage],
    tenant: TenantConfig | None = None,
) -> str:
    company = tenant.name if tenant else "empresa"
    facts_block = "\n".join(f"- {fact}" for fact in semantic_facts) or "- nenhum"
    recent_block = "\n".join(
        f"{'Cliente' if isinstance(m, HumanMessage) else 'Assistente'}: {m.content}"
        for m in recent_messages
    ) or "nenhuma"

    return (
        f"Empresa: {company}\n"
        f"Nome do contato: {contact_name or 'cliente'}\n"
        f"Resumo da conversa: {conversation_summary or 'início da conversa'}\n"
        f"Memória semântica do usuário:\n{facts_block}\n"
        f"Mensagens recentes:\n{recent_block}\n"
        f"Mensagem atual: {inbound_text}"
    )
