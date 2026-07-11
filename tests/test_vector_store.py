import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from clothing_assistant.infrastructure import vector_store
from clothing_assistant.infrastructure.knowledge_base import build_knowledge_chunks


@contextmanager
def temporary_vector_store_paths(temp_dir):
    temp_path = Path(temp_dir)
    with patch.object(vector_store, "VECTOR_STORE_FILE", temp_path / "vectors.json"), patch.object(
        vector_store,
        "VECTOR_STORE_META_FILE",
        temp_path / "meta.json",
    ):
        yield


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class VectorStoreStatusTests(unittest.TestCase):
    def get_status(self):
        status_loader = getattr(vector_store, "get_vector_store_status", None)
        self.assertIsNotNone(status_loader)
        return status_loader()

    def test_missing_vector_store_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir, temporary_vector_store_paths(temp_dir):
            status = self.get_status()

        self.assertEqual(status["ready"], False)
        self.assertEqual(status["reason"], "missing_vector_store")

    def test_missing_meta_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir, temporary_vector_store_paths(temp_dir):
            write_json(vector_store.VECTOR_STORE_FILE, [])
            status = self.get_status()

        self.assertEqual(status["ready"], False)
        self.assertEqual(status["reason"], "missing_vector_store_meta")

    def test_broken_meta_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir, temporary_vector_store_paths(temp_dir):
            write_json(vector_store.VECTOR_STORE_FILE, [])
            vector_store.VECTOR_STORE_META_FILE.write_text("{broken", encoding="utf-8")
            status = self.get_status()

        self.assertEqual(status["ready"], False)
        self.assertEqual(status["reason"], "invalid_vector_store_meta")

    def test_broken_vector_store_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir, temporary_vector_store_paths(temp_dir):
            vector_store.VECTOR_STORE_FILE.write_text("[broken", encoding="utf-8")
            write_json(vector_store.VECTOR_STORE_META_FILE, {"chunk_count": 0})
            status = self.get_status()

        self.assertEqual(status["ready"], False)
        self.assertEqual(status["reason"], "invalid_vector_store")

    def test_chunk_count_mismatch_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir, temporary_vector_store_paths(temp_dir):
            write_json(vector_store.VECTOR_STORE_FILE, [{"chunk_id": "one"}])
            write_json(vector_store.VECTOR_STORE_META_FILE, {"chunk_count": 2})
            status = self.get_status()

        self.assertEqual(status["ready"], False)
        self.assertEqual(status["reason"], "chunk_count_mismatch")

    def test_changed_source_files_are_not_ready(self):
        knowledge_docs = [
            {
                "file_name": "测试知识.txt",
                "file_path": "/missing/test.txt",
                "content": "新知识",
            }
        ]
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            temporary_vector_store_paths(temp_dir),
            patch.object(vector_store, "load_knowledge_files", return_value=knowledge_docs),
        ):
            write_json(vector_store.VECTOR_STORE_FILE, [{"chunk_id": "one"}])
            write_json(
                vector_store.VECTOR_STORE_META_FILE,
                {
                    "chunk_count": 1,
                    "source_files": [{"file_name": "测试知识.txt", "sha256": "old"}],
                },
            )
            status = self.get_status()

        self.assertEqual(status["ready"], False)
        self.assertEqual(status["reason"], "source_files_changed")

    def test_matching_store_meta_and_sources_are_ready(self):
        knowledge_docs = [
            {
                "file_name": "测试知识.txt",
                "file_path": "/missing/test.txt",
                "content": "第一条\n第二条",
            }
        ]
        chunks = build_knowledge_chunks(knowledge_docs)
        source_files = vector_store.build_source_file_meta(chunks)
        meta = {
            "version": "test-version",
            "built_at": "2026-07-10T00:00:00+00:00",
            "chunk_count": 2,
            "source_files": source_files,
        }

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            temporary_vector_store_paths(temp_dir),
            patch.object(vector_store, "load_knowledge_files", return_value=knowledge_docs),
        ):
            write_json(
                vector_store.VECTOR_STORE_FILE,
                [{"chunk_id": "one"}, {"chunk_id": "two"}],
            )
            write_json(vector_store.VECTOR_STORE_META_FILE, meta)
            status = self.get_status()

        self.assertEqual(
            status,
            {
                "ready": True,
                "reason": "ready",
                "chunk_count": 2,
                "version": "test-version",
                "built_at": "2026-07-10T00:00:00+00:00",
            },
        )


if __name__ == "__main__":
    unittest.main()
