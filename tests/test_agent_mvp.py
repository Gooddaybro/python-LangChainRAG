import inspect
import unittest

from clothing_assistant.agent.agent_executor import build_agent_query, build_final_prompt
from clothing_assistant.agent.router import (
    INTENT_POLICY_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
    intent_router,
)
from clothing_assistant.tools.memory_tool import run_memory_tool
from clothing_assistant.tools.policy_tool import build_no_policy_source_result
from clothing_assistant.tools.size_tool import build_size_query, run_size_tool


class AgentMvpTests(unittest.TestCase):
    def test_package_imports_work_from_repo_root(self):
        from clothing_assistant.agent.agent_executor import run_agent

        self.assertTrue(callable(run_agent))

    def test_router_identifies_policy_and_size_queries(self):
        self.assertEqual(intent_router("可以退货吗？")["intent"], INTENT_POLICY_QA)
        self.assertEqual(
            intent_router("我 175cm 70kg 穿什么码？")["intent"],
            INTENT_SIZE_RECOMMENDATION,
        )

    def test_router_uses_java_demand_intent_for_short_gender_input(self):
        result = intent_router(
            "男性",
            {"targetGender": "male", "hardFilters": ["targetGender"]},
        )

        self.assertEqual(result["intent"], INTENT_RECOMMENDATION)

    def test_memory_does_not_inject_empty_history_for_reference_words(self):
        memory_result = run_memory_tool("这件衣服适合夏天吗？", [])

        self.assertFalse(memory_result["need_history"])
        self.assertEqual(
            build_agent_query("这件衣服适合夏天吗？", memory_result),
            "这件衣服适合夏天吗？",
        )

    def test_size_tool_uses_history_measurements_for_follow_up(self):
        history = [
            {
                "user_query": "我身高168，体重65kg，想买一件日常穿的T恤",
                "assistant_answer": "建议选择 L 码。",
            }
        ]

        size_query = build_size_query("那我想宽松一点呢？", history)
        result = run_size_tool("那我想宽松一点呢？", chat_history=history)

        self.assertIn("身高168", size_query)
        self.assertEqual(result["recommended_size"], "L")
        self.assertEqual(result["alternative"], "XL")

    def test_size_tool_rejects_large_short_height_high_weight_conflict(self):
        result = run_size_tool("我身高158，体重75kg，想买一件日常穿的T恤")

        self.assertEqual(result["match_type"], "measurement_conflict")
        self.assertIsNone(result["recommended_size"])
        self.assertIsNone(result["alternative"])
        self.assertIn("S", result["reason"])
        self.assertIn("XL", result["reason"])
        self.assertIn("无法给出单一可靠尺码", result["reason"])

    def test_size_tool_rejects_large_tall_height_low_weight_conflict(self):
        result = run_size_tool("我身高188，体重65kg，想买一件日常穿的T恤")

        self.assertEqual(result["match_type"], "measurement_conflict")
        self.assertIsNone(result["recommended_size"])
        self.assertIsNone(result["alternative"])
        self.assertIn("4XL", result["reason"])
        self.assertIn("XL", result["reason"])
        self.assertIn("无法给出单一可靠尺码", result["reason"])

    def test_size_tool_keeps_adjacent_mixed_recommendation(self):
        result = run_size_tool("我身高160，体重60kg，想买一件日常穿的T恤")

        self.assertEqual(result["match_type"], "mixed")
        self.assertEqual(result["recommended_size"], "M")
        self.assertEqual(result["alternative"], "L")

    def test_domain_size_matching_is_config_free(self):
        from clothing_assistant.domain import size_matching

        source = inspect.getsource(size_matching)
        self.assertNotIn("config_data", source)
        self.assertNotIn("DATA_DIR", source)

        rule = size_matching.parse_size_rule_line("身高：165-175cm， 体重：96-120 斤，建议尺码M。")
        result = size_matching.match_size_rule("我身高170cm，体重110斤", [rule])

        self.assertTrue(result["matched"])
        self.assertEqual(result["primary_size"], "M")

    def test_final_prompt_tells_model_not_to_recommend_conflicting_sizes(self):
        prompt = build_final_prompt(
            "我身高158，体重75kg，推荐什么尺码？",
            {"intent": INTENT_SIZE_RECOMMENDATION},
            {"used_history": {}},
            {
                "size_tool": {
                    "match_type": "measurement_conflict",
                    "recommended_size": None,
                    "alternative": None,
                    "reason": "当前尺码表无法给出单一可靠尺码。",
                }
            },
        )

        self.assertIn("measurement_conflict", prompt)
        self.assertIn("不要输出两个跨度很大的尺码作为推荐", prompt)

    def test_no_policy_source_result_is_explicit_fallback(self):
        rag_result = {
            "retrieval_query": "可以退货吗？。退换货政策。",
            "retrieved_chunks": [],
        }

        result = build_no_policy_source_result("可以退货吗？", rag_result)

        self.assertFalse(result["has_policy_source"])
        self.assertIn("当前知识库没有退换货", result["policy_answer"])


if __name__ == "__main__":
    unittest.main()
