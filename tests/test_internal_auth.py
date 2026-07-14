import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from clothing_assistant.api.app import app


class InternalAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        self.environment = patch.dict(
            os.environ,
            {"APP_AI_PYTHON_INTERNAL_TOKEN": "python-test-token"},
            clear=False,
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    @patch("clothing_assistant.api.app.run_langgraph_agent")
    def test_chat_rejects_missing_internal_token_before_running_agent(self, run_agent):
        response = self.client.post("/chat", json=self._chat_payload())

        self.assertEqual(401, response.status_code)
        self.assertEqual("invalid_internal_token", response.json()["detail"]["code"])
        run_agent.assert_not_called()

    @patch("clothing_assistant.api.app.run_langgraph_agent")
    def test_stream_rejects_invalid_internal_token_before_running_agent(self, run_agent):
        response = self.client.post(
            "/chat/stream",
            headers={"X-Internal-Token": "wrong-token"},
            json=self._chat_payload(),
        )

        self.assertEqual(401, response.status_code)
        self.assertEqual("invalid_internal_token", response.json()["detail"]["code"])
        run_agent.assert_not_called()

    def test_business_endpoint_fails_closed_when_token_is_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post(
                "/chat",
                headers={"X-Internal-Token": "any-token"},
                json=self._chat_payload(),
            )

        self.assertEqual(503, response.status_code)
        self.assertEqual("internal_auth_not_configured", response.json()["detail"]["code"])

    def test_health_remains_available_without_internal_token(self):
        response = self.client.get("/health")

        self.assertEqual(200, response.status_code)

    def _chat_payload(self):
        return {
            "request_id": "req-internal-auth",
            "session_id": "session-internal-auth",
            "thread_id": "thread-internal-auth",
            "query": "hello",
            "chat_history": [],
            "user_context": {"user_id": 10},
            "candidates": [],
            "debug": False,
        }


if __name__ == "__main__":
    unittest.main()
