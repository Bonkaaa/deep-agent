from typing import List

from langchain_ollama import ChatOllama


def get_llm(
    model_name: str,
    temperature: float = 0.2,
) -> ChatOllama:
    return ChatOllama(
        model=model_name,
        temperature=temperature,
        validate_model_on_init=True,
    )
