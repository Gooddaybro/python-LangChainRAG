import json
import unittest
from pathlib import Path

from clothing_assistant.api.app import app
from clothing_assistant.file_history_store import load_chat_history
from clothing_assistant.infrastructure.file_history_store import load_chat_history as load_infra_chat_history
from clothing_assistant.infrastructure.knowledge_base import build_knowledge_chunks as build_infra_knowledge_chunks
from clothing_assistant.infrastructure.vector_store import search_similar_chunks as search_infra_similar_chunks
from clothing_assistant.knowledge_base import build_knowledge_chunks
from clothing_assistant.app_qa import build_page_hero_html
from clothing_assistant.ui.app_qa import build_page_hero_html as build_ui_page_hero_html
from clothing_assistant.config_data import PROJECT_API_TITLE, PROJECT_DISPLAY_NAME
from clothing_assistant.vector_stores import search_similar_chunks


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
        self.assertIn("当前主线入口是 `clothing_assistant.agent.langgraph_executor.run_langgraph_agent`", readme_text)
        self.assertIn("旧手写 pipeline 保留为 `clothing_assistant.agent.agent_executor.run_agent`", readme_text)
        self.assertNotIn("当前主线入口仍是 `clothing_assistant.agent.agent_executor.run_agent`", readme_text)
        self.assertNotIn("LangGraph shadow", readme_text)

    def test_langgraph_json_declares_main_graph(self):
        config_path = Path("langgraph.json")

        self.assertTrue(config_path.exists())
        config = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertIn("./clothing_assistant", config["dependencies"])
        self.assertEqual(
            config["graphs"]["clothing_assistant"],
            "./clothing_assistant/agent/langgraph_executor.py:get_default_langgraph_agent",
        )
        self.assertEqual(config["env"], "./.env")

    def test_streamlit_workbench_hero_uses_project_display_name(self):
        hero_html = build_page_hero_html()

        self.assertIn(PROJECT_DISPLAY_NAME, hero_html)
        self.assertIn("本地调试控制台", hero_html)

    def test_streamlit_workbench_has_ui_module_and_legacy_wrapper(self):
        self.assertIs(build_page_hero_html, build_ui_page_hero_html)

    def test_infrastructure_modules_have_legacy_wrappers(self):
        self.assertIs(build_knowledge_chunks, build_infra_knowledge_chunks)
        self.assertIs(search_similar_chunks, search_infra_similar_chunks)
        self.assertIs(load_chat_history, load_infra_chat_history)


if __name__ == "__main__":
    unittest.main()
