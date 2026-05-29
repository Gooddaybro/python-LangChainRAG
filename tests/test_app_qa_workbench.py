import unittest

from clothing_assistant.app_qa import (
    LANGGRAPH_MODE,
    PIPELINE_MODE,
    build_eval_tables,
    build_page_hero_html,
    build_status_summary,
    run_selected_agent,
)


class AgentWorkbenchTests(unittest.TestCase):
    def test_run_selected_agent_uses_pipeline_runner(self):
        calls = []
        history = [{"user_query": "前文", "assistant_answer": "回答"}]

        def pipeline_runner(query, chat_history=None):
            calls.append(("pipeline", query, chat_history))
            return {"answer": "pipeline answer", "debug": {}}

        def langgraph_runner(query, chat_history=None):
            calls.append(("langgraph", query, chat_history))
            return {"answer": "langgraph answer", "debug": {}}

        result = run_selected_agent(
            PIPELINE_MODE,
            "问题",
            chat_history=history,
            pipeline_runner=pipeline_runner,
            langgraph_runner=langgraph_runner,
        )

        self.assertEqual(result["answer"], "pipeline answer")
        self.assertEqual(calls, [("pipeline", "问题", history)])

    def test_run_selected_agent_uses_langgraph_runner(self):
        calls = []

        def pipeline_runner(query, chat_history=None):
            calls.append(("pipeline", query, chat_history))
            return {"answer": "pipeline answer", "debug": {}}

        def langgraph_runner(query, chat_history=None):
            calls.append(("langgraph", query, chat_history))
            return {"answer": "langgraph answer", "debug": {}}

        result = run_selected_agent(
            LANGGRAPH_MODE,
            "问题",
            chat_history=[],
            pipeline_runner=pipeline_runner,
            langgraph_runner=langgraph_runner,
        )

        self.assertEqual(result["answer"], "langgraph answer")
        self.assertEqual(calls, [("langgraph", "问题", [])])

    def test_build_status_summary_extracts_debug_fields(self):
        summary = build_status_summary(
            LANGGRAPH_MODE,
            {
                "intent_result": {"intent": "product_qa"},
                "selected_tools": ["rag_tool"],
                "stop_reason": "final_answer",
                "retrieved_chunks": [{"chunk_id": "1"}],
            },
        )

        self.assertEqual(summary["execution_mode"], LANGGRAPH_MODE)
        self.assertEqual(summary["intent"], "product_qa")
        self.assertEqual(summary["tool_count"], 1)
        self.assertEqual(summary["stop_reason"], "final_answer")
        self.assertEqual(summary["rag_chunk_count"], 1)

    def test_workbench_labels_langgraph_as_main_mode(self):
        hero_html = build_page_hero_html()

        self.assertEqual(LANGGRAPH_MODE, "LangGraph 主线")
        self.assertEqual(PIPELINE_MODE, "Pipeline 对照")
        self.assertIn("LangGraph 主线", hero_html)
        self.assertIn("Pipeline 对照", hero_html)
        self.assertNotIn("LangGraph Shadow", hero_html)
        self.assertNotIn("Pipeline 主线", hero_html)

    def test_build_eval_tables_returns_page_ready_rows(self):
        report = {
            "summary": {
                "case_count": 1,
                "pass_count": 2,
                "failed_count": 0,
                "consistent_case_count": 1,
                "inconsistent_case_count": 0,
            },
            "rows": [
                {
                    "case": "case1",
                    "executor": "pipeline",
                    "actual_intent": "chat",
                    "actual_tools": [],
                    "actual_stop_reason": "direct_answer",
                    "rag_chunk_count": 0,
                    "passed": True,
                }
            ],
            "consistency_rows": [
                {
                    "case": "case1",
                    "consistent": True,
                    "intent_count": 1,
                    "tools_count": 1,
                    "stop_reason_count": 1,
                    "rag_chunk_count_variants": 1,
                }
            ],
        }

        summary, result_rows, consistency_rows = build_eval_tables(report)

        self.assertEqual(summary["Cases"], 1)
        self.assertEqual(result_rows[0]["Tools"], "-")
        self.assertEqual(result_rows[0]["Pass"], "PASS")
        self.assertEqual(consistency_rows[0]["Consistent"], "PASS")


if __name__ == "__main__":
    unittest.main()
