import json
import logging
import os

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm, log_llm_usage
from context.policy import build_agent_context
from harness.state import HarnessState
from knowledge.retrieve import format_knowledge_block, retrieve_knowledge_chunks
from handoff.policy import resolve_handoff
from memory.semantic import recall, store
from tenants import get_tenant, load_prompt

logger = logging.getLogger(__name__)

_DEFAULT_AGENT_PROMPT = (
    "Você é um assistente virtual de atendimento por mensagem. "
    "Responda em português do Brasil de forma natural e útil."
)
_AGENT_JSON_INSTRUCTIONS = (
    "\n\n---\n"
    "Formato de saída obrigatório: responda APENAS com JSON válido (sem markdown), "
    'com as chaves "intent" (string), "should_reply" (boolean), '
    '"reply" (string — mensagem enviada ao cliente), '
    '"new_facts" (array de strings), "handoff_to_human" (boolean, opcional).'
)
_DEFAULT_FACTS_PROMPT = (
    'Extraia fatos duráveis sobre o usuário. Retorne JSON: {"facts": ["..."]}'
)
_DEFAULT_DISPATCH_PROMPT = (
    "Personalize a mensagem de disparo usando o template e variáveis. "
    "Mantenha tom natural, curto, sem markdown."
)


def _tenant_from_state(state: HarnessState):
    return get_tenant(state.get("tenant_id", "default"))


def load_semantic_memory(state: HarnessState) -> HarnessState:
    tenant = _tenant_from_state(state)
    facts = recall(tenant.id, state["phone"])
    return {**state, "semantic_facts": facts}


def ingest_message(state: HarnessState) -> HarnessState:
    return {
        **state,
        "messages": [HumanMessage(content=state["inbound_text"])],
    }


def manage_context(state: HarnessState) -> HarnessState:
    from context.policy import should_summarize, summarize_messages, trim_messages

    tenant = _tenant_from_state(state)
    messages = state.get("messages", [])
    summary = state.get("conversation_summary", "")

    if should_summarize(messages, tenant):
        summary = summarize_messages(messages, summary, tenant)
        messages = trim_messages(messages, tenant)

    return {
        **state,
        "messages": messages,
        "conversation_summary": summary,
        "agent_context": build_agent_context(
            inbound_text=state["inbound_text"],
            contact_name=state.get("contact_name", ""),
            conversation_summary=summary,
            semantic_facts=state.get("semantic_facts", []),
            recent_messages=messages,
            tenant=tenant,
        ),
    }


def retrieve_knowledge(state: HarnessState) -> HarnessState:
    tenant = _tenant_from_state(state)
    chunks = retrieve_knowledge_chunks(tenant, state["inbound_text"])
    knowledge_block = format_knowledge_block(chunks)
    base_context = state.get("agent_context", "")
    agent_context = f"{base_context}\n\n{knowledge_block}" if base_context else knowledge_block

    return {
        **state,
        "retrieved_knowledge": [chunk["text"] for chunk in chunks],
        "agent_context": agent_context,
    }


def run_agent(state: HarnessState) -> HarnessState:
    tenant = _tenant_from_state(state)
    llm = get_llm(tenant)
    text = state["inbound_text"]
    persona_prompt = load_prompt(tenant, "agent_system", _DEFAULT_AGENT_PROMPT)
    system_prompt = persona_prompt + _AGENT_JSON_INSTRUCTIONS
    agent_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{context}"),
        ]
    )

    if not llm:
        logger.error("LLM indisponível para tenant=%s", tenant.id)
        handoff, reason = resolve_handoff(
            inbound_text=text,
            retrieved_knowledge=state.get("retrieved_knowledge", []),
            tenant=tenant,
            llm_handoff=False,
        )
        return {
            **state,
            "intent": "other",
            "should_reply": True,
            "outbound_text": (
                "No momento não consigo processar com IA. "
                "Verifique o provedor LLM no painel ou OPENAI_API_KEY no servidor."
            ),
            "handoff_to_human": handoff,
            "handoff_reason": reason or "llm_unavailable",
            "new_semantic_facts": [],
        }

    chain = agent_prompt | llm | JsonOutputParser()
    context_text = state.get("agent_context", text)
    model_ref = tenant.model.name
    try:
        result = chain.invoke({"context": context_text})
        reply_text = str(result.get("reply") or "")
        log_llm_usage(
            tenant,
            model_ref,
            max(1, len(context_text) // 4),
            max(1, len(reply_text) // 4),
        )
    except Exception as error:
        logger.warning(
            "Falha ao parsear JSON do agente tenant=%s: %s",
            tenant.id,
            error,
        )
        try:
            raw = (agent_prompt | llm).invoke({"context": context_text})
            content = str(getattr(raw, "content", raw)).strip()
            result = {
                "intent": "other",
                "should_reply": bool(content),
                "reply": content,
                "handoff_to_human": False,
                "new_facts": [],
            }
            if content:
                log_llm_usage(
                    tenant,
                    model_ref,
                    max(1, len(context_text) // 4),
                    max(1, len(content) // 4),
                )
        except Exception as inner:
            logger.exception("Falha na chamada LLM tenant=%s", tenant.id)
            result = {
                "intent": "other",
                "should_reply": True,
                "reply": "Desculpe, tive um problema ao processar sua mensagem. Pode tentar de novo?",
                "handoff_to_human": False,
                "new_facts": [],
                "handoff_reason": str(inner),
            }

    llm_handoff = bool(result.get("handoff_to_human", False))
    reply = str(result.get("reply") or "")
    handoff, reason = resolve_handoff(
        inbound_text=text,
        retrieved_knowledge=state.get("retrieved_knowledge", []),
        tenant=tenant,
        llm_handoff=llm_handoff,
        bot_reply=reply,
    )

    if handoff:
        return {
            **state,
            "intent": str(result.get("intent", "other")),
            "should_reply": False,
            "outbound_text": "",
            "handoff_to_human": True,
            "handoff_reason": reason,
            "new_semantic_facts": [str(f) for f in result.get("new_facts", []) if f],
        }

    return {
        **state,
        "intent": str(result.get("intent", "other")),
        "should_reply": bool(result.get("should_reply", True)),
        "outbound_text": str(result.get("reply") or ""),
        "handoff_to_human": handoff,
        "handoff_reason": reason,
        "new_semantic_facts": [str(f) for f in result.get("new_facts", []) if f],
    }


def persist_semantic_memory(state: HarnessState) -> HarnessState:
    tenant = _tenant_from_state(state)
    facts = state.get("new_semantic_facts", [])
    if not facts and state.get("outbound_text"):
        llm = get_llm(tenant)
        if llm:
            facts_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", load_prompt(tenant, "facts_system", _DEFAULT_FACTS_PROMPT)),
                    ("human", "Mensagem: {text}\nResposta: {reply}"),
                ]
            )
            chain = facts_prompt | llm | JsonOutputParser()
            try:
                extracted = chain.invoke(
                    {"text": state["inbound_text"], "reply": state["outbound_text"]}
                )
                facts = [str(f) for f in extracted.get("facts", []) if f]
            except Exception:
                facts = []

    if facts:
        store(tenant.id, state["phone"], facts)
        merged = list(dict.fromkeys(state.get("semantic_facts", []) + facts))
        return {**state, "semantic_facts": merged, "new_semantic_facts": facts}

    return state


def generate_dispatch_message(
    template: str,
    variables: dict,
    tenant_id: str | None = None,
) -> str:
    tenant = get_tenant(tenant_id or os.getenv("TENANT_ID", "default"))
    llm = get_llm(tenant)
    if not llm:
        message = template
        for key, value in variables.items():
            message = message.replace(f"{{{key}}}", str(value))
        return message

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt(tenant, "dispatch_system", _DEFAULT_DISPATCH_PROMPT)),
            ("human", "Template:\n{template}\n\nVariáveis:\n{variables}"),
        ]
    )
    chain = prompt | llm
    return str(
        chain.invoke(
            {"template": template, "variables": json.dumps(variables, ensure_ascii=False)}
        ).content
    )
