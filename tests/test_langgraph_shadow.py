import unittest
from uuid import uuid4

from clothing_assistant.agent.eval_cases import (
    EVAL_CASES,
    case_supports_executor,
    get_expected_value,
)
from clothing_assistant.agent import nodes
from clothing_assistant.agent.langgraph_executor import (
    get_default_langgraph_agent,
    run_langgraph_agent,
)
from clothing_assistant.agent.tool_registry import build_default_tool_registry


def fake_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "shadow-chunk-001",
                "file_name": "颜色选择.txt",
                "content": "用于 LangGraph 主线测试的知识库资料。",
                "score": 0.1,
            }
        ],
        "source_count": 1,
    }


def fake_policy_runner(query):
    return {
        "has_policy_source": False,
        "policy_answer": "当前知识库没有退换货、物流或售后政策资料，建议联系人工客服确认。",
        "retrieval_query": query,
        "policy_chunks": [],
        "raw_retrieved_chunks": [],
        "source_count": 0,
        "reason": "langgraph no policy source",
    }


def fake_size_runner(query, chat_history=None):
    return {
        "recommended_size": "L",
        "reason": "langgraph size",
        "alternative": "XL" if "宽松" in query else None,
        "match_type": "exact",
        "preference": None,
        "size_query": query,
        "measurements": {},
        "raw_match": {},
    }


def fake_answer_generator(state):
    return f"langgraph answer for {state['intent_result']['intent']}", "langgraph prompt"


def build_fake_registry():
    return build_default_tool_registry(
        rag_runner=fake_rag_runner,
        policy_runner=fake_policy_runner,
        size_runner=fake_size_runner,
    )


class LangGraphShadowTests(unittest.TestCase):
    def test_nodes_module_exposes_graph_node_functions(self):
        self.assertTrue(callable(nodes.route_intent_node))
        self.assertTrue(callable(nodes.resolve_memory_node))
        self.assertTrue(callable(nodes.direct_answer_node))
        self.assertTrue(callable(nodes.execute_tools_node))
        self.assertTrue(callable(nodes.policy_fallback_node))
        self.assertTrue(callable(nodes.fallback_rag_node))
        self.assertTrue(callable(nodes.generate_answer_node))
        self.assertTrue(callable(nodes.tool_budget_exhausted_node))

    def test_default_langgraph_agent_is_cached(self):
        self.assertIs(get_default_langgraph_agent(), get_default_langgraph_agent())

    def test_default_langgraph_agent_persists_checkpoints_by_thread_id(self):
        thread_id = f"test-thread-{uuid4()}"

        result = run_langgraph_agent("你是谁？", thread_id=thread_id)
        graph = get_default_langgraph_agent()
        history = list(graph.get_state_history({"configurable": {"thread_id": thread_id}}))

        self.assertEqual(result["debug"]["thread_id"], thread_id)
        self.assertGreater(len(history), 0)

    def test_response_debug_includes_thread_and_run_ids(self):
        result = run_langgraph_agent(
            "你是谁？",
            thread_id="learn-thread",
            tool_registry=build_fake_registry(),
            answer_generator=fake_answer_generator,
        )
        debug = result["debug"]
        trace_steps = [event["step"] for event in debug["trace_events"]]

        self.assertEqual(debug["thread_id"], "learn-thread")
        self.assertTrue(debug["run_id"])
        self.assertIn("run_started", trace_steps)
        self.assertEqual(debug["trace_events"][0]["data"]["thread_id"], "learn-thread")
        self.assertEqual(debug["trace_events"][0]["data"]["run_id"], debug["run_id"])

    def test_response_debug_includes_java_request_context(self):
        user_context = {
            "user_id": 10001,
            "height_cm": 175,
            "weight_kg": 70,
            "preferred_styles": ["commute"],
        }
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "通勤轻薄外套",
            }
        ]

        result = run_langgraph_agent(
            "你是谁？",
            thread_id="learn-thread-with-context",
            request_id="req-langgraph-1",
            session_id="session-langgraph-1",
            user_context=user_context,
            candidates=candidates,
            tool_registry=build_fake_registry(),
            answer_generator=fake_answer_generator,
        )
        debug = result["debug"]

        self.assertEqual(debug["request_id"], "req-langgraph-1")
        self.assertEqual(debug["session_id"], "session-langgraph-1")
        self.assertEqual(debug["user_context"], user_context)
        self.assertEqual(debug["candidates"], candidates)
        self.assertEqual(debug["trace_events"][0]["data"]["request_id"], "req-langgraph-1")
        self.assertEqual(debug["trace_events"][0]["data"]["session_id"], "session-langgraph-1")

    def test_missing_thread_id_is_generated(self):
        result = run_langgraph_agent(
            "你是谁？",
            tool_registry=build_fake_registry(),
            answer_generator=fake_answer_generator,
        )

        self.assertTrue(result["debug"]["thread_id"].startswith("thread-"))
        self.assertTrue(result["debug"]["run_id"].startswith("run-"))

    def test_direct_answer_uses_no_tools(self):
        result = run_langgraph_agent(
            "你是谁？",
            tool_registry=build_fake_registry(),
            answer_generator=fake_answer_generator,
        )

        self.assertEqual(result["debug"]["selected_tools"], [])
        self.assertEqual(result["debug"]["stop_reason"], "direct_answer")

    def test_policy_fallback_stops_graph(self):
        result = run_langgraph_agent(
            "可以退货吗？",
            tool_registry=build_fake_registry(),
            answer_generator=fake_answer_generator,
        )

        self.assertEqual(result["debug"]["selected_tools"], ["policy_tool"])
        self.assertEqual(result["debug"]["stop_reason"], "policy_fallback")
        self.assertIn("当前知识库没有退换货", result["answer"])

    def test_product_question_uses_rag_and_generates_answer(self):
        result = run_langgraph_agent(
            "这件衣服适合夏天吗？",
            tool_registry=build_fake_registry(),
            answer_generator=fake_answer_generator,
        )

        self.assertEqual(result["debug"]["selected_tools"], ["rag_tool"])
        self.assertEqual(result["debug"]["stop_reason"], "final_answer")
        self.assertGreater(len(result["debug"]["retrieved_chunks"]), 0)

    def test_langgraph_records_tool_call_count(self):
        result = run_langgraph_agent(
            "我身高175cm，体重70kg，这件T恤适合我吗？",
            tool_registry=build_fake_registry(),
            answer_generator=fake_answer_generator,
        )

        self.assertEqual(result["debug"]["selected_tools"], ["size_tool", "rag_tool"])
        self.assertEqual(result["debug"]["tool_call_count"], 2)

    def test_tool_budget_zero_stops_before_tools(self):
        result = run_langgraph_agent(
            "这件衣服适合夏天吗？",
            tool_registry=build_fake_registry(),
            answer_generator=fake_answer_generator,
            max_tool_calls=0,
        )

        self.assertEqual(result["debug"]["selected_tools"], [])
        self.assertEqual(result["debug"]["tool_call_count"], 0)
        self.assertEqual(result["debug"]["stop_reason"], "tool_budget_exhausted")
        self.assertIn("工具调用次数已达到上限", result["answer"])

    def test_eval_cases_match_expected_contracts(self):
        registry = build_fake_registry()

        for case in EVAL_CASES:
            if not case_supports_executor(case, "langgraph"):
                continue

            with self.subTest(case=case["name"]):
                result = run_langgraph_agent(
                    case["query"],
                    chat_history=case.get("chat_history"),
                    tool_registry=registry,
                    answer_generator=fake_answer_generator,
                )
                debug = result["debug"]

                self.assertEqual(
                    debug["intent_result"]["intent"],
                    get_expected_value(case, "langgraph", "expected_intent"),
                )
                self.assertEqual(
                    debug["selected_tools"],
                    get_expected_value(case, "langgraph", "expected_tools"),
                )
                self.assertEqual(
                    debug["stop_reason"],
                    get_expected_value(case, "langgraph", "expected_stop_reason"),
                )

                if get_expected_value(case, "langgraph", "requires_rag"):
                    self.assertGreater(len(debug["retrieved_chunks"]), 0)
                else:
                    self.assertEqual(len(debug["retrieved_chunks"]), 0)


if __name__ == "__main__":
    unittest.main()
