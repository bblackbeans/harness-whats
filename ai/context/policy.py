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
    contact_profile: dict | None = None,
    custom_fields: list[dict] | None = None,
    http_tools_block: str = "",
    files_block: str = "",
    flow_block: str = "",
) -> str:
    company = tenant.name if tenant else "empresa"
    facts_block = "\n".join(f"- {fact}" for fact in semantic_facts) or "- nenhum"
    recent_block = "\n".join(
        f"{'Cliente' if isinstance(m, HumanMessage) else 'Assistente'}: {m.content}"
        for m in recent_messages
    ) or "nenhuma"

    profile = contact_profile or {}
    fields = profile.get("fields") or {}
    profile_lines = [
        f"- telefone: {profile.get('phone') or 'desconhecido'}",
        f"- nome: {profile.get('name') or contact_name or 'desconhecido'}",
        f"- email: {profile.get('email') or 'desconhecido'}",
    ]
    for key, value in fields.items():
        profile_lines.append(f"- {key}: {value}")
    profile_block = "\n".join(profile_lines)

    known_keys = {"nome", "email", "telefone", "phone", "name", *(fields.keys() if isinstance(fields, dict) else [])}
    missing = []
    for cf in custom_fields or []:
        key = cf.get("key")
        if key and key not in fields and key not in known_keys:
            missing.append(f"{cf.get('label') or key} ({key})")
    missing_block = ", ".join(missing) if missing else "nenhum campo obrigatório pendente listado"

    extras = ""
    if flow_block:
        extras += f"\n{flow_block}\n"
    if http_tools_block:
        extras += f"\n{http_tools_block}\n"
    if files_block:
        extras += f"\n{files_block}\n"

    return (
        f"Empresa: {company}\n"
        f"Nome do contato: {contact_name or profile.get('name') or 'cliente'}\n"
        f"Perfil persistente do contato:\n{profile_block}\n"
        f"Campos ainda não preenchidos (pergunte só se necessário):\n{missing_block}\n"
        f"Resumo da conversa: {conversation_summary or 'início da conversa'}\n"
        f"Memória semântica do usuário:\n{facts_block}\n"
        f"Mensagens recentes:\n{recent_block}\n"
        f"{extras}"
        f"Mensagem atual: {inbound_text}"
    )


def format_flow_context_block(
    *,
    roteiro: dict | None,
    checklist: list | None,
    checklist_state: dict | None,
    base_prompt: str = "",
) -> str:
    if not roteiro and not checklist:
        return ""
    roteiro = roteiro or {}
    state = checklist_state or {}
    lines = [
        "=== ROTEIRO OPERACIONAL (OBRIGATÓRIO) ===",
        "Isto NÃO é um fluxo rígido de botões. É um roteiro que você DEVE cumprir.",
        "Você pode escrever de forma natural e adaptar a linguagem,",
        "mas NÃO pode pular etapas obrigatórias, esquecer de salvar campos,",
        "deixar de executar tools/APIs obrigatórias ou transferir sem necessidade do roteiro.",
    ]
    if base_prompt:
        lines.append(f"Instruções do Flow: {base_prompt}")
    if roteiro.get("objetivo"):
        lines.append(f"Objetivo: {roteiro['objetivo']}")
    etapas = roteiro.get("etapas") or []
    if etapas:
        lines.append("Etapas:")
        for e in etapas:
            if not isinstance(e, dict):
                continue
            sid = e.get("id") or ""
            st = state.get(sid, "pending")
            mark = {"completed": "✓", "skipped": "–", "pending": "□"}.get(st, "□")
            obr = "obrigatória" if e.get("obrigatoria", True) else "opcional"
            campos = ", ".join(e.get("campos") or []) or "—"
            lines.append(f"  {mark} [{sid}] {e.get('titulo') or sid} ({obr}; campos: {campos}; status={st})")
            if e.get("validacao"):
                lines.append(f"      validação: {e['validacao']}")
            tools = e.get("tools") or []
            if tools:
                lines.append(f"      tools: {tools}")
    if checklist:
        lines.append("Checklist atual:")
        for item in checklist:
            if isinstance(item, dict):
                sid = str(item.get("id") or "")
                titulo = item.get("titulo") or sid
            else:
                sid = str(item)
                titulo = sid
            st = state.get(sid, "pending")
            mark = {"completed": "✓", "skipped": "–", "pending": "□"}.get(st, "□")
            lines.append(f"  {mark} {titulo} ({sid}) = {st}")
    if roteiro.get("handoff_quando"):
        lines.append(f"Transferir humano quando: {roteiro['handoff_quando']}")
    if roteiro.get("encerramento"):
        lines.append(f"Encerramento: {roteiro['encerramento']}")
    lines.append("=== FIM DO ROTEIRO ===")
    return "\n".join(lines)
