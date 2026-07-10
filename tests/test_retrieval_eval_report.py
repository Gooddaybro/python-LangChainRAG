import json
import tempfile
import unittest
from pathlib import Path

from clothing_assistant import config_data
from clothing_assistant.agent import retrieval_eval_report as report_module


def fake_retriever(query, top_k=3, query_type=None):
    if "防火服" in query:
        chunks = [
            {
                "file_name": "颜色选择.txt",
                "chunk_id": "color-1",
                "content": "通勤颜色",
                "score": 0.91,
            }
        ]
    else:
        chunks = [
            {
                "file_name": "洗涤养护.txt",
                "chunk_id": "care-1",
                "content": "纯棉建议30℃以下洗涤",
                "score": 0.12,
            }
        ]
    return {
        "retrieved_chunks": chunks[:top_k],
        "retrieval_query": query,
        "rag_meta": {},
    }


class RetrievalEvalReportTests(unittest.TestCase):
    def test_runtime_retrieval_defaults_are_explicit(self):
        self.assertEqual(getattr(config_data, "RAG_TOP_K", None), 3)
        self.assertEqual(getattr(config_data, "RAG_DISTANCE_THRESHOLD", None), 0.7)

    def test_positive_case_passes_when_expected_chunk_is_accepted(self):
        case = {
            "name": "cotton",
            "query": "纯棉怎么洗",
            "query_type": "product",
            "expected_file_names": ["洗涤养护.txt"],
            "expected_keywords_any": ["纯棉"],
            "should_retrieve": True,
        }

        row = report_module.evaluate_retrieval_case(
            case,
            fake_retriever,
            top_k=3,
            threshold=0.7,
        )

        self.assertTrue(row["passed"])
        self.assertTrue(row["hit"])

    def test_negative_case_passes_when_all_chunks_are_above_threshold(self):
        case = {
            "name": "fireproof",
            "query": "防火服国家标准",
            "query_type": "product",
            "expected_file_names": [],
            "expected_keywords_any": [],
            "should_retrieve": False,
        }

        row = report_module.evaluate_retrieval_case(
            case,
            fake_retriever,
            top_k=3,
            threshold=0.7,
        )

        self.assertTrue(row["passed"])
        self.assertEqual(row["accepted_chunks"], [])

    def test_report_separates_hits_and_false_accepts(self):
        cases = [
            {
                "name": "cotton",
                "query": "纯棉怎么洗",
                "query_type": "product",
                "expected_file_names": ["洗涤养护.txt"],
                "expected_keywords_any": ["纯棉"],
                "should_retrieve": True,
            },
            {
                "name": "fireproof",
                "query": "防火服国家标准",
                "query_type": "product",
                "expected_file_names": [],
                "expected_keywords_any": [],
                "should_retrieve": False,
            },
        ]

        report = report_module.build_retrieval_eval_report(
            cases=cases,
            retriever=fake_retriever,
            top_k=3,
            threshold=0.7,
        )

        self.assertEqual(report["summary"]["positive_hit_count"], 1)
        self.assertEqual(report["summary"]["false_accept_count"], 0)

    def test_markdown_report_contains_summary_case_and_chunk(self):
        report = report_module.build_retrieval_eval_report(
            cases=[
                {
                    "name": "cotton",
                    "query": "纯棉怎么洗",
                    "query_type": "product",
                    "expected_file_names": ["洗涤养护.txt"],
                    "expected_keywords_any": ["纯棉"],
                    "should_retrieve": True,
                }
            ],
            retriever=fake_retriever,
        )

        markdown = report_module.format_markdown_report(report)

        self.assertIn("# RAG Retrieval Report", markdown)
        self.assertIn("cotton", markdown)
        self.assertIn("care-1", markdown)
        self.assertIn("PASS", markdown)

    def test_json_report_is_parseable_and_keeps_chinese(self):
        report = {
            "summary": {"case_count": 1},
            "rows": [{"case": "纯棉_case", "passed": True}],
        }

        json_text = report_module.format_json_report(report)

        self.assertEqual(json.loads(json_text)["rows"][0]["case"], "纯棉_case")

    def test_write_report_creates_parent_directory(self):
        report = {"summary": {"case_count": 0}, "rows": []}

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "retrieval.md"
            written_path = report_module.write_report(report, "markdown", output_path)

            self.assertEqual(written_path, output_path)
            self.assertTrue(output_path.exists())

    def test_arg_parser_accepts_retrieval_parameters(self):
        args = report_module.build_arg_parser().parse_args(
            ["--top-k", "5", "--threshold", "0.55", "--format", "json"]
        )

        self.assertEqual(args.top_k, 5)
        self.assertEqual(args.threshold, 0.55)
        self.assertEqual(args.format, "json")


if __name__ == "__main__":
    unittest.main()
