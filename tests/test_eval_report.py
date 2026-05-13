import json
import tempfile
import unittest
from pathlib import Path

from clothing_rag_demo.agent.eval_cases import EVAL_CASES
from clothing_rag_demo.agent.eval_report import (
    build_eval_report,
    format_json_report,
    format_markdown_report,
    write_report,
)


class EvalReportTests(unittest.TestCase):
    def test_build_eval_report_compares_pipeline_and_langgraph(self):
        report = build_eval_report()
        summary = report["summary"]
        executors = {row["executor"] for row in report["rows"]}

        self.assertEqual(summary["case_count"], len(EVAL_CASES))
        self.assertEqual(summary["executor_count"], 2)
        self.assertEqual(summary["row_count"], len(EVAL_CASES) * 2)
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(summary["inconsistent_case_count"], 0)
        self.assertEqual(executors, {"pipeline", "langgraph"})

    def test_format_markdown_report_contains_result_and_consistency_tables(self):
        report = build_eval_report()

        markdown = format_markdown_report(report)

        self.assertIn("Executor Results", markdown)
        self.assertIn("Executor Consistency", markdown)
        self.assertIn("pipeline", markdown)
        self.assertIn("langgraph", markdown)

    def test_format_json_report_is_parseable_and_keeps_chinese(self):
        report = {
            "summary": {"case_count": 1},
            "rows": [{"case": "中文_case"}],
            "consistency_rows": [],
        }

        json_text = format_json_report(report)
        parsed = json.loads(json_text)

        self.assertEqual(parsed["rows"][0]["case"], "中文_case")
        self.assertIn("中文_case", json_text)

    def test_write_report_creates_markdown_output_parent_directory(self):
        report = build_eval_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "eval-report.md"

            written_path = write_report(report, "markdown", output_path)

            self.assertEqual(written_path, output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("# Agent Eval Report", output_path.read_text(encoding="utf-8"))

    def test_write_report_creates_json_output(self):
        report = {
            "summary": {"case_count": 1},
            "rows": [{"case": "中文_case"}],
            "consistency_rows": [],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "eval-report.json"

            write_report(report, "json", output_path)

            parsed = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["rows"][0]["case"], "中文_case")


if __name__ == "__main__":
    unittest.main()
