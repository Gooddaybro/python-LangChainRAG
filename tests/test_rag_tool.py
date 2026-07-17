import unittest
from unittest.mock import patch

import httpx

from clothing_assistant.tools.rag_tool import run_rag_tool, simplify_chunk


class RagToolTests(unittest.TestCase):
    def test_simplify_chunk_keeps_knowledge_domain(self):
        chunk = {
            "chunk_id": "材质知识.txt-001",
            "file_name": "材质知识.txt",
            "content": "聚酯纤维耐皱。",
            "score": 0.2,
            "domain": "material",
        }

        simplified = simplify_chunk(chunk)

        self.assertEqual(simplified["domain"], "material")

    def test_missing_vector_store_degrades_to_empty_sources(self):
        with patch(
            "clothing_assistant.tools.rag_tool.search_similar_chunks",
            side_effect=FileNotFoundError("vector store missing"),
        ):
            result = run_rag_tool("推荐一件通勤外套", query_type="recommendation")

        self.assertEqual(result["retrieved_chunks"], [])
        self.assertEqual(result["source_count"], 0)
        self.assertIn("导购推荐", result["retrieval_query"])

    def test_rag_tool_includes_vector_store_meta_when_available(self):
        with patch(
            "clothing_assistant.tools.rag_tool.search_similar_chunks",
            return_value=[],
        ), patch(
            "clothing_assistant.tools.rag_tool.load_vector_store_meta",
            return_value={"version": "2026-07-03T18:30:00+08:00", "chunk_count": 12},
        ):
            result = run_rag_tool("推荐一件通勤外套", query_type="recommendation")

        self.assertEqual(result["rag_meta"]["version"], "2026-07-03T18:30:00+08:00")
        self.assertEqual(result["rag_meta"]["chunk_count"], 12)

    def test_rag_tool_ignores_broken_vector_store_meta(self):
        with patch(
            "clothing_assistant.tools.rag_tool.search_similar_chunks",
            return_value=[],
        ), patch(
            "clothing_assistant.tools.rag_tool.load_vector_store_meta",
            side_effect=ValueError("broken meta"),
        ):
            result = run_rag_tool("推荐一件通勤外套", query_type="recommendation")

        self.assertEqual(result["retrieved_chunks"], [])
        self.assertEqual(result["source_count"], 0)
        self.assertEqual(result["rag_meta"], {})

    def test_recoverable_rag_failures_degrade_with_safe_reason(self):
        request = httpx.Request("POST", "https://example.test/embeddings")
        cases = (
            (httpx.ReadTimeout("private timeout", request=request), "timeout"),
            (httpx.ConnectError("private connection", request=request), "connection_error"),
            (
                httpx.HTTPStatusError(
                    "private rate limit",
                    request=request,
                    response=httpx.Response(429, request=request),
                ),
                "rate_limited",
            ),
            (
                httpx.HTTPStatusError(
                    "private upstream failure",
                    request=request,
                    response=httpx.Response(503, request=request),
                ),
                "upstream_5xx",
            ),
        )

        for error, reason in cases:
            with self.subTest(reason=reason), patch(
                "clothing_assistant.tools.rag_tool.search_similar_chunks",
                side_effect=error,
            ):
                result = run_rag_tool("通勤穿什么颜色？")

            self.assertEqual(result["retrieved_chunks"], [])
            self.assertEqual(result["source_count"], 0)
            self.assertEqual(result["rag_meta"]["degraded_reason"], reason)

    def test_rag_tool_does_not_swallow_programming_errors(self):
        with patch(
            "clothing_assistant.tools.rag_tool.search_similar_chunks",
            side_effect=TypeError("programming error"),
        ):
            with self.assertRaisesRegex(TypeError, "programming error"):
                run_rag_tool("通勤穿什么颜色？")


if __name__ == "__main__":
    unittest.main()
