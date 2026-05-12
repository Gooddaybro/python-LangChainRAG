import unittest

from clothing_rag_demo.agent.eval_cases import EVAL_CASES
from clothing_rag_demo.agent.eval_report import build_eval_report, format_markdown_report


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


if __name__ == "__main__":
    unittest.main()
