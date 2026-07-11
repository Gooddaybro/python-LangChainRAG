import os
import unittest
from unittest.mock import patch

from clothing_assistant.config_data import CHAT_MODEL_NAME, CHAT_TEMPERATURE, KIMI_BASE_URL
from clothing_assistant.infrastructure import llm_client


class KimiChatClientTests(unittest.TestCase):
    def test_kimi_client_uses_moonshot_openai_compatibility(self):
        chat_client_type = getattr(llm_client, "ChatOpenAI", None)
        self.assertIsNotNone(chat_client_type)

        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "test-moonshot-key"}, clear=True), patch(
            "clothing_assistant.infrastructure.llm_client.ChatOpenAI"
        ) as chat_client:
            llm_client.get_chat_model()

        chat_client.assert_called_once_with(
            model=CHAT_MODEL_NAME,
            temperature=CHAT_TEMPERATURE,
            api_key="test-moonshot-key",
            base_url=KIMI_BASE_URL,
        )

    def test_kimi_client_requires_moonshot_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MOONSHOT_API_KEY"):
                llm_client.get_chat_model()


if __name__ == "__main__":
    unittest.main()
