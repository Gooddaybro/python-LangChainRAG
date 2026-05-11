import os
import tempfile
import unittest
from pathlib import Path

from clothing_rag_demo.agent.agent_executor import run_agent
from clothing_rag_demo.agent.state import AgentState
from clothing_rag_demo.agent.tool_registry import (
    build_default_tool_registry,
    matching_tool_names,
)
from clothing_rag_demo.agent.tracing import persist_trace_if_enabled


def fake_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "颜色选择.txt-001",
                "file_name": "颜色选择.txt",
                "content": "日常通勤适合基础色。",
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
        "reason": "test fallback",
    }


def fake_size_runner(query, chat_history=None):
    return {
        "recommended_size": "XL",
        "reason": "test size",
        "alternative": None,
        "match_type": "exact",
        "preference": None,
        "size_query": query,
        "measurements": {},
        "raw_match": {},
    }


def fake_answer_generator(state):
    return "fake answer", "fake prompt"


class AgentPipelineTests(unittest.TestCase):
    def test_agent_state_tracks_trace_events(self):
        state = AgentState(user_query="你是谁？")

        state.add_trace("route_intent", intent="chat")

        self.assertEqual(state.user_query, "你是谁？")
        self.assertEqual(state.selected_tools, [])
        self.assertEqual(state.trace_events[0]["step"], "route_intent")
        self.assertEqual(state.trace_events[0]["data"]["intent"], "chat")

    def test_tool_registry_selects_size_and_rag_for_product_size_question(self):
        state = AgentState(user_query="我身高175cm，体重70kg，这件T恤适合我吗？")
        state.intent_result = {
            "intent": "size_recommendation",
            "query_type": "size",
            "need_history": False,
            "reason": "test",
        }
        state.memory_result = {
            "used_history": {},
            "need_history": False,
        }

        registry = build_default_tool_registry()

        self.assertEqual(matching_tool_names(state, registry), ["rag_tool", "size_tool"])

    def test_run_agent_accepts_fake_tools_and_records_trace(self):
        registry = build_default_tool_registry(
            rag_runner=fake_rag_runner,
            policy_runner=fake_policy_runner,
            size_runner=fake_size_runner,
        )

        result = run_agent(
            "这件衣服适合夏天吗？",
            tool_registry=registry,
            answer_generator=fake_answer_generator,
        )

        self.assertEqual(result["answer"], "fake answer")
        self.assertEqual(result["debug"]["selected_tools"], ["rag_tool"])
        self.assertEqual(result["debug"]["stop_reason"], "final_answer")
        self.assertIn("trace_events", result["debug"])
        self.assertIn("tool_result", [event["step"] for event in result["debug"]["trace_events"]])

    def test_policy_fallback_stops_before_answer_generation(self):
        registry = build_default_tool_registry(
            rag_runner=fake_rag_runner,
            policy_runner=fake_policy_runner,
            size_runner=fake_size_runner,
        )

        def failing_answer_generator(state):
            raise AssertionError("policy fallback should not call answer generator")

        result = run_agent(
            "可以退货吗？",
            tool_registry=registry,
            answer_generator=failing_answer_generator,
        )

        self.assertEqual(result["debug"]["selected_tools"], ["policy_tool"])
        self.assertEqual(result["debug"]["stop_reason"], "policy_fallback")
        self.assertIn("当前知识库没有退换货", result["answer"])

    def test_trace_persistence_is_opt_in(self):
        state = AgentState(user_query="你是谁？")
        state.answer = "我是服装导购助手。"
        state.stop_reason = "direct_answer"
        state.add_trace("direct_answer", intent="chat")

        with tempfile.TemporaryDirectory() as trace_dir:
            old_enabled = os.environ.get("AGENT_TRACE_TO_FILE")
            old_dir = os.environ.get("AGENT_TRACE_DIR")
            os.environ["AGENT_TRACE_TO_FILE"] = "true"
            os.environ["AGENT_TRACE_DIR"] = trace_dir
            try:
                trace_path = persist_trace_if_enabled(state)
                trace_content = Path(trace_path).read_text(encoding="utf-8")
            finally:
                if old_enabled is None:
                    os.environ.pop("AGENT_TRACE_TO_FILE", None)
                else:
                    os.environ["AGENT_TRACE_TO_FILE"] = old_enabled

                if old_dir is None:
                    os.environ.pop("AGENT_TRACE_DIR", None)
                else:
                    os.environ["AGENT_TRACE_DIR"] = old_dir

        self.assertIsNotNone(trace_path)
        self.assertTrue(Path(trace_path).name.endswith(".jsonl"))
        self.assertIn("direct_answer", trace_content)


if __name__ == "__main__":
    unittest.main()
