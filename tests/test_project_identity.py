import json
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

    def test_readme_documents_langgraph_as_main_chat_entrypoint(self):
        readme_text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("`POST /chat`：调用 LangGraph 主线", readme_text)
        self.assertIn("`POST /chat/pipeline`：调用旧手写 pipeline", readme_text)
        self.assertIn("`POST /chat/langgraph`：兼容路径，同样调用 LangGraph 主线", readme_text)
        self.assertIn("当前主线入口是 `clothing_rag_demo.agent.langgraph_executor.run_langgraph_agent`", readme_text)
        self.assertIn("旧手写 pipeline 保留为 `clothing_rag_demo.agent.agent_executor.run_agent`", readme_text)
        self.assertNotIn("当前主线入口仍是 `clothing_rag_demo.agent.agent_executor.run_agent`", readme_text)
        self.assertNotIn("LangGraph shadow", readme_text)

    def test_langgraph_json_declares_main_graph(self):
        config_path = Path("langgraph.json")

        self.assertTrue(config_path.exists())
        config = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertIn("./clothing_rag_demo", config["dependencies"])
        self.assertEqual(
            config["graphs"]["clothing_assistant"],
            "./clothing_rag_demo/agent/langgraph_executor.py:get_default_langgraph_agent",
        )
        self.assertEqual(config["env"], "./.env")

    def test_streamlit_workbench_hero_uses_project_display_name(self):
        hero_html = build_page_hero_html()

        self.assertIn(PROJECT_DISPLAY_NAME, hero_html)
        self.assertIn("本地调试控制台", hero_html)


if __name__ == "__main__":
    unittest.main()
