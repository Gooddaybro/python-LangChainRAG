"""LLM client factory for chat-model access."""

import os

from langchain_openai import ChatOpenAI

from clothing_assistant.config_data import CHAT_MODEL_NAME, CHAT_TEMPERATURE, KIMI_BASE_URL


def get_chat_model():
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        raise RuntimeError("MOONSHOT_API_KEY is required to generate Kimi chat responses.")

    return ChatOpenAI(
        model=CHAT_MODEL_NAME,
        temperature=CHAT_TEMPERATURE,
        api_key=api_key,
        base_url=KIMI_BASE_URL,
    )
