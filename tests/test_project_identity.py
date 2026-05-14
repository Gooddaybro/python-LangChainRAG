import unittest
from pathlib import Path

from clothing_rag_demo.api.app import app
from clothing_rag_demo.app_qa import build_page_hero_html
from clothing_rag_demo.config_data import PROJECT_API_TITLE, PROJECT_DISPLAY_NAME


class ProjectIdentityTests(unittest.TestCase):
    def test_project_display_name_constant(self):
        self.assertEqual(PROJECT_DISPLAY_NAME, "AI Clothing Shopping Assistant System")

    def test_fastapi_uses_project_api_title(self):
        self.assertEqual(PROJECT_API_TITLE, "AI Clothing Shopping Assistant System API")
        self.assertEqual(app.title, PROJECT_API_TITLE)

    def test_readme_uses_project_display_name_as_title(self):
        readme_text = Path("README.md").read_text(encoding="utf-8")

        self.assertTrue(readme_text.startswith(f"# {PROJECT_DISPLAY_NAME}"))

    def test_streamlit_workbench_hero_uses_project_display_name(self):
        hero_html = build_page_hero_html()

        self.assertIn(PROJECT_DISPLAY_NAME, hero_html)
        self.assertIn("本地调试控制台", hero_html)


if __name__ == "__main__":
    unittest.main()
