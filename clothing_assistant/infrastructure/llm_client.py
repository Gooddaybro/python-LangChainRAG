"""LLM client factory for chat-model access."""

from langchain_community.chat_models.tongyi import ChatTongyi

from clothing_assistant.config_data import CHAT_MODEL_NAME, CHAT_TEMPERATURE


def get_chat_model():
    return ChatTongyi(
        model=CHAT_MODEL_NAME,
        temperature=CHAT_TEMPERATURE,
    )
