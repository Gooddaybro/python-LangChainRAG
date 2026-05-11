import unittest

from clothing_rag_demo.agent.agent_executor import run_agent
from clothing_rag_demo.agent.eval_cases import EVAL_CASES
from clothing_rag_demo.agent.tool_registry import build_default_tool_registry


def fake_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "eval-chunk-001",
                "file_name": "颜色选择.txt",
                "content": "用于评测的知识库资料。",
                "score": 0.1,
            }
        ],
        "source_count": 1,
    }


def fake_policy_runner(query):
    return {
        "has_policy_source": False,
        "policy_answer": "当前知识库没有退换货、物流或售后政策资料，建议联系人工客服确认。",
        "retrieval_query": query,
        "policy_chunks": [],
        "raw_retrieved_chunks": [],
        "source_count": 0,
        "reason": "eval no policy source",
    }


def fake_size_runner(query, chat_history=None):
    return {
        "recommended_size": "L",
        "reason": "eval size",
        "alternative": "XL" if "宽松" in query else None,
        "match_type": "exact",
        "preference": None,
        "size_query": query,
        "measurements": {},
        "raw_match": {},
    }


def fake_answer_generator(state):
    return f"eval answer for {state.intent_result['intent']}", "eval prompt"


class AgentEvalCaseTests(unittest.TestCase):
    def test_eval_cases_cover_core_agent_contracts(self):
        registry = build_default_tool_registry(
            rag_runner=fake_rag_runner,
            policy_runner=fake_policy_runner,
            size_runner=fake_size_runner,
        )

        for case in EVAL_CASES:
            with self.subTest(case=case["name"]):
                result = run_agent(
                    case["query"],
                    chat_history=case.get("chat_history"),
                    tool_registry=registry,
                    answer_generator=fake_answer_generator,
                )

                debug = result["debug"]

                self.assertEqual(debug["intent_result"]["intent"], case["expected_intent"])
                self.assertEqual(debug["selected_tools"], case["expected_tools"])
                self.assertEqual(debug["stop_reason"], case["expected_stop_reason"])

                if case["requires_rag"]:
                    self.assertGreater(len(debug["retrieved_chunks"]), 0)
                else:
                    self.assertEqual(len(debug["retrieved_chunks"]), 0)


if __name__ == "__main__":
    unittest.main()
