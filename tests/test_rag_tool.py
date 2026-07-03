import unittest
from unittest.mock import patch

from clothing_assistant.tools.rag_tool import run_rag_tool


class RagToolTests(unittest.TestCase):
    def test_missing_vector_store_degrades_to_empty_sources(self):
        with patch(
            "clothing_assistant.tools.rag_tool.search_similar_chunks",
            side_effect=FileNotFoundError("vector store missing"),
        ):
            result = run_rag_tool("推荐一件通勤外套", query_type="recommendation")

        self.assertEqual(result["retrieved_chunks"], [])
        self.assertEqual(result["source_count"], 0)
        self.assertIn("导购推荐", result["retrieval_query"])


if __name__ == "__main__":
    unittest.main()
