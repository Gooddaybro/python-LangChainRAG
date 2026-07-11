import json
import tempfile
import unittest
from pathlib import Path

from clothing_assistant.agent.answer_quality_cases import ANSWER_QUALITY_CASES
from clothing_assistant.agent.answer_quality_report import (
    build_answer_quality_report,
    format_json_report,
    format_markdown_report,
    score_answer,
    write_report,
)
from clothing_assistant.application.answer_service import append_rag_sources, format_rag_sources


class AnswerQualityReportTests(unittest.TestCase):
    def test_format_rag_sources_keeps_each_source_once(self):
        chunks = [
            {"file_name": "颜色选择.txt", "chunk_id": "颜色选择.txt-001"},
            {"file_name": "颜色选择.txt", "chunk_id": "颜色选择.txt-001"},
            {"file_name": "场景穿搭.txt", "chunk_id": "场景穿搭.txt-002"},
        ]

        sources = format_rag_sources(chunks)

        self.assertEqual(
            sources,
            "颜色选择.txt（颜色选择.txt-001）、场景穿搭.txt（场景穿搭.txt-002）",
        )

    def test_append_rag_sources_keeps_answer_unchanged_without_accepted_chunks(self):
        answer = "当前知识库没有检索到足够可靠的资料。"

        cited_answer = append_rag_sources(answer, [])

        self.assertEqual(cited_answer, answer)

    def test_score_answer_passes_when_text_and_debug_match(self):
        case = {
            "must_include": ["基础款纯棉T恤", "99"],
            "must_not_include": ["大约"],
            "expected_grounding": "structured_lookup",
            "expected_stop_reason": "final_answer",
            "max_answer_length": 50,
        }
        debug = {
            "selected_tools": ["structured_lookup"],
            "stop_reason": "final_answer",
        }

        score = score_answer("基础款纯棉T恤的价格是 99 元。", debug, case)

        self.assertTrue(score["passed"])
        self.assertEqual(score["failures"], [])

    def test_score_answer_reports_missing_required_text(self):
        case = {
            "must_include": ["黑色", "L", "8"],
            "expected_grounding": "structured_lookup",
            "expected_stop_reason": "final_answer",
        }
        debug = {
            "selected_tools": ["structured_lookup"],
            "stop_reason": "final_answer",
        }

        score = score_answer("基础款纯棉T恤有货。", debug, case)

        self.assertFalse(score["passed"])
        self.assertIn("missing_required_text", [failure["reason"] for failure in score["failures"]])

    def test_score_answer_reports_forbidden_text_and_debug_leak(self):
        case = {
            "must_include": ["通勤"],
            "must_not_include": ["trace_events"],
            "expected_grounding": "rag_tool",
            "expected_stop_reason": "final_answer",
        }
        debug = {
            "selected_tools": ["rag_tool"],
            "stop_reason": "final_answer",
        }

        score = score_answer("通勤建议如下：trace_events=[]", debug, case)
        reasons = [failure["reason"] for failure in score["failures"]]

        self.assertFalse(score["passed"])
        self.assertIn("contains_forbidden_text", reasons)
        self.assertIn("debug_leak", reasons)

    def test_score_answer_reports_unexpected_stop_reason(self):
        case = {
            "expected_grounding": "structured_lookup",
            "expected_stop_reason": "missing_info",
        }
        debug = {
            "selected_tools": ["structured_lookup"],
            "stop_reason": "final_answer",
        }

        score = score_answer("请补充颜色。", debug, case)

        self.assertFalse(score["passed"])
        self.assertIn("unexpected_stop_reason", [failure["reason"] for failure in score["failures"]])

    def test_default_answer_quality_report_passes_core_cases(self):
        report = build_answer_quality_report()

        self.assertEqual(report["summary"]["case_count"], len(ANSWER_QUALITY_CASES))
        self.assertEqual(report["summary"]["failed_count"], 0)
        self.assertEqual(report["summary"]["pass_count"], len(ANSWER_QUALITY_CASES))

    def test_format_markdown_report_contains_summary_and_rows(self):
        report = build_answer_quality_report()

        markdown = format_markdown_report(report)

        self.assertIn("# Answer Quality Report", markdown)
        self.assertIn("inventory_answer_mentions_exact_stock", markdown)
        self.assertIn("PASS", markdown)

    def test_format_json_report_is_parseable_and_keeps_chinese(self):
        report = {
            "summary": {"case_count": 1, "pass_count": 1, "failed_count": 0},
            "rows": [{"case": "中文_case", "passed": True}],
        }

        json_text = format_json_report(report)
        parsed = json.loads(json_text)

        self.assertEqual(parsed["rows"][0]["case"], "中文_case")
        self.assertIn("中文_case", json_text)

    def test_write_report_creates_parent_directory(self):
        report = build_answer_quality_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "answer-quality.md"

            written_path = write_report(report, "markdown", output_path)

            self.assertEqual(written_path, output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("# Answer Quality Report", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
