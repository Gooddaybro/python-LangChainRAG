import unittest

from clothing_assistant.agent.router import intent_router
from clothing_assistant.agent.langgraph_executor import run_langgraph_agent
from clothing_assistant.application.recommendation_service import build_product_refs
from clothing_assistant.tools.size_tool import normalize_measurement_query, run_size_tool


class RecommendationServiceTests(unittest.TestCase):
    def test_bare_height_weight_pair_is_routed_as_size_signal(self):
        result = intent_router("明天面试想要显瘦 177 130 该怎么选")

        self.assertEqual(result["intent"], "size_recommendation")
        self.assertIn("身高体重", result["reason"])

    def test_bare_height_weight_pair_is_normalized_for_size_tool(self):
        normalized = normalize_measurement_query("明天面试想要显瘦 177 130 该怎么选")

        self.assertIn("身高177cm", normalized)
        self.assertIn("体重130斤", normalized)

        result = run_size_tool("明天面试想要显瘦 177 130 该怎么选")

        self.assertEqual(result["recommended_size"], "XL")
        self.assertEqual(result["measurements"]["height_cm"], 177.0)
        self.assertEqual(result["measurements"]["weight_jin"], 130.0)

    def test_height_with_kg_pair_overrides_previous_measurements(self):
        history = [
            {
                "user_query": "177 130 怎么穿？",
                "assistant_answer": "建议优先看 XL 码。",
            }
        ]

        normalized = normalize_measurement_query("160 60kg呢？")
        self.assertIn("身高160cm", normalized)
        self.assertIn("体重60kg", normalized)

        result = run_size_tool("160 60kg呢？", chat_history=history)

        self.assertEqual(result["recommended_size"], "M")
        self.assertEqual(result["measurements"]["height_cm"], 160.0)
        self.assertEqual(result["measurements"]["weight_jin"], 120.0)

    def test_partial_weight_question_only_fills_missing_height_from_history(self):
        history = [
            {
                "user_query": "177 130 怎么穿？",
                "assistant_answer": "建议优先看 XL 码。",
            }
        ]

        result = run_size_tool("60kg呢？", chat_history=history)

        self.assertEqual(result["measurements"]["height_cm"], 177.0)
        self.assertEqual(result["measurements"]["weight_jin"], 120.0)

    def test_same_thread_does_not_reuse_previous_size_state(self):
        thread_id = "size-switch-thread"
        first = run_langgraph_agent(
            "177 130 怎么穿？",
            thread_id=thread_id,
            request_id="req-size-switch-1",
            session_id="session-size-switch",
        )
        second = run_langgraph_agent(
            "160 60kg呢？",
            chat_history=[
                {
                    "user_query": "177 130 怎么穿？",
                    "assistant_answer": first["answer"],
                }
            ],
            thread_id=thread_id,
            request_id="req-size-switch-2",
            session_id="session-size-switch",
        )

        size_result = second["debug"]["tool_results"]["size_tool"]
        self.assertEqual(size_result["recommended_size"], "M")
        self.assertEqual(size_result["measurements"]["height_cm"], 160.0)
        self.assertEqual(size_result["measurements"]["weight_jin"], 120.0)

    def test_build_product_refs_selects_only_java_candidates_matching_size(self):
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "面试通勤西装外套",
                "category": "外套",
                "size": "XL",
                "stock_status": "in_stock",
                "style_tags": ["通勤", "显瘦"],
                "sale_price": 399,
            },
            {
                "spu_id": 1002,
                "sku_id": 2002,
                "name": "日常休闲衬衫",
                "category": "衬衫",
                "size": "M",
                "stock_status": "in_stock",
                "style_tags": ["日常"],
                "sale_price": 199,
            },
        ]

        refs = build_product_refs(
            candidates,
            {"intent": "size_recommendation"},
            "明天面试想要显瘦 177 130 该怎么选",
            {},
            {"size_tool": {"recommended_size": "XL"}},
        )

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["spu_id"], 1001)
        self.assertEqual(refs[0]["sku_id"], 2001)
        self.assertIn("XL 码匹配", refs[0]["reason"])

    def test_build_product_refs_uses_alternative_size_after_primary_size(self):
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "基础款纯棉T恤",
                "category": "T恤",
                "size": "L",
                "stock_status": "in_stock",
                "style_tags": ["日常"],
                "sale_price": 99,
            },
            {
                "spu_id": 1002,
                "sku_id": 2002,
                "name": "修身短袖T恤",
                "category": "T恤",
                "size": "M",
                "stock_status": "in_stock",
                "style_tags": ["日常"],
                "sale_price": 109,
            },
        ]

        refs = build_product_refs(
            candidates,
            {"intent": "size_recommendation"},
            "160 60kg呢？",
            {},
            {"size_tool": {"recommended_size": "M", "alternative": "L"}},
        )

        self.assertEqual([ref["spu_id"] for ref in refs], [1002, 1001])
        self.assertIn("M 码匹配", refs[0]["reason"])
        self.assertIn("L 码是当前尺码建议的备选范围", refs[1]["reason"])

    def test_build_product_refs_does_not_recommend_for_chat_intent(self):
        refs = build_product_refs(
            [{"spu_id": 1001, "sku_id": 2001, "name": "通勤外套"}],
            {"intent": "chat"},
            "你是谁？",
            {},
            {},
        )

        self.assertEqual(refs, [])

    def test_build_product_refs_skips_invalid_and_duplicate_candidate_ids(self):
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "通勤轻薄外套",
                "category": "外套",
                "stock_status": "in_stock",
                "style_tags": ["通勤"],
                "sale_price": 299,
            },
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "重复 SKU",
                "category": "外套",
                "stock_status": "in_stock",
                "style_tags": ["通勤"],
                "sale_price": 299,
            },
            {
                "spu_id": 1002,
                "name": "缺少 SKU 的候选",
                "category": "外套",
                "stock_status": "in_stock",
                "style_tags": ["通勤"],
                "sale_price": 199,
            },
        ]

        refs = build_product_refs(
            candidates,
            {"intent": "recommendation"},
            "推荐一件通勤外套",
            {},
            {},
        )

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["spu_id"], 1001)
        self.assertEqual(refs[0]["sku_id"], 2001)

    def test_build_product_refs_explains_budget_color_and_scene_matches(self):
        candidates = [
            {
                "spu_id": 1002,
                "sku_id": 2101,
                "name": "通勤轻薄外套",
                "category": "外套",
                "color": "黑色",
                "stock_status": "in_stock",
                "season": ["autumn"],
                "style_tags": ["commute"],
                "sale_price": 299,
            }
        ]

        refs = build_product_refs(
            candidates,
            {"intent": "recommendation"},
            "秋季通勤，想要黑色外套",
            {"budget_max": 300, "preferred_colors": ["黑色"]},
            {},
        )

        self.assertEqual(len(refs), 1)
        reason = refs[0]["reason"]
        self.assertIn("当前候选显示有库存", reason)
        self.assertIn("风格、季节或场景标签匹配", reason)
        self.assertIn("价格 299 在预算 300 内", reason)
        self.assertIn("黑色匹配颜色偏好", reason)

    def test_fuzzy_student_budget_query_prefers_matching_candidate(self):
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "基础百搭卫衣",
                "category": "卫衣",
                "color": "黑色",
                "stock_status": "in_stock",
                "style_tags": ["casual", "basic"],
                "sale_price": 199,
            },
            {
                "spu_id": 1002,
                "sku_id": 2002,
                "name": "正式商务西装",
                "category": "西装",
                "color": "黑色",
                "stock_status": "in_stock",
                "style_tags": ["formal"],
                "sale_price": 899,
            },
        ]

        refs = build_product_refs(
            candidates,
            {"intent": "recommendation"},
            "学生党想要平价百搭，预算500以内",
            {},
            {},
        )

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["spu_id"], 1001)
        self.assertIn("风格、季节或场景标签匹配", refs[0]["reason"])
        self.assertIn("价格 199 在预算 500 内", refs[0]["reason"])
        self.assertIn("符合平价优先", refs[0]["reason"])

    def test_router_treats_fuzzy_profile_as_recommendation(self):
        result = intent_router("学生党平价百搭")

        self.assertEqual(result["intent"], "recommendation")

    def test_router_treats_synonym_profile_as_recommendation(self):
        result = intent_router("大学生日常上课，别太贵，还要遮肉显腿长")

        self.assertEqual(result["intent"], "recommendation")

    def test_visual_goal_uses_java_attribute_tags(self):
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "中高腰直筒牛仔裤",
                "category": "牛仔裤",
                "color": "黑色",
                "stock_status": "in_stock",
                "style_tags": ["casual"],
                "attribute_tags": ["下装版型:直筒", "腰线:中高腰"],
                "sale_price": 259,
            },
            {
                "spu_id": 1002,
                "sku_id": 2002,
                "name": "宽松低腰休闲裤",
                "category": "休闲裤",
                "color": "米色",
                "stock_status": "in_stock",
                "style_tags": ["casual"],
                "attribute_tags": ["下装版型:宽松", "腰线:低腰"],
                "sale_price": 229,
            },
        ]

        refs = build_product_refs(
            candidates,
            {"intent": "recommendation"},
            "想要显高显瘦的裤子",
            {},
            {},
        )

        self.assertEqual(refs[0]["spu_id"], 1001)
        self.assertIn("版型或腰线更利于拉长比例", refs[0]["reason"])
        self.assertIn("颜色、线条或版型更贴合显瘦需求", refs[0]["reason"])

    def test_synonym_profile_scores_student_and_visual_reasons(self):
        candidates = [
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "name": "黑色中高腰直筒裤",
                "category": "裤子",
                "color": "黑色",
                "stock_status": "in_stock",
                "style_tags": ["casual", "basic"],
                "attribute_tags": ["腰线:中高腰", "下装版型:直筒"],
                "sale_price": 199,
            },
            {
                "spu_id": 1002,
                "sku_id": 2002,
                "name": "米色低腰宽松裤",
                "category": "裤子",
                "color": "米色",
                "stock_status": "in_stock",
                "style_tags": ["formal"],
                "attribute_tags": ["腰线:低腰", "版型:过度宽松"],
                "sale_price": 299,
            },
        ]

        refs = build_product_refs(
            candidates,
            {"intent": "recommendation"},
            "适合大学生日常上课，别太贵，看起来显腿长一点，还要遮肉",
            {},
            {},
        )

        self.assertEqual(refs[0]["spu_id"], 1001)
        self.assertIn("价格和风格更适合学生日常穿搭", refs[0]["reason"])
        self.assertIn("版型或腰线更利于拉长比例", refs[0]["reason"])
        self.assertIn("颜色、线条或版型更贴合显瘦需求", refs[0]["reason"])


if __name__ == "__main__":
    unittest.main()
