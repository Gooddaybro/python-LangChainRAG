import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from clothing_assistant.api.app import app
from clothing_assistant.api.streaming import (
    build_stream_done_payload,
    format_sse_event,
    iter_answer_chunks,
)


class ChatStreamHelperTests(unittest.TestCase):
    def test_format_sse_event_uses_single_line_json_data(self):
        event = format_sse_event("token", {"content": "我建议\n穿 L 码"})

        self.assertEqual(event.count("\n\n"), 1)
        self.assertTrue(event.startswith("event: token\n"))
        data_line = next(line for line in event.splitlines() if line.startswith("data: "))
        self.assertNotIn("\n", data_line.removeprefix("data: "))
        self.assertEqual(json.loads(data_line.removeprefix("data: ")), {"content": "我建议\n穿 L 码"})

    def test_iter_answer_chunks_splits_answer_without_dropping_text(self):
        chunks = list(iter_answer_chunks("abcdefghijklmnop", chunk_size=5))

        self.assertEqual(chunks, ["abcde", "fghij", "klmno", "p"])
        self.assertEqual("".join(chunks), "abcdefghijklmnop")

    def test_iter_answer_chunks_returns_empty_list_for_empty_answer(self):
        self.assertEqual(list(iter_answer_chunks("")), [])

    def test_build_stream_done_payload_keeps_python_to_java_contract_shape(self):
        agent_result = {
            "answer": "我建议您穿 L 码。",
            "debug": {
                "intent_result": {"intent": "size_recommendation"},
            },
        }

        payload = build_stream_done_payload(agent_result, request_id="req-stream-1")

        self.assertEqual(
            payload,
            {
                "request_id": "req-stream-1",
                "answer": "我建议您穿 L 码。",
                "intent": "size_recommendation",
                "product_refs": [],
            },
        )


def parse_sse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        event_name = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(json.loads(line.removeprefix("data: ")) for line in lines if line.startswith("data: "))
        events.append((event_name, data))
    return events


class ChatStreamEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_chat_stream_calls_langgraph_and_returns_token_then_done(self):
        fake_result = {
            "answer": "我建议您穿 L 码。",
            "debug": {
                "intent_result": {"intent": "size_recommendation"},
                "stop_reason": "final_answer",
            },
        }

        with patch(
            "clothing_assistant.api.app.run_langgraph_agent",
            return_value=fake_result,
        ) as mock_run:
            with self.client.stream(
                "POST",
                "/chat/stream",
                json={
                    "request_id": "req-stream-api-1",
                    "session_id": "session-stream-api-1",
                    "thread_id": "thread-stream-api-1",
                    "query": "我 175cm 70kg 穿什么码？",
                    "chat_history": [],
                    "user_context": {"user_id": 10001, "height_cm": 175, "weight_kg": 70},
                    "candidates": [],
                    "debug": False,
                },
            ) as response:
                body = response.read().decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        events = parse_sse_events(body)
        self.assertEqual(events[0], ("token", {"content": "我建议您穿 L 码。"}))
        self.assertEqual(
            events[-1],
            (
                "done",
                {
                    "request_id": "req-stream-api-1",
                    "answer": "我建议您穿 L 码。",
                    "intent": "size_recommendation",
                    "product_refs": [],
                },
            ),
        )
        mock_run.assert_called_once_with(
            "我 175cm 70kg 穿什么码？",
            chat_history=[],
            thread_id="thread-stream-api-1",
            request_id="req-stream-api-1",
            session_id="session-stream-api-1",
            user_context={"user_id": 10001, "height_cm": 175.0, "weight_kg": 70.0},
            candidates=[],
        )

    def test_chat_stream_uses_session_id_when_thread_id_is_absent(self):
        fake_result = {
            "answer": "我是服装导购助手。",
            "debug": {"intent_result": {"intent": "chat"}},
        }

        with patch(
            "clothing_assistant.api.app.run_langgraph_agent",
            return_value=fake_result,
        ) as mock_run:
            with self.client.stream(
                "POST",
                "/chat/stream",
                json={
                    "request_id": "req-stream-api-2",
                    "session_id": "session-stream-api-2",
                    "query": "你是谁？",
                },
            ) as response:
                body = response.read().decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(parse_sse_events(body)[-1][1]["request_id"], "req-stream-api-2")
        mock_run.assert_called_once_with(
            "你是谁？",
            chat_history=[],
            thread_id="session-stream-api-2",
            request_id="req-stream-api-2",
            session_id="session-stream-api-2",
            user_context={},
            candidates=[],
        )

    def test_chat_stream_returns_error_event_without_internal_details(self):
        with (
            patch(
                "clothing_assistant.api.app.run_langgraph_agent",
                side_effect=RuntimeError("secret provider stack trace"),
            ),
            patch("clothing_assistant.api.app.logger.exception") as mock_log_exception,
        ):
            with self.client.stream(
                "POST",
                "/chat/stream",
                json={
                    "request_id": "req-stream-api-error",
                    "session_id": "session-stream-api-error",
                    "query": "你是谁？",
                },
            ) as response:
                body = response.read().decode("utf-8")

        mock_log_exception.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("secret provider stack trace", body)
        self.assertEqual(
            parse_sse_events(body),
            [
                (
                    "error",
                    {
                        "code": "internal_error",
                        "message": "AI service failed to process the request.",
                    },
                )
            ],
        )

    def test_chat_stream_rejects_invalid_request_before_streaming(self):
        response = self.client.post(
            "/chat/stream",
            json={
                "request_id": "req-invalid-stream",
                "session_id": "session-invalid-stream",
                "query": "   ",
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
