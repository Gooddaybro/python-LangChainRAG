import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from clothing_rag_demo.api.app import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_returns_ok(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    # /chat 现在走 LangGraph 主工作流
    def test_chat_calls_langgraph_executor(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with patch(
            "clothing_rag_demo.api.app.run_langgraph_agent",
            return_value=fake_result,
        ) as mock_run:
            response = self.client.post(
                "/chat",
                json={
                    "query": "我 175cm 70kg 穿什么码？",
                    "chat_history": [],
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fake_result)
        mock_run.assert_called_once_with("我 175cm 70kg 穿什么码？", chat_history=[])

    def test_chat_hides_debug_when_disabled(self):
        fake_result = {
            "answer": "fake answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with patch("clothing_rag_demo.api.app.run_langgraph_agent", return_value=fake_result):
            response = self.client.post(
                "/chat",
                json={"query": "这件衣服适合夏天吗？", "debug": False},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "fake answer"})

    # /chat/pipeline 走旧手写 pipeline
    def test_pipeline_calls_pipeline_executor(self):
        fake_result = {
            "answer": "pipeline answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with patch(
            "clothing_rag_demo.api.app.run_agent",
            return_value=fake_result,
        ) as mock_run:
            response = self.client.post(
                "/chat/pipeline",
                json={
                    "query": "我 175cm 70kg 穿什么码？",
                    "chat_history": [],
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fake_result)
        mock_run.assert_called_once_with("我 175cm 70kg 穿什么码？", chat_history=[])

    # /chat/langgraph 保留旧路径，仍然可用
    def test_langgraph_endpoint_still_works(self):
        fake_result = {
            "answer": "shadow answer",
            "debug": {"stop_reason": "final_answer"},
        }

        with patch(
            "clothing_rag_demo.api.app.run_langgraph_agent",
            return_value=fake_result,
        ) as mock_run:
            response = self.client.post(
                "/chat/langgraph",
                json={
                    "query": "这件衣服适合夏天吗？",
                    "chat_history": [],
                    "debug": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fake_result)
        mock_run.assert_called_once_with("这件衣服适合夏天吗？", chat_history=[])

    def test_chat_rejects_blank_query(self):
        response = self.client.post("/chat", json={"query": "   "})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
