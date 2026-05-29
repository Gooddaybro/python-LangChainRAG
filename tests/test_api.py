import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from clothing_assistant.api.app import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_health_returns_ok(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    # /chat 现在走 LangGraph 主工作流
    def test_chat_uses_java_contract_and_calls_langgraph_executor(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {
                "intent_result": {"intent": "chat"},
                "stop_reason": "final_answer",
            },
        }

        with patch(
            "clothing_assistant.api.app.run_langgraph_agent",
            return_value=fake_result,
        ) as mock_run:
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-api-1",
                    "session_id": "session-api-1",
                    "query": "我 175cm 70kg 穿什么码？",
                    "chat_history": [],
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "request_id": "req-api-1",
                "answer": "fake answer",
                "intent": "chat",
                "product_refs": [],
                "suggested_actions": [],
                "debug": fake_result["debug"],
            },
        )
        mock_run.assert_called_once_with(
            "我 175cm 70kg 穿什么码？",
            chat_history=[],
            thread_id="session-api-1",
            request_id="req-api-1",
            session_id="session-api-1",
            user_context={},
            candidates=[],
        )

    def test_chat_passes_thread_id_to_langgraph_executor(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {
                "thread_id": "api-thread-1",
                "intent_result": {"intent": "chat"},
            },
        }

        with patch(
            "clothing_assistant.api.app.run_langgraph_agent",
            return_value=fake_result,
        ) as mock_run:
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-api-2",
                    "session_id": "session-api-2",
                    "query": "你是谁？",
                    "chat_history": [],
                    "thread_id": "api-thread-1",
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["debug"], fake_result["debug"])
        mock_run.assert_called_once_with(
            "你是谁？",
            chat_history=[],
            thread_id="api-thread-1",
            request_id="req-api-2",
            session_id="session-api-2",
            user_context={},
            candidates=[],
        )

    def test_chat_hides_debug_when_disabled(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {
                "intent_result": {"intent": "product_qa"},
                "stop_reason": "final_answer",
            },
        }

        with patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-api-3",
                    "session_id": "session-api-3",
                    "query": "这件衣服适合夏天吗？",
                    "debug": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "request_id": "req-api-3",
                "answer": "fake answer",
                "intent": "product_qa",
                "product_refs": [],
                "suggested_actions": [],
            },
        )

    def test_chat_missing_info_adds_follow_up_action(self):
        fake_result = {
            "answer": "想查哪件商品？请补充商品名或 SKU，我再帮你查库存或价格。",
            "debug": {
                "intent_result": {"intent": "inventory_check"},
                "stop_reason": "missing_info",
            },
        }

        with patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-api-4",
                    "session_id": "session-api-4",
                    "query": "黑色M码有货吗？",
                    "debug": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggested_actions"], [{"type": "ask_follow_up"}])

    def test_chat_rejects_missing_request_id(self):
        response = self.client.post(
            "/chat",
            json={"session_id": "session-api-5", "query": "你是谁？"},
        )

        self.assertEqual(response.status_code, 422)

    def test_chat_rejects_missing_session_id(self):
        response = self.client.post(
            "/chat",
            json={"request_id": "req-api-6", "query": "你是谁？"},
        )

        self.assertEqual(response.status_code, 422)

    def test_chat_error_response_hides_internal_exception_detail(self):
        with (
            patch(
                "clothing_assistant.api.app.run_langgraph_agent",
                side_effect=RuntimeError("secret internal detail"),
            ),
            patch("clothing_assistant.api.app.logger.exception") as mock_log_exception,
        ):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-api-error",
                    "session_id": "session-api-error",
                    "query": "你是谁？",
                },
            )

        mock_log_exception.assert_called_once()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "error": "internal_server_error",
                "request_id": "req-api-error",
                "message": "AI service failed to process the request.",
            },
        )
        self.assertNotIn("secret internal detail", response.text)

    # /chat/pipeline 走旧手写 pipeline
    def test_pipeline_calls_pipeline_executor(self):
        fake_result = {
            "answer": "pipeline answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with patch(
            "clothing_assistant.api.app.run_agent",
            return_value=fake_result,
        ) as mock_run:
            response = self.client.post(
                "/chat/pipeline",
                json={
                    "query": "我 175cm 70kg 穿什么码？",
                    "chat_history": [],
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fake_result)
        mock_run.assert_called_once_with("我 175cm 70kg 穿什么码？", chat_history=[])

    # /chat/langgraph 保留旧路径，仍然可用
    def test_langgraph_endpoint_still_works(self):
        fake_result = {
            "answer": "shadow answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with patch(
            "clothing_assistant.api.app.run_langgraph_agent",
            return_value=fake_result,
        ) as mock_run:
            response = self.client.post(
                "/chat/langgraph",
                json={
                    "query": "这件衣服适合夏天吗？",
                    "chat_history": [],
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fake_result)
        mock_run.assert_called_once_with("这件衣服适合夏天吗？", chat_history=[], thread_id=None)

    def test_chat_rejects_blank_query(self):
        response = self.client.post(
            "/chat",
            json={
                "request_id": "req-api-blank",
                "session_id": "session-api-blank",
                "query": "   ",
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
