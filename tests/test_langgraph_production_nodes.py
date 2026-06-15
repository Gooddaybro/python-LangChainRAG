import unittest

from clothing_assistant.agent.langgraph_executor import run_langgraph_agent
from clothing_assistant.agent.tool_registry import build_default_tool_registry


def fake_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "production-chunk-001",
                "file_name": "颜色选择.txt",
                "content": "黑色更百搭，白色更清爽，通勤场景可以优先选择低饱和颜色。",
                "score": 0.1,
            }
        ],
        "source_count": 1,
    }


def weak_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "weak-chunk-001",
                "file_name": "无关资料.txt",
                "content": "这段资料和用户问题没有可靠关系。",
                "score": 0.95,
            }
        ],
        "source_count": 1,
    }


def empty_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [],
        "source_count": 0,
    }


def fake_policy_runner(query):
    return {
        "has_policy_source": False,
        "policy_answer": "当前知识库没有退换货、物流或售后政策资料，建议联系人工客服确认。",
        "retrieval_query": query,
        "policy_chunks": [],
        "raw_retrieved_chunks": [],
        "source_count": 0,
        "reason": "production no policy source",
    }


def fake_size_runner(query, chat_history=None):
    return {
        "recommended_size": "L",
        "reason": "production size",
        "alternative": None,
        "match_type": "exact",
        "preference": None,
        "size_query": query,
        "measurements": {},
        "raw_match": {},
    }


def fake_answer_generator(state):
    return f"draft for {state['intent_result']['intent']}", "draft prompt"


def build_registry(rag_runner=fake_rag_runner):
    return build_default_tool_registry(
        rag_runner=rag_runner,
        policy_runner=fake_policy_runner,
        size_runner=fake_size_runner,
    )


class LangGraphProductionNodeTests(unittest.TestCase):
    def test_inventory_without_product_stops_at_missing_info_gate(self):
        result = run_langgraph_agent(
            "黑色有货吗？",
            tool_registry=build_registry(),
            answer_generator=fake_answer_generator,
        )
        debug = result["debug"]

        self.assertEqual(debug["stop_reason"], "missing_info")
        self.assertEqual(debug["selected_tools"], [])
        self.assertIn("product", debug["missing_info_result"]["missing_fields"])
        self.assertIn("哪件商品", result["answer"])

    def test_inventory_uses_structured_lookup_not_rag(self):
        result = run_langgraph_agent(
            "基础款纯棉T恤黑色L码有货吗？",
            tool_registry=build_registry(),
            answer_generator=fake_answer_generator,
        )
        debug = result["debug"]

        self.assertEqual(debug["selected_tools"], ["structured_lookup"])
        self.assertEqual(debug["structured_result"]["stock_count"], 8)
        self.assertEqual(debug["retrieved_chunks"], [])
        self.assertIn("8", result["answer"])

    def test_price_uses_catalog_value(self):
        result = run_langgraph_agent(
            "基础款纯棉T恤多少钱？",
            tool_registry=build_registry(),
            answer_generator=fake_answer_generator,
        )
        debug = result["debug"]

        self.assertEqual(debug["selected_tools"], ["structured_lookup"])
        self.assertEqual(debug["structured_result"]["price_cny"], 99)
        self.assertIn("99", result["answer"])

    def test_semantic_question_uses_rag_and_rule_grader(self):
        result = run_langgraph_agent(
            "日常通勤推荐什么颜色？",
            tool_registry=build_registry(),
            answer_generator=fake_answer_generator,
        )
        debug = result["debug"]

        self.assertEqual(debug["selected_tools"], ["rag_tool"])
        self.assertEqual(len(debug["accepted_chunks"]), 1)
        self.assertEqual(debug["retrieval_route"]["status"], "good")
        self.assertEqual(debug["stop_reason"], "final_answer")

    def test_weak_retrieval_is_rejected_before_final_answer(self):
        result = run_langgraph_agent(
            "日常通勤推荐什么颜色？",
            tool_registry=build_registry(rag_runner=weak_rag_runner),
            answer_generator=fake_answer_generator,
        )
        debug = result["debug"]
        trace_steps = [event["step"] for event in debug["trace_events"]]

        self.assertEqual(debug["selected_tools"], ["rag_tool"])
        self.assertEqual(debug["accepted_chunks"], [])
        self.assertEqual(debug["retrieval_route"]["status"], "weak")
        self.assertEqual(debug["stop_reason"], "answer_fallback")
        self.assertIn("没有检索到足够可靠", result["answer"])
        self.assertIn("retrieval_grader", trace_steps)
        self.assertIn("fallback_answer", trace_steps)
        self.assertNotIn("answer_generated", trace_steps)

    def test_empty_retrieval_routes_to_fallback_answer(self):
        result = run_langgraph_agent(
            "日常通勤推荐什么颜色？",
            tool_registry=build_registry(rag_runner=empty_rag_runner),
            answer_generator=fake_answer_generator,
        )
        debug = result["debug"]
        trace_steps = [event["step"] for event in debug["trace_events"]]

        self.assertEqual(debug["selected_tools"], ["rag_tool"])
        self.assertEqual(debug["accepted_chunks"], [])
        self.assertEqual(debug["rejected_chunks"], [])
        self.assertEqual(debug["retrieval_route"]["status"], "empty")
        self.assertEqual(debug["stop_reason"], "answer_fallback")
        self.assertIn("fallback_answer", trace_steps)
        self.assertNotIn("answer_generated", trace_steps)


if __name__ == "__main__":
    unittest.main()
