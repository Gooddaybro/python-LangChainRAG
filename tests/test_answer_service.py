import unittest

from clothing_assistant.application.answer_service import build_outfit_advice_draft


def outfit_state(candidates):
    return {
        "user_query": "你好，我想要轻松一点的，我177 130，夏天怎么穿呢？男性",
        "intent_result": {
            "intent": "recommendation",
            "request_type": "OUTFIT_ADVICE",
            "requested_capabilities": ["OUTFIT_PLAN", "PRODUCT_SELECTION", "SIZE_GUIDANCE"],
        },
        "demand_intent": {
            "version": "demand-intent-v2",
            "requestType": "OUTFIT_ADVICE",
            "requestedCapabilities": ["OUTFIT_PLAN", "PRODUCT_SELECTION", "SIZE_GUIDANCE"],
            "targetGender": "male",
            "season": "summer",
            "style": ["casual"],
            "fitPreferences": ["relaxed"],
            "subjectMeasurements": {
                "heightCm": 177,
                "weightKg": 65,
                "originalText": "177 130",
                "normalizedFrom": "ASSUMED_JIN",
                "subject": "SELF",
            },
        },
        "candidates": candidates,
        "user_context": {},
        "tool_results": {"size_tool": {"recommended_size": "XL"}},
    }


class OutfitAnswerServiceTests(unittest.TestCase):
    def test_outfit_answer_uses_fixed_layers_and_only_real_matched_products(self):
        answer = build_outfit_advice_draft(
            outfit_state(
                [
                    {
                        "spu_id": 1001,
                        "sku_id": 2001,
                        "name": "夏季休闲T恤",
                        "season": ["summer"],
                        "style_tags": ["casual"],
                        "fit_type": "relaxed",
                        "size": "XL",
                        "sale_price": 139,
                        "stock_status": "in_stock",
                    }
                ]
            )
        )

        self.assertIn("需求确认", answer)
        self.assertIn("男性", answer)
        self.assertIn("177cm", answer)
        self.assertIn("65kg", answer)
        self.assertIn("130斤", answer)
        self.assertIn("搭配公式", answer)
        self.assertIn("版型、材质与颜色", answer)
        self.assertIn("可购买商品", answer)
        self.assertIn("夏季休闲T恤", answer)
        self.assertIn("139 元", answer)
        self.assertIn("尺码提示", answer)
        self.assertIn("XL", answer)
        self.assertIn("可选追问", answer)

    def test_outfit_answer_without_strong_match_keeps_plan_and_does_not_invent_product(self):
        answer = build_outfit_advice_draft(
            outfit_state(
                [
                    {
                        "spu_id": 1002,
                        "sku_id": 2002,
                        "name": "秋季正式西装",
                        "season": ["autumn"],
                        "style_tags": ["formal"],
                        "sale_price": 899,
                        "stock_status": "in_stock",
                    }
                ]
            )
        )

        self.assertIn("搭配公式", answer)
        self.assertIn("略宽松上衣 + 直筒下装", answer)
        self.assertIn("当前没有可归因的强匹配商品", answer)
        self.assertNotIn("秋季正式西装", answer)
        self.assertNotIn("推荐运动鞋", answer)


if __name__ == "__main__":
    unittest.main()
