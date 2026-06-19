import os

from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.3, api_key=api_key)
