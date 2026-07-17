import unittest

from clothing_assistant.infrastructure.knowledge_base import (
    build_knowledge_chunks,
    split_numbered_sections_into_chunks,
)


class KnowledgeBaseTests(unittest.TestCase):
    def test_numbered_sections_keep_title_and_body_together(self):
        text = "1. 通勤\n基础色更稳妥。\n2. 校园\n休闲基础款更实用。"

        self.assertEqual(
            split_numbered_sections_into_chunks(text),
            ["1. 通勤\n基础色更稳妥。", "2. 校园\n休闲基础款更实用。"],
        )

    def test_chunks_include_domain_metadata(self):
        docs = [
            {
                "file_name": "场景穿搭.txt",
                "file_path": "/tmp/scene.txt",
                "content": "1. 通勤\n选择简洁基础款。",
            }
        ]

        chunks = build_knowledge_chunks(docs)

        self.assertEqual(chunks[0]["domain"], "scene")


if __name__ == "__main__":
    unittest.main()
