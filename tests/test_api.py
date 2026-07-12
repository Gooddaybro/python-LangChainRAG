import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from clothing_assistant.api.app import app
from clothing_assistant.api.schemas import PythonChatRequest


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_health_returns_ok(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_rag_health_returns_vector_store_status(self):
        status = {
            "ready": True,
            "reason": "ready",
            "chunk_count": 34,
            "version": "test-version",
            "built_at": "2026-07-10T00:00:00+00:00",
        }
        with patch(
            "clothing_assistant.api.app.get_vector_store_status",
            return_value=status,
        ):
            response = self.client.get("/health/rag")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), status)

    # /chat 现在走 LangGraph 主工作流
    def test_chat_uses_java_contract_and_calls_langgraph_executor(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {
                "intent_result": {"intent": "chat"},
                "stop_reason": "final_answer",
            },
        }

        with (
            patch(
                "clothing_assistant.api.app.run_langgraph_agent",
                return_value=fake_result,
            ) as mock_run,
            patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=True),
        ):
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
            demand_intent=None,
        )

    def test_chat_passes_thread_id_to_langgraph_executor(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {
                "thread_id": "api-thread-1",
                "intent_result": {"intent": "chat"},
            },
        }

        with (
            patch(
                "clothing_assistant.api.app.run_langgraph_agent",
                return_value=fake_result,
            ) as mock_run,
            patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=True),
        ):
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
            demand_intent=None,
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

    def test_chat_hides_debug_when_debug_responses_are_disabled(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {"intent_result": {"intent": "chat"}, "trace_events": [{"step": "secret"}]},
        }
        with (
            patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result),
            patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=False),
        ):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-debug-disabled",
                    "session_id": "session-debug-disabled",
                    "query": "你是谁？",
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("debug", response.json())
        self.assertNotIn("trace_events", response.text)

    def test_chat_includes_debug_only_when_enabled(self):
        fake_result = {"answer": "fake answer", "debug": {"intent_result": {"intent": "chat"}}}
        with (
            patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result),
            patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=True),
        ):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-debug-enabled",
                    "session_id": "session-debug-enabled",
                    "query": "你是谁？",
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["debug"], fake_result["debug"])

    def test_chat_returns_product_refs_from_agent_result(self):
        product_refs = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "reason": "尺码和场景匹配。",
                "rank_score": 0.95,
            }
        ]
        fake_result = {
            "answer": "推荐这件通勤外套。",
            "product_refs": product_refs,
            "debug": {
                "intent_result": {"intent": "recommendation"},
                "stop_reason": "final_answer",
            },
        }

        with patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-api-product-refs",
                    "session_id": "session-api-product-refs",
                    "query": "推荐一件通勤外套",
                    "debug": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["product_refs"], product_refs)

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

    def test_chat_rejects_blank_request_id(self):
        response = self.client.post(
            "/chat",
            json={
                "request_id": "   ",
                "session_id": "session-api-blank-request",
                "query": "你是谁？",
            },
        )

        self.assertEqual(response.status_code, 422)

    def assert_invalid_request_id_is_not_echoed_or_logged(self, invalid_request_id):
        secret = "raw-request-id-secret"
        with (
            patch("clothing_assistant.api.app.logger.warning") as mock_warning,
            patch("clothing_assistant.api.app.logger.error") as mock_error,
        ):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": invalid_request_id,
                    "session_id": "session-invalid-request-id",
                    "query": "   ",
                },
            )

        logged_text = " ".join(
            str(argument)
            for call in mock_warning.call_args_list
            for argument in call.args
        )
        self.assertEqual(response.status_code, 422)
        self.assertIsNone(response.json()["body"])
        self.assertNotIn(secret, response.text)
        self.assertNotIn(secret, logged_text)
        mock_error.assert_not_called()

    def test_chat_does_not_echo_or_log_object_request_id(self):
        self.assert_invalid_request_id_is_not_echoed_or_logged({"trace": "raw-request-id-secret"})

    def test_chat_does_not_echo_or_log_array_request_id(self):
        self.assert_invalid_request_id_is_not_echoed_or_logged(["raw-request-id-secret"])

    def test_chat_does_not_echo_or_log_oversized_request_id(self):
        self.assert_invalid_request_id_is_not_echoed_or_logged("raw-request-id-secret" * 20)

    def test_chat_validation_error_does_not_echo_sensitive_body(self):
        with (
            patch("clothing_assistant.api.app.logger.warning") as mock_log_warning,
            patch("clothing_assistant.api.app.logger.error") as mock_log_error,
        ):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-api-sensitive-validation",
                    "session_id": "session-api-sensitive-validation",
                    "query": "   ",
                    "user_context": {
                        "user_id": 10001,
                        "preferred_colors": ["secret-color"],
                    },
                    "candidates": [
                        {
                            "spu_id": 1002,
                            "sku_id": 2101,
                            "name": "secret candidate",
                        }
                    ],
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["body"], {"request_id": "req-api-sensitive-validation"})
        self.assertNotIn("secret-color", response.text)
        self.assertNotIn("secret candidate", response.text)
        logged_arguments = " ".join(
            str(argument)
            for call in mock_log_warning.call_args_list + mock_log_error.call_args_list
            for argument in call.args
        )
        self.assertNotIn("secret-color", logged_arguments)
        self.assertNotIn("secret candidate", logged_arguments)
        mock_log_error.assert_not_called()

    def test_chat_missing_field_validation_does_not_echo_sensitive_body(self):
        response = self.client.post(
            "/chat",
            json={
                "request_id": "req-api-sensitive-missing-field",
                "query": "推荐一件外套",
                "user_context": {
                    "user_id": 10001,
                    "preferred_colors": ["secret-color"],
                },
                "candidates": [
                    {
                        "spu_id": 1002,
                        "sku_id": 2101,
                        "name": "secret candidate",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["body"], {"request_id": "req-api-sensitive-missing-field"})
        self.assertNotIn("input", response.json()["detail"][0])
        self.assertNotIn("secret-color", response.text)
        self.assertNotIn("secret candidate", response.text)

    def test_chat_rejects_blank_session_id(self):
        response = self.client.post(
            "/chat",
            json={
                "request_id": "req-api-blank-session",
                "session_id": "   ",
                "query": "你是谁？",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_chat_unknown_intent_falls_back_to_unknown(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": "req-api-unknown-intent",
                    "session_id": "session-api-unknown-intent",
                    "query": "你是谁？",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["intent"], "unknown")

    def test_python_chat_request_documents_external_fields(self):
        external_fields = [
            "request_id",
            "session_id",
            "thread_id",
            "query",
            "chat_history",
            "user_context",
            "candidates",
            "debug",
        ]

        for field_name in external_fields:
            with self.subTest(field_name=field_name):
                self.assertTrue(PythonChatRequest.model_fields[field_name].description)

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

    def assert_chat_executor_error_does_not_echo_or_log_invalid_request_id(self, invalid_request_id):
        with (
            patch(
                "clothing_assistant.api.app.run_langgraph_agent",
                side_effect=RuntimeError("executor failure"),
            ),
            patch("clothing_assistant.api.app.logger.exception") as mock_log_exception,
        ):
            response = self.client.post(
                "/chat",
                json={
                    "request_id": invalid_request_id,
                    "session_id": "session-invalid-error-request-id",
                    "query": "你是谁？",
                },
            )

        logged_text = " ".join(
            str(argument)
            for call in mock_log_exception.call_args_list
            for argument in call.args
        )
        self.assertEqual(response.status_code, 500)
        self.assertIsNone(response.json()["request_id"])
        self.assertNotIn(invalid_request_id, response.text)
        self.assertNotIn(invalid_request_id, logged_text)
        mock_log_exception.assert_called_once()

    def test_chat_executor_error_does_not_echo_or_log_whitespace_punctuation_request_id(self):
        self.assert_chat_executor_error_does_not_echo_or_log_invalid_request_id("raw request/id-secret")

    def test_chat_executor_error_does_not_echo_or_log_oversized_request_id(self):
        self.assert_chat_executor_error_does_not_echo_or_log_invalid_request_id("raw-request-id-secret" * 20)

    # /chat/pipeline 走旧手写 pipeline
    def test_pipeline_hides_debug_when_debug_responses_are_disabled(self):
        fake_result = {
            "answer": "pipeline answer",
            "debug": {"trace_events": [{"step": "secret"}]},
        }

        with (
            patch("clothing_assistant.api.app.run_agent", return_value=fake_result),
            patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=False),
        ):
            response = self.client.post(
                "/chat/pipeline",
                json={
                    "query": "我 175cm 70kg 穿什么码？",
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "pipeline answer"})

    def test_pipeline_calls_pipeline_executor(self):
        fake_result = {
            "answer": "pipeline answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with (
            patch(
                "clothing_assistant.api.app.run_agent",
                return_value=fake_result,
            ) as mock_run,
            patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=True),
        ):
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
    def test_langgraph_hides_debug_when_debug_responses_are_disabled(self):
        fake_result = {
            "answer": "shadow answer",
            "debug": {"trace_events": [{"step": "secret"}]},
        }

        with (
            patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result),
            patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=False),
        ):
            response = self.client.post(
                "/chat/langgraph",
                json={
                    "query": "这件衣服适合夏天吗？",
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "shadow answer"})

    def test_langgraph_endpoint_still_works(self):
        fake_result = {
            "answer": "shadow answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with (
            patch(
                "clothing_assistant.api.app.run_langgraph_agent",
                return_value=fake_result,
            ) as mock_run,
            patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=True),
        ):
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
