import asyncio
import json
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from clothing_assistant.agent.langgraph_executor import (
    AgentStreamEvent,
    run_langgraph_agent,
    stream_langgraph_agent,
)
from clothing_assistant.agent.tool_registry import build_default_tool_registry
from clothing_assistant.api.app import app, generate_chat_stream
from clothing_assistant.api.schemas import PythonChatRequest
from clothing_assistant.api.streaming import (
    SafeTokenBuffer,
    UnsafeStreamContent,
    build_stream_done_payload,
    format_sse_event,
    iter_answer_chunks,
)
from clothing_assistant.agent.nodes import find_forbidden_rag_fact


class ChatStreamHelperTests(unittest.TestCase):
    def test_safe_token_buffer_preserves_provider_fragments_and_holds_tail(self):
        buffer = SafeTokenBuffer(tail_chars=4, validator=lambda _: None)

        emitted = []
        emitted.extend(buffer.push("abc"))
        emitted.extend(buffer.push("def"))
        emitted.extend(buffer.push(""))

        self.assertEqual(emitted, ["ab"])
        self.assertEqual(buffer.text, "abcdef")
        self.assertEqual(buffer.emitted_text, "ab")
        self.assertEqual(buffer.finish(), ["cdef"])
        self.assertEqual(buffer.emitted_text, "abcdef")

    def test_safe_token_buffer_blocks_forbidden_fact_split_across_fragments(self):
        cases = (
            ("这件衣服库存 ", "8 件。"),
            ("当前售价 9", "9 元。"),
            ("商品 S", "KU ABC 已上架。"),
        )

        for first, second in cases:
            with self.subTest(text=first + second):
                buffer = SafeTokenBuffer(tail_chars=32, validator=find_forbidden_rag_fact)
                emitted = buffer.push(first)
                with self.assertRaises(UnsafeStreamContent):
                    buffer.push(second)

                self.assertEqual(emitted, [])
                self.assertEqual(buffer.emitted_text, "")

    def test_safe_token_buffer_never_releases_offending_buffered_suffix(self):
        buffer = SafeTokenBuffer(tail_chars=32, validator=find_forbidden_rag_fact)
        safe_prefix = "适合通勤的低饱和基础色。" * 4
        emitted = buffer.push(safe_prefix)

        with self.assertRaises(UnsafeStreamContent):
            buffer.push("库存 8 件。")

        self.assertEqual("".join(emitted), safe_prefix[:-32])
        self.assertNotIn("库存", buffer.emitted_text)

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
                "rejected_reasons": {},
            },
        )

    def test_build_stream_done_payload_includes_product_refs(self):
        product_refs = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "reason": "尺码匹配。",
                "rank_score": 0.93,
            }
        ]
        agent_result = {
            "answer": "推荐这件外套。",
            "product_refs": product_refs,
            "rejected_reasons": {"OVER_BUDGET": 2},
            "debug": {
                "intent_result": {"intent": "recommendation"},
            },
        }

        payload = build_stream_done_payload(agent_result, request_id="req-stream-product-refs")

        self.assertEqual(payload["product_refs"], product_refs)
        self.assertEqual(payload["rejected_reasons"], {"OVER_BUDGET": 2})
        self.assertNotIn("debug", payload)


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

    def test_streaming_executor_emits_provider_token_before_model_finishes(self):
        release_model = threading.Event()
        model_finished = threading.Event()

        def fake_stream_content(_messages, stop_requested=None):
            yield "通勤"
            release_model.wait(timeout=2)
            if not (stop_requested and stop_requested()):
                yield "建议"
            model_finished.set()

        registry = build_default_tool_registry(
            rag_runner=lambda query, query_type=None: {
                "retrieval_query": query,
                "retrieved_chunks": [
                    {
                        "chunk_id": "颜色选择.txt-001",
                        "file_name": "颜色选择.txt",
                        "domain": "color",
                        "content": "通勤适合低饱和基础色。",
                        "score": 0.1,
                    }
                ],
                "source_count": 1,
            },
        )

        with patch(
            "clothing_assistant.agent.langgraph_executor.get_stream_safety_tail_chars",
            return_value=1,
            create=True,
        ):
            events = stream_langgraph_agent(
                "通勤适合什么颜色？",
                tool_registry=registry,
                stream_content=fake_stream_content,
                checkpointer=InMemorySaver(),
            )
            try:
                first = next(event for event in events if event.kind != "heartbeat")
                self.assertEqual(first.kind, "token")
                self.assertFalse(model_finished.is_set())
            finally:
                release_model.set()
                list(events)

    def test_closing_streaming_executor_closes_provider_iterator(self):
        provider_closed = threading.Event()

        def blocking_stream(_messages, stop_requested=None):
            try:
                yield "第一段安全内容"
                while not (stop_requested and stop_requested()):
                    threading.Event().wait(0.01)
            finally:
                provider_closed.set()

        registry = build_default_tool_registry(
            rag_runner=lambda query, query_type=None: {
                "retrieval_query": query,
                "retrieved_chunks": [
                    {
                        "chunk_id": "颜色选择.txt-001",
                        "file_name": "颜色选择.txt",
                        "domain": "color",
                        "content": "通勤适合低饱和基础色。",
                        "score": 0.1,
                    }
                ],
                "source_count": 1,
            },
        )

        with patch(
            "clothing_assistant.agent.langgraph_executor.get_stream_safety_tail_chars",
            return_value=1,
        ):
            events = stream_langgraph_agent(
                "通勤适合什么颜色？",
                tool_registry=registry,
                stream_content=blocking_stream,
                checkpointer=InMemorySaver(),
            )
            first = next(event for event in events if event.kind != "heartbeat")
            self.assertEqual(first.kind, "token")
            events.close()

        self.assertTrue(provider_closed.wait(timeout=1))

    def test_deterministic_sync_and_stream_results_are_consistent(self):
        sync_result = run_langgraph_agent(
            "你是谁？",
            thread_id="sync-consistency",
            checkpointer=InMemorySaver(),
        )
        events = list(
            stream_langgraph_agent(
                "你是谁？",
                thread_id="stream-consistency",
                checkpointer=InMemorySaver(),
            )
        )
        tokens = "".join(event.content for event in events if event.kind == "token")
        stream_result = next(event.result for event in events if event.kind == "result")

        self.assertEqual(tokens, stream_result["answer"])
        self.assertEqual(stream_result["answer"], sync_result["answer"])
        self.assertEqual(stream_result["product_refs"], sync_result["product_refs"])
        self.assertEqual(
            stream_result["debug"]["intent_result"]["intent"],
            sync_result["debug"]["intent_result"]["intent"],
        )
        self.assertEqual(stream_result["debug"]["stop_reason"], sync_result["debug"]["stop_reason"])

    def test_forbidden_streaming_generation_retries_then_emits_only_safe_fallback(self):
        generation_calls = 0

        def forbidden_stream(_messages, stop_requested=None):
            nonlocal generation_calls
            generation_calls += 1
            yield "这件衣服库存 8 件，售价 99 元。"

        registry = build_default_tool_registry(
            rag_runner=lambda query, query_type=None: {
                "retrieval_query": query,
                "retrieved_chunks": [
                    {
                        "chunk_id": "颜色选择.txt-001",
                        "file_name": "颜色选择.txt",
                        "domain": "color",
                        "content": "通勤适合低饱和基础色。",
                        "score": 0.1,
                    }
                ],
                "source_count": 1,
            },
        )

        events = list(
            stream_langgraph_agent(
                "通勤适合什么颜色？",
                tool_registry=registry,
                stream_content=forbidden_stream,
                checkpointer=InMemorySaver(),
            )
        )
        public_text = "".join(event.content for event in events if event.kind == "token")
        result = next(event.result for event in events if event.kind == "result")

        self.assertEqual(generation_calls, 2)
        self.assertNotIn("库存 8", public_text)
        self.assertNotIn("99 元", public_text)
        self.assertEqual(public_text, result["answer"])
        self.assertEqual(result["debug"]["stop_reason"], "answer_fallback")

    def test_disconnected_http_stream_closes_executor_without_reading_events(self):
        class DisconnectedRequest:
            async def is_disconnected(self):
                return True

        class InternalEvents:
            def __init__(self):
                self.next_calls = 0
                self.closed = False

            def __iter__(self):
                return self

            def __next__(self):
                self.next_calls += 1
                raise AssertionError("disconnected request must not read graph events")

            def close(self):
                self.closed = True

        internal_events = InternalEvents()
        chat_request = PythonChatRequest(
            request_id="req-disconnected",
            session_id="session-disconnected",
            query="你是谁？",
        )

        async def collect_events():
            return [
                event
                async for event in generate_chat_stream(chat_request, DisconnectedRequest())
            ]

        with patch(
            "clothing_assistant.api.app.stream_langgraph_agent",
            return_value=internal_events,
            create=True,
        ):
            emitted = asyncio.run(collect_events())

        self.assertEqual(emitted, [])
        self.assertEqual(internal_events.next_calls, 0)
        self.assertTrue(internal_events.closed)

    def test_chat_stream_calls_langgraph_and_returns_token_then_done(self):
        fake_result = {
            "answer": "我建议您穿 L 码。",
            "debug": {
                "intent_result": {"intent": "size_recommendation"},
                "stop_reason": "final_answer",
            },
        }

        with patch(
            "clothing_assistant.api.app.stream_langgraph_agent",
            return_value=iter(
                [
                    AgentStreamEvent(kind="token", content=fake_result["answer"]),
                    AgentStreamEvent(kind="result", result=fake_result),
                ]
            ),
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
                    "rejected_reasons": {},
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
            demand_intent=None,
        )

    def test_chat_stream_done_event_does_not_expose_debug_payload(self):
        fake_result = {
            "answer": "推荐这件通勤外套。",
            "product_refs": [
                {
                    "spu_id": 1001,
                    "sku_id": 2001,
                    "reason": "候选商品匹配通勤场景。",
                    "rank_score": 0.8,
                }
            ],
            "debug": {
                "intent_result": {"intent": "recommendation"},
                "trace_events": [{"step": "run_started"}],
                "selected_tools": ["rag_tool"],
            },
        }

        with patch(
            "clothing_assistant.api.app.stream_langgraph_agent",
            return_value=iter(
                [
                    AgentStreamEvent(kind="token", content=fake_result["answer"]),
                    AgentStreamEvent(kind="result", result=fake_result),
                ]
            ),
        ):
            with self.client.stream(
                "POST",
                "/chat/stream",
                json={
                    "request_id": "req-stream-no-debug",
                    "session_id": "session-stream-no-debug",
                    "query": "推荐一件通勤外套",
                    "debug": True,
                },
            ) as response:
                body = response.read().decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("trace_events", body)
        self.assertNotIn("selected_tools", body)
        events = parse_sse_events(body)
        self.assertEqual(events[-1][0], "done")
        self.assertEqual(events[-1][1]["product_refs"][0]["spu_id"], 1001)
        for line in body.splitlines():
            if line.startswith("data: "):
                self.assertNotIn("\n", line.removeprefix("data: "))
                json.loads(line.removeprefix("data: "))

    def test_chat_stream_uses_session_id_when_thread_id_is_absent(self):
        fake_result = {
            "answer": "我是服装导购助手。",
            "debug": {"intent_result": {"intent": "chat"}},
        }

        with patch(
            "clothing_assistant.api.app.stream_langgraph_agent",
            return_value=iter(
                [
                    AgentStreamEvent(kind="token", content=fake_result["answer"]),
                    AgentStreamEvent(kind="result", result=fake_result),
                ]
            ),
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
            demand_intent=None,
        )

    def test_chat_stream_returns_error_event_without_internal_details(self):
        with patch(
            "clothing_assistant.api.app.stream_langgraph_agent",
            return_value=iter([AgentStreamEvent(kind="error", code="internal_error")]),
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
