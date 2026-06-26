import json
import os

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm
from context.policy import build_agent_context
from harness.state import HarnessState
from knowledge.retrieve import format_knowledge_block, retrieve_knowledge_chunks
from handoff.policy import resolve_handoff
from memory.semantic import recall, store
from tenants import get_tenant, load_prompt

_DEFAULT_AGENT_PROMPT = (
    "Você é um assistente virtual de atendimento por mensagem. "
    "Responda apenas JSON com: intent, should_reply, reply, new_facts."
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
    system_prompt = load_prompt(tenant, "agent_system", _DEFAULT_AGENT_PROMPT)
    agent_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{context}"),
        ]
    )

    if not llm:
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
            "outbound_text": f"Recebi sua mensagem: {text}",
            "handoff_to_human": handoff,
            "handoff_reason": reason,
            "new_semantic_facts": [],
        }

    chain = agent_prompt | llm | JsonOutputParser()
    try:
        result = chain.invoke({"context": state.get("agent_context", text)})
    except Exception:
        result = {
            "intent": "other",
            "should_reply": True,
            "reply": f"Recebi sua mensagem: {text}",
            "handoff_to_human": False,
            "new_facts": [],
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
