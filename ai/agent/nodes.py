import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm
from context.policy import build_agent_context
from harness.state import HarnessState
from memory.semantic import recall, store

AGENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Você é o componente de raciocínio de um harness WhatsApp. "
            "Use o contexto fornecido para classificar e responder. "
            "Responda apenas JSON com: "
            "intent (greeting|question|support|sales|other), "
            "should_reply (boolean), "
            "reply (string curta em português ou null), "
            "new_facts (array de fatos duráveis sobre o usuário, ou []).",
        ),
        ("human", "{context}"),
    ]
)

FACTS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Extraia fatos duráveis sobre o usuário a partir da interação. "
            "Retorne JSON: {\"facts\": [\"...\"]}",
        ),
        ("human", "Mensagem: {text}\nResposta: {reply}"),
    ]
)


def load_semantic_memory(state: HarnessState) -> HarnessState:
    facts = recall(state["phone"])
    return {**state, "semantic_facts": facts}


def ingest_message(state: HarnessState) -> HarnessState:
    return {
        **state,
        "messages": [HumanMessage(content=state["inbound_text"])],
    }


def manage_context(state: HarnessState) -> HarnessState:
    from context.policy import should_summarize, summarize_messages, trim_messages

    messages = state.get("messages", [])
    summary = state.get("conversation_summary", "")

    if should_summarize(messages):
        summary = summarize_messages(messages, summary)
        messages = trim_messages(messages)

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
        ),
    }


def run_agent(state: HarnessState) -> HarnessState:
    llm = get_llm()
    text = state["inbound_text"]

    if not llm:
        return {
            **state,
            "intent": "other",
            "should_reply": True,
            "outbound_text": f"Recebi sua mensagem: {text}",
            "new_semantic_facts": [],
        }

    chain = AGENT_PROMPT | llm | JsonOutputParser()
    try:
        result = chain.invoke({"context": state.get("agent_context", text)})
    except Exception:
        result = {
            "intent": "other",
            "should_reply": True,
            "reply": f"Recebi sua mensagem: {text}",
            "new_facts": [],
        }

    return {
        **state,
        "intent": str(result.get("intent", "other")),
        "should_reply": bool(result.get("should_reply", True)),
        "outbound_text": str(result.get("reply") or ""),
        "new_semantic_facts": [str(f) for f in result.get("new_facts", []) if f],
    }


def persist_semantic_memory(state: HarnessState) -> HarnessState:
    facts = state.get("new_semantic_facts", [])
    if not facts and state.get("outbound_text"):
        llm = get_llm()
        if llm:
            chain = FACTS_PROMPT | llm | JsonOutputParser()
            try:
                extracted = chain.invoke(
                    {"text": state["inbound_text"], "reply": state["outbound_text"]}
                )
                facts = [str(f) for f in extracted.get("facts", []) if f]
            except Exception:
                facts = []

    if facts:
        store(state["phone"], facts)
        merged = list(dict.fromkeys(state.get("semantic_facts", []) + facts))
        return {**state, "semantic_facts": merged, "new_semantic_facts": facts}

    return state


def generate_dispatch_message(template: str, variables: dict) -> str:
    llm = get_llm()
    if not llm:
        message = template
        for key, value in variables.items():
            message = message.replace(f"{{{key}}}", str(value))
        return message

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Personalize a mensagem de disparo WhatsApp usando o template e variáveis. "
                "Mantenha tom natural, curto, sem markdown.",
            ),
            ("human", "Template:\n{template}\n\nVariáveis:\n{variables}"),
        ]
    )
    chain = prompt | llm
    return str(
        chain.invoke(
            {"template": template, "variables": json.dumps(variables, ensure_ascii=False)}
        ).content
    )
