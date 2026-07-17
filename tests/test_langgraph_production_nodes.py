import unittest
from unittest.mock import patch

from clothing_assistant.agent.langgraph_executor import run_langgraph_agent
from clothing_assistant.agent.nodes import (
    answer_validator_node,
    chunk_is_relevant,
    find_forbidden_rag_fact,
)
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


def forbidden_commerce_fact_answer_generator(state):
    return "这件衣服库存 8 件，售价 99 元，SKU ABC 已上架。", "forbidden commerce fact"


def build_registry(rag_runner=fake_rag_runner):
    return build_default_tool_registry(
        rag_runner=rag_runner,
        policy_runner=fake_policy_runner,
        size_runner=fake_size_runner,
    )


class LangGraphProductionNodeTests(unittest.TestCase):
    def pure_rag_state(self, draft_answer):
        return {
            "structured_result": {},
            "draft_answer": draft_answer,
            "tool_results": {"rag_tool": {"retrieved_chunks": [fake_rag_runner("test")["retrieved_chunks"][0]]}},
            "accepted_chunks": [fake_rag_runner("test")["retrieved_chunks"][0]],
            "candidates": [],
            "intent_result": {"intent": "product_qa"},
            "user_query": "这件衣服适合通勤吗？",
            "user_context": {},
            "demand_intent": {},
        }

    def test_pure_rag_commerce_facts_request_retry(self):
        for draft_answer in ["这件衣服库存 8 件。", "售价 99 元。", "SKU ABC 已上架。"]:
            with self.subTest(draft_answer=draft_answer):
                validation = answer_validator_node(self.pure_rag_state(draft_answer))

                self.assertFalse(validation["validation_result"]["grounded"])
                self.assertTrue(validation["validation_result"]["retryable"])
                self.assertEqual(
                    validation["validation_result"]["reason"],
                    "rag_answer_contains_forbidden_commerce_fact",
                )
                self.assertIn("删除价格、库存、SKU", validation["validation_feedback"])

    def test_forbidden_pure_rag_answer_retries_then_falls_back(self):
        result = run_langgraph_agent(
            "日常通勤推荐什么颜色？",
            tool_registry=build_registry(),
            answer_generator=forbidden_commerce_fact_answer_generator,
        )
        debug = result["debug"]

        self.assertEqual(debug["generation_attempts"], 2)
        self.assertEqual(debug["stop_reason"], "answer_fallback")
        self.assertEqual(
            debug["validation_result"]["reason"],
            "rag_answer_contains_forbidden_commerce_fact",
        )
        self.assertNotIn("库存 8 件", result["answer"])
        self.assertNotIn("99 元", result["answer"])
        self.assertNotIn("SKU", result["answer"])

    def test_java_candidate_price_is_allowed_for_recommendation(self):
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "基础通勤夹克",
                "category": "外套",
                "color": "黑色",
                "stock_status": "in_stock",
                "style_tags": ["commute", "casual", "basic"],
                "attribute_tags": ["适用场景:通勤", "风格:基础款"],
                "sale_price": 269,
            }
        ]

        result = run_langgraph_agent(
            "推荐一件300以内适合学生党通勤、不要太正式的外套",
            candidates=candidates,
            tool_registry=build_registry(),
            answer_generator=forbidden_commerce_fact_answer_generator,
        )

        self.assertEqual(result["debug"]["stop_reason"], "final_answer")
        self.assertTrue(result["debug"]["validation_result"]["grounded"])
        self.assertIn("269 元", result["answer"])

    def test_find_forbidden_rag_fact_returns_matched_commerce_text(self):
        self.assertEqual(find_forbidden_rag_fact("库存 8 件"), "库存 8")
        self.assertEqual(find_forbidden_rag_fact("售价 99 元"), "99 元")
        self.assertEqual(find_forbidden_rag_fact("SKU ABC 已上架"), "SKU")
        self.assertIsNone(find_forbidden_rag_fact("通勤适合低饱和基础色。"))

    def test_new_explanatory_domains_are_allowed_for_semantic_queries(self):
        material_chunk = {"file_name": "材质知识.txt", "score": 0.1}
        scene_chunk = {"file_name": "场景穿搭.txt", "score": 0.1}
        fit_chunk = {"file_name": "版型知识.txt", "score": 0.1}

        self.assertTrue(chunk_is_relevant(material_chunk, "product"))
        self.assertTrue(chunk_is_relevant(scene_chunk, "recommendation"))
        self.assertTrue(chunk_is_relevant(fit_chunk, "size"))

    def test_inventory_without_product_stops_at_missing_info_gate(self):
        result = run_langgraph_agent(
            "黑色有货吗？",
            tool_registry=build_registry(),
            answer_generator=fake_answer_generator,
            allow_demo_catalog=True,
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
            allow_demo_catalog=True,
        )
        debug = result["debug"]

        self.assertEqual(debug["selected_tools"], ["structured_lookup"])
        self.assertEqual(debug["structured_result"]["stock_count"], 8)
        self.assertEqual(debug["validation_result"]["reason"], "structured facts validated")
        self.assertEqual(debug["retrieved_chunks"], [])
        self.assertIn("8", result["answer"])
        self.assertNotIn("参考资料：", result["answer"])

    def test_price_uses_catalog_value(self):
        result = run_langgraph_agent(
            "基础款纯棉T恤多少钱？",
            tool_registry=build_registry(),
            answer_generator=fake_answer_generator,
            allow_demo_catalog=True,
        )
        debug = result["debug"]

        self.assertEqual(debug["selected_tools"], ["structured_lookup"])
        self.assertEqual(debug["structured_result"]["price_cny"], 99)
        self.assertEqual(debug["validation_result"]["reason"], "structured facts validated")
        self.assertIn("99", result["answer"])
        self.assertNotIn("参考资料：", result["answer"])

    def test_production_inventory_without_java_candidates_does_not_use_local_catalog(self):
        with (
            patch(
                "clothing_assistant.agent.nodes.find_matching_product",
                side_effect=AssertionError("local match called"),
            ),
            patch(
                "clothing_assistant.agent.nodes.run_structured_lookup",
                side_effect=AssertionError("local lookup called"),
            ),
        ):
            result = run_langgraph_agent(
                "基础款纯棉T恤黑色L码有货吗？",
                tool_registry=build_registry(),
                answer_generator=fake_answer_generator,
            )

        self.assertEqual(result["debug"]["stop_reason"], "missing_authoritative_candidates")
        self.assertEqual(result["debug"]["selected_tools"], [])
        self.assertEqual(
            result["debug"]["missing_info_result"]["missing_fields"],
            ["authoritative_candidates"],
        )
        self.assertEqual(result["product_refs"], [])
        self.assertNotIn("8 件", result["answer"])

    def test_production_price_without_java_candidates_does_not_use_local_catalog(self):
        with (
            patch(
                "clothing_assistant.agent.nodes.find_matching_product",
                side_effect=AssertionError("local match called"),
            ),
            patch(
                "clothing_assistant.agent.nodes.run_structured_lookup",
                side_effect=AssertionError("local lookup called"),
            ),
        ):
            result = run_langgraph_agent(
                "基础款纯棉T恤多少钱？",
                tool_registry=build_registry(),
                answer_generator=fake_answer_generator,
            )

        self.assertEqual(result["debug"]["stop_reason"], "missing_authoritative_candidates")
        self.assertEqual(result["debug"]["selected_tools"], [])
        self.assertEqual(result["product_refs"], [])
        self.assertNotIn("99", result["answer"])

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
        self.assertIn("参考资料：颜色选择.txt（production-chunk-001）", result["answer"])
        self.assertEqual(
            debug["evidence_summary"]["rag_sources"],
            [{"file_name": "颜色选择.txt", "chunk_id": "production-chunk-001"}],
        )

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
        self.assertNotIn("参考资料：", result["answer"])

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
        self.assertNotIn("参考资料：", result["answer"])


if __name__ == "__main__":
    unittest.main()
