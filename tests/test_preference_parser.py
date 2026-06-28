import unittest

from clothing_assistant.application.preference_parser import parse_preferences, sanitize_llm_preferences


class PreferenceParserTests(unittest.TestCase):
    def test_parse_student_budget_and_visual_goals(self):
        preferences = parse_preferences("学生党想要平价百搭，显高显瘦，预算500以内")

        self.assertIn("student", preferences["persona_tags"])
        self.assertIn("taller", preferences["visual_goals"])
        self.assertIn("slimmer", preferences["visual_goals"])
        self.assertIn("basic", preferences["style_tags"])
        self.assertEqual(preferences["price_preference"], "budget")
        self.assertEqual(preferences["budget_max"], 500)
        self.assertGreater(preferences["confidence"], 0.5)

    def test_parse_synonym_signals_without_exact_shortcut_words(self):
        preferences = parse_preferences("适合大学生日常上课，别太贵，看起来显腿长一点，还要遮肉")

        self.assertIn("student", preferences["persona_tags"])
        self.assertIn("campus", preferences["scene"])
        self.assertIn("taller", preferences["visual_goals"])
        self.assertIn("slimmer", preferences["visual_goals"])
        self.assertEqual(preferences["price_preference"], "budget")

    def test_low_confidence_llm_mapping_keeps_rule_fallback(self):
        preferences = parse_preferences(
            "大学生日常上课穿，预算有限",
            {
                "style_tags": ["date"],
                "confidence": 0.2,
            },
        )

        self.assertIn("student", preferences["persona_tags"])
        self.assertIn("basic", preferences["style_tags"])
        self.assertNotIn("date", preferences["style_tags"])
        self.assertEqual(preferences["price_preference"], "budget")

    def test_sanitize_llm_preferences_keeps_only_allowed_tags(self):
        preferences = sanitize_llm_preferences(
            {
                "style_tags": ["minimal", "made_up_tag"],
                "visual_goals": ["slimmer", "fake_goal"],
                "budget_max": 399.9,
                "confidence": 1.5,
            }
        )

        self.assertEqual(preferences["style_tags"], ["minimal"])
        self.assertEqual(preferences["visual_goals"], ["slimmer"])
        self.assertEqual(preferences["budget_max"], 399)
        self.assertEqual(preferences["confidence"], 1.0)

    def test_invalid_llm_json_falls_back_to_empty_preferences(self):
        preferences = sanitize_llm_preferences("{not-json")

        self.assertEqual(preferences["style_tags"], [])
        self.assertIsNone(preferences["budget_max"])

    def test_parse_preferences_merges_safe_llm_mapping(self):
        preferences = parse_preferences(
            "想要约会穿搭",
            {
                "style_tags": ["minimal", "made_up"],
                "visual_goals": ["slimmer"],
                "preferred_colors": ["黑色"],
                "budget_max": 450,
                "confidence": 0.8,
            },
        )

        self.assertIn("date", preferences["style_tags"])
        self.assertIn("minimal", preferences["style_tags"])
        self.assertIn("slimmer", preferences["visual_goals"])
        self.assertEqual(preferences["preferred_colors"], ["黑色"])
        self.assertEqual(preferences["budget_max"], 450)


if __name__ == "__main__":
    unittest.main()
