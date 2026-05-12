import unittest

from clothing_rag_demo.agent.eval_cases import EVAL_CASES
from clothing_rag_demo.agent.langgraph_executor import run_langgraph_agent
from clothing_rag_demo.agent.tool_registry import build_default_tool_registry


def fake_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "shadow-chunk-001",
                "file_name": "颜色选择.txt",
                "content": "用于 LangGraph shadow 测试的知识库资料。",
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
        "reason": "shadow no policy source",
    }


def fake_size_runner(query, chat_history=None):
    return {
        "recommended_size": "L",
        "reason": "shadow size",
        "alternative": "XL" if "宽松" in query else None,
        "match_type": "exact",
        "preference": None,
        "size_query": query,
        "measurements": {},
        "raw_match": {},
    }


def fake_answer_generator(state):
    return f"shadow answer for {state.intent_result['intent']}", "shadow prompt"


def build_fake_registry():
    return build_default_tool_registry(
        rag_runner=fake_rag_runner,
        policy_runner=fake_policy_runner,
        size_runner=fake_size_runner,
    )


class LangGraphShadowTests(unittest.TestCase):
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

    def test_eval_cases_match_expected_contracts(self):
        registry = build_fake_registry()

        for case in EVAL_CASES:
            with self.subTest(case=case["name"]):
                result = run_langgraph_agent(
                    case["query"],
                    chat_history=case.get("chat_history"),
                    tool_registry=registry,
                    answer_generator=fake_answer_generator,
                )
                debug = result["debug"]

                self.assertEqual(debug["intent_result"]["intent"], case["expected_intent"])
                self.assertEqual(debug["selected_tools"], case["expected_tools"])
                self.assertEqual(debug["stop_reason"], case["expected_stop_reason"])

                if case["requires_rag"]:
                    self.assertGreater(len(debug["retrieved_chunks"]), 0)
                else:
                    self.assertEqual(len(debug["retrieved_chunks"]), 0)


if __name__ == "__main__":
    unittest.main()
