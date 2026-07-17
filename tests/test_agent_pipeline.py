import os
import unittest
from pathlib import Path

from clothing_assistant.agent import agent_executor
from clothing_assistant.agent.agent_executor import run_agent
from clothing_assistant.agent.langgraph_executor import run_langgraph_agent
from clothing_assistant.agent.state import AgentState, make_trace
from clothing_assistant.agent.tool_registry import (
    build_default_tool_registry,
    matching_tool_names,
)
from clothing_assistant.agent.tracing import persist_trace_if_enabled
from clothing_assistant.application import answer_service
from clothing_assistant.config_data import BASE_DIR


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


def fake_empty_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [],
        "source_count": 0,
        "rag_meta": {"version": "test-rag-version", "chunk_count": 0},
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
    def test_make_trace_creates_trace_event(self):
        """make_trace 创建标准 trace 事件列表，供 mutate 函数返回。"""
        events = make_trace("route_intent", intent="chat")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["step"], "route_intent")
        self.assertEqual(events[0]["data"]["intent"], "chat")

    def test_answer_service_is_shared_by_legacy_pipeline(self):
        self.assertIs(agent_executor.build_final_prompt, answer_service.build_final_prompt)
        self.assertIs(agent_executor.default_answer_generator, answer_service.default_answer_generator)
        self.assertIs(agent_executor.build_response_from_state, answer_service.build_response_from_state)

    def test_tool_registry_selects_size_and_rag_for_product_size_question(self):
        state: AgentState = {
            "user_query": "我身高175cm，体重70kg，这件T恤适合我吗？",
            "intent_result": {
                "intent": "size_recommendation",
                "query_type": "size",
                "need_history": False,
                "reason": "test",
            },
            "memory_result": {
                "used_history": {},
                "need_history": False,
            },
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
        self.assertEqual(result["debug"]["tool_call_count"], 1)
        self.assertEqual(result["debug"]["stop_reason"], "final_answer")
        self.assertIn("trace_events", result["debug"])
        self.assertIn("tool_result", [event["step"] for event in result["debug"]["trace_events"]])

    def test_recommendation_uses_java_candidates_when_rag_is_empty(self):
        registry = build_default_tool_registry(
            rag_runner=fake_empty_rag_runner,
            policy_runner=fake_policy_runner,
            size_runner=fake_size_runner,
        )
        candidates = [
            {
                "spu_id": 1002,
                "sku_id": 2101,
                "name": "通勤夹克",
                "category_name": "外套",
                "fit_type": "合身",
                "color": "黑色",
                "size": "M",
                "materials": "棉混纺",
                "seasons": ["spring", "autumn"],
                "style_tags": ["commute", "minimal"],
                "sale_price": 299.0,
                "stock_status": "in_stock",
                "attribute_tags": ["适用场景:通勤", "风格:简洁"],
            }
        ]

        result = run_langgraph_agent(
            "推荐一件500以内适合通勤的外套",
            tool_registry=registry,
            answer_generator=fake_answer_generator,
            candidates=candidates,
            user_context={"user_id": 1},
            thread_id="test-recommendation-candidates",
        )

        self.assertEqual(result["debug"]["retrieval_route"]["status"], "empty")
        self.assertEqual(result["debug"]["stop_reason"], "final_answer")
        self.assertEqual(result["debug"]["recommendation_source"], "java_candidates_with_ai_rerank")
        self.assertIn("semantic_preferences", result["debug"])
        self.assertIn("candidate_scores", result["debug"])
        self.assertEqual(result["debug"]["selected_product_refs"], result["product_refs"])
        self.assertEqual(result["debug"]["rag_meta"]["version"], "test-rag-version")
        self.assertEqual(result["product_refs"][0]["spu_id"], 1002)
        self.assertIn("通勤夹克", result["answer"])
        self.assertNotIn("当前知识库没有检索到", result["answer"])

    def test_outfit_search_with_slimming_budget_uses_candidates_when_rag_is_empty(self):
        registry = build_default_tool_registry(
            rag_runner=fake_empty_rag_runner,
            policy_runner=fake_policy_runner,
            size_runner=fake_size_runner,
        )
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "通勤轻薄风衣",
                "category_name": "外套",
                "fit_type": "合身",
                "color": "黑色",
                "size": "M",
                "materials": "棉混纺",
                "seasons": ["spring"],
                "style_tags": ["commute", "basic"],
                "sale_price": 439.0,
                "stock_status": "in_stock",
                "attribute_tags": ["适用场景:通勤", "风格:简洁"],
            }
        ]

        result = run_langgraph_agent(
            "我想找一套适合春天通勤的穿搭，显瘦一点，预算500以内",
            tool_registry=registry,
            answer_generator=fake_answer_generator,
            candidates=candidates,
            user_context={"user_id": 1},
            thread_id="test-outfit-search-candidates",
        )

        self.assertEqual(result["debug"]["intent_result"]["intent"], "recommendation")
        self.assertEqual(result["debug"]["retrieval_route"]["status"], "empty")
        self.assertEqual(result["debug"]["stop_reason"], "final_answer")
        self.assertEqual(result["product_refs"][0]["spu_id"], 1001)
        self.assertIn("通勤轻薄风衣", result["answer"])
        self.assertNotIn("当前知识库没有检索到", result["answer"])

    def test_price_check_uses_java_candidate_price(self):
        candidates = [
            {
                "spu_id": 9101,
                "sku_id": 9201,
                "spu_code": "JAVA_ONLY_TSHIRT",
                "sku_code": "JAVA_ONLY_TSHIRT-BLACK-L",
                "name": "候选款测试T恤",
                "category": "T恤",
                "color": "黑色",
                "size": "L",
                "sale_price": 123.0,
                "stock_status": "in_stock",
                "available_stock": 17,
            }
        ]

        result = run_langgraph_agent(
            "候选款测试T恤多少钱？",
            candidates=candidates,
            user_context={"user_id": 1},
            thread_id="test-price-uses-java-candidates",
        )

        self.assertEqual(result["debug"]["stop_reason"], "final_answer")
        self.assertIn("候选款测试T恤", result["answer"])
        self.assertIn("123", result["answer"])
        self.assertNotIn("99", result["answer"])
        self.assertEqual(result["debug"]["structured_result"]["reason"], "价格来自 Java 候选商品。")

    def test_inventory_check_uses_java_candidate_stock(self):
        candidates = [
            {
                "spu_id": 9101,
                "sku_id": 9201,
                "spu_code": "JAVA_ONLY_TSHIRT",
                "sku_code": "JAVA_ONLY_TSHIRT-BLACK-L",
                "name": "候选款测试T恤",
                "category": "T恤",
                "color": "黑色",
                "size": "L",
                "sale_price": 123.0,
                "stock_status": "in_stock",
                "available_stock": 17,
            }
        ]

        result = run_langgraph_agent(
            "候选款测试T恤黑色L码有货吗？",
            candidates=candidates,
            user_context={"user_id": 1},
            thread_id="test-inventory-uses-java-candidates",
        )

        self.assertEqual(result["debug"]["stop_reason"], "final_answer")
        self.assertIn("候选款测试T恤", result["answer"])
        self.assertIn("黑色", result["answer"])
        self.assertIn("L", result["answer"])
        self.assertIn("17", result["answer"])
        self.assertEqual(result["debug"]["structured_result"]["reason"], "库存来自 Java 候选商品。")

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
        state: AgentState = {
            "user_query": "你是谁？",
            "answer": "我是服装导购助手。",
            "stop_reason": "direct_answer",
            "selected_tools": [],
            "tool_call_count": 0,
        }
        trace_events = make_trace("direct_answer", intent="chat")

        trace_dir = BASE_DIR.parent / ".test_tmp" / "trace_test"
        trace_dir.mkdir(parents=True, exist_ok=True)

        old_enabled = os.environ.get("AGENT_TRACE_TO_FILE")
        old_dir = os.environ.get("AGENT_TRACE_DIR")
        os.environ["AGENT_TRACE_TO_FILE"] = "true"
        os.environ["AGENT_TRACE_DIR"] = str(trace_dir)
        try:
            trace_path = persist_trace_if_enabled(state, trace_events)
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

    def test_trace_persistence_redacts_obvious_secrets(self):
        state: AgentState = {
            "user_query": "Authorization: Bearer abc123 password=raw-secret",
            "answer": "token=assistant-secret",
            "stop_reason": "direct_answer",
            "selected_tools": [],
            "tool_call_count": 0,
        }
        trace_events = make_trace("direct_answer", detail="api_key=provider-secret")

        trace_dir = BASE_DIR.parent / ".test_tmp" / "trace_redaction_test"
        trace_dir.mkdir(parents=True, exist_ok=True)

        old_enabled = os.environ.get("AGENT_TRACE_TO_FILE")
        old_dir = os.environ.get("AGENT_TRACE_DIR")
        os.environ["AGENT_TRACE_TO_FILE"] = "true"
        os.environ["AGENT_TRACE_DIR"] = str(trace_dir)
        try:
            trace_path = persist_trace_if_enabled(state, trace_events)
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

        self.assertNotIn("abc123", trace_content)
        self.assertNotIn("raw-secret", trace_content)
        self.assertNotIn("assistant-secret", trace_content)
        self.assertNotIn("provider-secret", trace_content)
        self.assertIn("[已隐藏]", trace_content)


if __name__ == "__main__":
    unittest.main()
