import unittest
from types import SimpleNamespace

from clothing_assistant.config_data import KNOWLEDGE_FILES
from clothing_assistant.infrastructure.knowledge_upload import (
    calculate_file_md5,
    compare_uploaded_files,
    validate_uploaded_files,
)


class KnowledgeUploadTests(unittest.TestCase):
    def test_validate_uploaded_files_accepts_the_configured_file_set(self):
        uploaded_files = [SimpleNamespace(name=file_name) for file_name in KNOWLEDGE_FILES]

        self.assertEqual(validate_uploaded_files(uploaded_files), [])

    def test_validate_uploaded_files_reports_duplicate_missing_and_unexpected_files(self):
        uploaded_files = [
            SimpleNamespace(name=KNOWLEDGE_FILES[0]),
            SimpleNamespace(name=KNOWLEDGE_FILES[0]),
            SimpleNamespace(name="未知知识.txt"),
        ]

        errors = validate_uploaded_files(uploaded_files)

        self.assertTrue(any("重复文件" in error for error in errors))
        self.assertTrue(any("缺少文件" in error for error in errors))
        self.assertTrue(any("未约定" in error for error in errors))

    def test_compare_uploaded_files_only_marks_changed_content(self):
        snapshots = [
            {"name": "场景穿搭.txt", "md5": "new-scene"},
            {"name": "材质知识.txt", "md5": "same-material"},
        ]
        hash_record = {
            "场景穿搭.txt": "old-scene",
            "材质知识.txt": "same-material",
        }

        changed, unchanged, updated_record = compare_uploaded_files(snapshots, hash_record)

        self.assertEqual(changed, ["场景穿搭.txt"])
        self.assertEqual(unchanged, ["材质知识.txt"])
        self.assertEqual(updated_record["场景穿搭.txt"], "new-scene")
        self.assertEqual(calculate_file_md5("knowledge".encode("utf-8")), calculate_file_md5(b"knowledge"))


if __name__ == "__main__":
    unittest.main()
