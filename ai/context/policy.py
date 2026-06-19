import os

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm

SUMMARIZE_AFTER = int(os.getenv("CONTEXT_SUMMARIZE_AFTER", "12"))
KEEP_RECENT = int(os.getenv("CONTEXT_KEEP_RECENT", "6"))


def should_summarize(messages: list[BaseMessage]) -> bool:
    return len(messages) >= SUMMARIZE_AFTER


def summarize_messages(messages: list[BaseMessage], existing_summary: str) -> str:
    llm = get_llm()
    if not llm:
        return existing_summary or "Resumo indisponível."

    transcript = "\n".join(
        f"{'user' if isinstance(m, HumanMessage) else 'assistant'}: {m.content}"
        for m in messages[:-KEEP_RECENT]
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Resuma a conversa de WhatsApp mantendo fatos, pedidos e decisões relevantes. "
                "Descarte cumprimentos repetidos e ruído. Máximo 8 frases.",
            ),
            (
                "human",
                "Resumo anterior:\n{existing_summary}\n\nNovas mensagens:\n{transcript}",
            ),
        ]
    )
    chain = prompt | llm
    return str(chain.invoke({"existing_summary": existing_summary or "nenhum", "transcript": transcript}).content)


def trim_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    if len(messages) <= KEEP_RECENT:
        return messages
    return messages[-KEEP_RECENT:]


def build_agent_context(
    *,
    inbound_text: str,
    contact_name: str,
    conversation_summary: str,
    semantic_facts: list[str],
    recent_messages: list[BaseMessage],
) -> str:
    facts_block = "\n".join(f"- {fact}" for fact in semantic_facts) or "- nenhum"
    recent_block = "\n".join(
        f"{'Cliente' if isinstance(m, HumanMessage) else 'Assistente'}: {m.content}"
        for m in recent_messages
    ) or "nenhuma"

    return (
        f"Nome do contato: {contact_name or 'cliente'}\n"
        f"Resumo da conversa: {conversation_summary or 'início da conversa'}\n"
        f"Memória semântica do usuário:\n{facts_block}\n"
        f"Mensagens recentes:\n{recent_block}\n"
        f"Mensagem atual: {inbound_text}"
    )
