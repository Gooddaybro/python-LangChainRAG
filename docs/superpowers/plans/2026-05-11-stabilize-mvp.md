# Stabilize Clothing RAG Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the clothing RAG agent MVP importable, testable, and cleaner to run without changing its core user-facing behavior.

**Architecture:** Keep the current router plus tools architecture. Convert imports to package-qualified imports, add deterministic tests, ignore generated artifacts, and document setup.

**Tech Stack:** Python 3.13, Streamlit, LangChain Tongyi/DashScope, local JSON vector store, `unittest`.

---

### Task 1: Add Regression Tests For Current MVP Contracts

**Files:**
- Create: `tests/test_agent_mvp.py`

- [ ] **Step 1: Write failing tests**

```python
import unittest

from clothing_assistant.agent.agent_executor import build_agent_query
from clothing_assistant.agent.router import (
    INTENT_POLICY_QA,
    INTENT_SIZE_RECOMMENDATION,
    intent_router,
)
from clothing_assistant.tools.memory_tool import run_memory_tool
from clothing_assistant.tools.policy_tool import build_no_policy_source_result
from clothing_assistant.tools.size_tool import build_size_query, run_size_tool


class AgentMvpTests(unittest.TestCase):
    def test_package_imports_work_from_repo_root(self):
        from clothing_assistant.agent.agent_executor import run_agent

        self.assertTrue(callable(run_agent))

    def test_router_identifies_policy_and_size_queries(self):
        self.assertEqual(intent_router("可以退货吗？")["intent"], INTENT_POLICY_QA)
        self.assertEqual(intent_router("我 175cm 70kg 穿什么码？")["intent"], INTENT_SIZE_RECOMMENDATION)

    def test_memory_does_not_inject_empty_history_for_reference_words(self):
        memory_result = run_memory_tool("这件衣服适合夏天吗？", [])

        self.assertFalse(memory_result["need_history"])
        self.assertEqual(build_agent_query("这件衣服适合夏天吗？", memory_result), "这件衣服适合夏天吗？")

    def test_size_tool_uses_history_measurements_for_follow_up(self):
        history = [
            {
                "user_query": "我身高168，体重65kg，想买一件日常穿的T恤",
                "assistant_answer": "建议选择 L 码。",
            }
        ]

        size_query = build_size_query("那我想宽松一点呢？", history)
        result = run_size_tool("那我想宽松一点呢？", chat_history=history)

        self.assertIn("身高168", size_query)
        self.assertEqual(result["recommended_size"], "L")
        self.assertEqual(result["alternative"], "XL")

    def test_no_policy_source_result_is_explicit_fallback(self):
        rag_result = {
            "retrieval_query": "可以退货吗？。退换货政策。",
            "retrieved_chunks": [],
        }

        result = build_no_policy_source_result("可以退货吗？", rag_result)

        self.assertFalse(result["has_policy_source"])
        self.assertIn("当前知识库没有退换货", result["policy_answer"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_agent_mvp -v`

Expected: failure or import error before package-qualified imports and memory logic are fixed.

### Task 2: Make Imports Package-Qualified

**Files:**
- Modify: `clothing_rag_demo/__init__.py`
- Modify: `clothing_rag_demo/app_qa.py`
- Modify: `clothing_rag_demo/app_file_uploader.py`
- Modify: `clothing_rag_demo/rag.py`
- Modify: `clothing_rag_demo/vector_stores.py`
- Modify: `clothing_rag_demo/knowledge_base.py`
- Modify: `clothing_rag_demo/size_matcher.py`
- Modify: `clothing_rag_demo/file_history_store.py`
- Modify: `clothing_rag_demo/agent/agent_executor.py`
- Modify: `clothing_rag_demo/agent/router.py`
- Modify: `clothing_rag_demo/tools/memory_tool.py`
- Modify: `clothing_rag_demo/tools/policy_tool.py`
- Modify: `clothing_rag_demo/tools/rag_tool.py`
- Modify: `clothing_rag_demo/tools/size_tool.py`

- [ ] **Step 1: Add package marker**

Create or keep `clothing_rag_demo/__init__.py` with a short package docstring.

- [ ] **Step 2: Replace local absolute imports**

Use package-qualified imports such as:

```python
from clothing_assistant.agent.router import intent_router
from clothing_assistant.config_data import DEFAULT_TEST_QUERY
from clothing_assistant.tools.size_tool import run_size_tool
```

- [ ] **Step 3: Run import test**

Run: `python -c "import clothing_rag_demo.agent.agent_executor; print('ok')"`

Expected: `ok`

### Task 3: Fix Empty-History Memory Injection

**Files:**
- Modify: `clothing_rag_demo/tools/memory_tool.py`
- Test: `tests/test_agent_mvp.py`

- [ ] **Step 1: Keep the failing memory test from Task 1**

The test `test_memory_does_not_inject_empty_history_for_reference_words` must fail before the fix because the current code sets `need_history=True` on reference words alone.

- [ ] **Step 2: Implement minimal fix**

Change `need_history` to require usable extracted history:

```python
need_history = bool(
    used_history["measurements_query"]
    or used_history["last_recommended_size"]
    or used_history["preference"]
    or used_history["current_product"]
)
```

Keep `has_reference_words` in debug output so the UI can still explain why a query looked like a follow-up.

- [ ] **Step 3: Run targeted test**

Run: `python -m unittest tests.test_agent_mvp.AgentMvpTests.test_memory_does_not_inject_empty_history_for_reference_words -v`

Expected: `OK`

### Task 4: Ignore Generated Runtime Artifacts

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Add ignore rules**

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
.idea/
.vscode/
clothing_rag_demo/chat_history/*.jsonl
clothing_rag_demo/chroma_db/
clothing_rag_demo/_chroma_probe/
```

- [ ] **Step 2: Check ignored files**

Run: `git status --short --ignored`

Expected: generated caches and local runtime data appear as ignored rather than untracked after they are removed from the index in a later cleanup step.

### Task 5: Document Setup And Run Commands

**Files:**
- Create: `requirements.txt`
- Create: `README.md`

- [ ] **Step 1: Add dependencies**

```text
streamlit
requests
langchain-core
langchain-community
dashscope
```

- [ ] **Step 2: Add README commands**

Document:

```powershell
pip install -r requirements.txt
$env:DASHSCOPE_API_KEY="your-key"
streamlit run clothing_rag_demo/app_file_uploader.py
streamlit run clothing_rag_demo/app_qa.py
python -m unittest discover -v
```

### Task 6: Final Verification

**Files:**
- Test all touched files.

- [ ] **Step 1: Compile**

Run: `python -m compileall -q clothing_rag_demo tests`

Expected: exit code 0.

- [ ] **Step 2: Unit tests**

Run: `python -m unittest discover -v`

Expected: all tests pass.

- [ ] **Step 3: Smoke tests**

Run:

```powershell
python -c "from clothing_rag_demo.agent.agent_executor import run_agent; result=run_agent('你是谁？'); print(result['answer']); print(result['debug']['selected_tools'])"
python -c "from clothing_rag_demo.tools.size_tool import run_size_tool; print(run_size_tool('我 175cm 70kg 穿什么码？')['recommended_size'])"
```

Expected: direct chat answer with no tools, and size recommendation `XL`.
