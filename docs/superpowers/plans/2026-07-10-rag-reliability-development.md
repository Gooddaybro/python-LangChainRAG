# RAG Reliability Development Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前只能通过 fake RAG 验证流程的本地 RAG，发展成可重建、可真实评测、可调参、可溯源且证据不足时能拒答的最小可靠系统。

**Architecture:** MySQL/Java 继续负责商品、SKU、价格、库存和上下架事实，Python 只在 Java candidates 内重排序。RAG 只索引颜色、材质、洗涤、版型、季节和场景等解释性知识；先用真实检索评测建基线，再根据失败 case 补知识和调参。

**Tech Stack:** Python 3.11+、`unittest`、LangGraph、Jina embeddings、Kimi（Moonshot OpenAI 兼容接口）、FastAPI、本地 JSON 向量索引、Markdown/JSON 评测报告。

## Global Constraints

- 价格、库存、SKU、上下架和购买状态必须来自 Java/MySQL，不得从 RAG 推断。
- Python `product_refs` 必须可追溯到当前 Java `candidates`。
- 真实检索评测与现有 fake tool 路由评测分开。
- 单元测试不调用外部 embedding 或聊天模型；真实基线使用独立手动命令。
- `chroma_db/` 继续作为忽略提交的本地派生索引，知识源文件和评测 case 进入版本控制。
- 当前数据规模下不引入 Milvus、Qdrant、Elasticsearch、Kafka 或 CDC。
- 每次只调整一类变量，所有参数变更都必须保留评测前后证据。
- 不将密钥、凭证或本地向量文件写入文档和 Git。

---

## Development Order And Why

```text
1. 建真实检索评测器  -> 没有尺子就不能调参
2. 建索引状态和重建入口 -> 没有真实索引就只能测 fake RAG
3. 跑第一份基线报告 -> 后续修改才有对照组
4. 根据失败 case 补知识 -> 避免盲目堆文档
5. 用同一评测集调 top-k/阈值 -> 参数变更有数据依据
6. 增加来源和强事实防护 -> 让答案可溯源、可拒答
7. 原子化重建和更新界面 -> 防止重建失败破坏旧索引
8. 端到端验收 -> 确认单测、真实检索和 API 行为一致
```

---

### Task 1: Build The Real Retrieval Evaluation Module

**Why:** 当前 `eval_report` 和 `answer_quality_report` 使用 fake RAG，只能验证路由和答案规则。本任务单独回答“真实 query 是否召回了正确 chunk”。

**Files:**
- Modify: `clothing_assistant/config_data.py:20-23`
- Modify: `clothing_assistant/tools/rag_tool.py:1-45`
- Modify: `clothing_assistant/agent/nodes.py:31-44, 525-536`
- Create: `clothing_assistant/agent/retrieval_eval_cases.py`
- Create: `clothing_assistant/agent/retrieval_eval_report.py`
- Create: `tests/test_retrieval_eval_report.py`

**Interfaces:**
- Produces: `RAG_TOP_K: int = 3`
- Produces: `RAG_DISTANCE_THRESHOLD: float = 0.7`
- Produces: `evaluate_retrieval_case(case, retriever, top_k, threshold) -> dict`
- Produces: `build_retrieval_eval_report(cases, retriever, top_k, threshold) -> dict`
- Produces CLI: `python -m clothing_assistant.agent.retrieval_eval_report`

- [x] **Step 1: Add the shared runtime defaults test**

Create `tests/test_retrieval_eval_report.py` with the first test:

```python
import unittest

from clothing_assistant.config_data import RAG_DISTANCE_THRESHOLD, RAG_TOP_K


class RetrievalEvalReportTests(unittest.TestCase):
    def test_runtime_retrieval_defaults_are_explicit(self):
        self.assertEqual(RAG_TOP_K, 3)
        self.assertEqual(RAG_DISTANCE_THRESHOLD, 0.7)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the focused test and confirm RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_retrieval_eval_report -v
```

Expected: FAIL because `RAG_TOP_K` and `RAG_DISTANCE_THRESHOLD` do not exist.

- [x] **Step 3: Add shared retrieval constants and reuse them in production**

Add to `clothing_assistant/config_data.py`:

```python
RAG_TOP_K = 3
RAG_DISTANCE_THRESHOLD = 0.7
```

Change `clothing_assistant/tools/rag_tool.py` so `DEFAULT_AGENT_RAG_TOP_K` is removed and `run_rag_tool` defaults to `RAG_TOP_K`.

Change `clothing_assistant/agent/nodes.py` to import `RAG_DISTANCE_THRESHOLD` and use:

```python
def chunk_is_relevant(chunk, query_type, threshold=RAG_DISTANCE_THRESHOLD):
    score = float(chunk.get("score", 1.0))
    file_name = chunk.get("file_name")
    allowed_sources = RAG_ALLOWED_SOURCES.get(query_type)

    if score > threshold:
        return False

    if allowed_sources and file_name not in allowed_sources:
        return False

    return True
```

- [x] **Step 4: Add the initial real retrieval cases**

Create `clothing_assistant/agent/retrieval_eval_cases.py`:

```python
RETRIEVAL_EVAL_CASES = [
    {
        "name": "care_cotton_tshirt",
        "query": "纯棉T恤怎么洗？",
        "query_type": "product",
        "expected_file_names": ["洗涤养护.txt"],
        "expected_keywords_any": ["纯棉", "30℃", "中性洗涤剂"],
        "should_retrieve": True,
    },
    {
        "name": "care_wool_sweater",
        "query": "羊毛衫可以机洗吗？",
        "query_type": "product",
        "expected_file_names": ["洗涤养护.txt"],
        "expected_keywords_any": ["羊毛", "干洗", "手洗"],
        "should_retrieve": True,
    },
    {
        "name": "care_denim_fading",
        "query": "牛仔外套怎么洗不容易掉色？",
        "query_type": "product",
        "expected_file_names": ["洗涤养护.txt"],
        "expected_keywords_any": ["牛仔", "翻面", "褪色"],
        "should_retrieve": True,
    },
    {
        "name": "color_commute",
        "query": "日常通勤适合什么颜色？",
        "query_type": "recommendation",
        "expected_file_names": ["颜色选择.txt"],
        "expected_keywords_any": ["通勤", "基础色", "藏蓝"],
        "should_retrieve": True,
    },
    {
        "name": "color_daily_basic",
        "query": "想要百搭耐看应该优先什么颜色？",
        "query_type": "recommendation",
        "expected_file_names": ["颜色选择.txt"],
        "expected_keywords_any": ["基础色", "黑白灰", "百搭"],
        "should_retrieve": True,
    },
    {
        "name": "care_silk",
        "query": "真丝衬衫清洗时要注意什么？",
        "query_type": "product",
        "expected_file_names": ["洗涤养护.txt"],
        "expected_keywords_any": ["真丝", "25℃", "禁止搓揉"],
        "should_retrieve": True,
    },
    {
        "name": "care_knit_drying",
        "query": "针织衫洗完为什么不建议悬挂晾干？",
        "query_type": "product",
        "expected_file_names": ["洗涤养护.txt"],
        "expected_keywords_any": ["针织", "平铺阴干", "拉伸"],
        "should_retrieve": True,
    },
    {
        "name": "color_interview",
        "query": "面试场景选什么颜色更稳妥？",
        "query_type": "recommendation",
        "expected_file_names": ["颜色选择.txt"],
        "expected_keywords_any": ["正式", "稳重", "低饱和"],
        "should_retrieve": True,
    },
    {
        "name": "unsupported_fireproof_standard",
        "query": "这件衣服符合哪个防火服国家标准？",
        "query_type": "product",
        "expected_file_names": [],
        "expected_keywords_any": [],
        "should_retrieve": False,
    },
    {
        "name": "unsupported_polar_expedition",
        "query": "纯棉T恤能不能作为极地科考的主保暖层？",
        "query_type": "product",
        "expected_file_names": [],
        "expected_keywords_any": [],
        "should_retrieve": False,
    },
]
```

- [x] **Step 5: Add failing evaluator behavior tests**

Append tests using an injected fake retriever:

```python
from clothing_assistant.agent.retrieval_eval_report import (
    build_retrieval_eval_report,
    evaluate_retrieval_case,
)


def fake_retriever(query, top_k=3, query_type=None):
    if "防火服" in query:
        chunks = [{"file_name": "颜色选择.txt", "chunk_id": "color-1", "content": "通勤颜色", "score": 0.91}]
    else:
        chunks = [{"file_name": "洗涤养护.txt", "chunk_id": "care-1", "content": "纯棉建议30℃以下洗涤", "score": 0.12}]
    return {"retrieved_chunks": chunks[:top_k], "retrieval_query": query, "rag_meta": {}}


class RetrievalEvalReportTests(unittest.TestCase):
    # Keep the defaults test from Step 1.

    def test_positive_case_passes_when_expected_chunk_is_accepted(self):
        case = {
            "name": "cotton",
            "query": "纯棉怎么洗",
            "query_type": "product",
            "expected_file_names": ["洗涤养护.txt"],
            "expected_keywords_any": ["纯棉"],
            "should_retrieve": True,
        }
        row = evaluate_retrieval_case(case, fake_retriever, top_k=3, threshold=0.7)
        self.assertTrue(row["passed"])
        self.assertTrue(row["hit"])

    def test_negative_case_passes_when_all_chunks_are_above_threshold(self):
        case = {
            "name": "fireproof",
            "query": "防火服国家标准",
            "query_type": "product",
            "expected_file_names": [],
            "expected_keywords_any": [],
            "should_retrieve": False,
        }
        row = evaluate_retrieval_case(case, fake_retriever, top_k=3, threshold=0.7)
        self.assertTrue(row["passed"])
        self.assertEqual(row["accepted_chunks"], [])

    def test_report_separates_hits_and_false_accepts(self):
        report = build_retrieval_eval_report(
            cases=[
                {
                    "name": "cotton",
                    "query": "纯棉怎么洗",
                    "query_type": "product",
                    "expected_file_names": ["洗涤养护.txt"],
                    "expected_keywords_any": ["纯棉"],
                    "should_retrieve": True,
                },
                {
                    "name": "fireproof",
                    "query": "防火服国家标准",
                    "query_type": "product",
                    "expected_file_names": [],
                    "expected_keywords_any": [],
                    "should_retrieve": False,
                },
            ],
            retriever=fake_retriever,
            top_k=3,
            threshold=0.7,
        )
        self.assertEqual(report["summary"]["positive_hit_count"], 1)
        self.assertEqual(report["summary"]["false_accept_count"], 0)
```

- [x] **Step 6: Implement the minimal evaluator and CLI**

Create `clothing_assistant/agent/retrieval_eval_report.py` following the existing `answer_quality_report.py` formatter/CLI pattern. Required behavior:

```python
def accepted_chunks(chunks, threshold):
    return [chunk for chunk in chunks if float(chunk.get("score", 1.0)) <= threshold]


def expected_chunk_matches(chunk, case):
    if chunk.get("file_name") not in case["expected_file_names"]:
        return False
    keywords = case.get("expected_keywords_any", [])
    return not keywords or any(keyword in chunk.get("content", "") for keyword in keywords)


def evaluate_retrieval_case(case, retriever=run_rag_tool, top_k=RAG_TOP_K, threshold=RAG_DISTANCE_THRESHOLD):
    result = retriever(case["query"], top_k=top_k, query_type=case["query_type"])
    retrieved = result.get("retrieved_chunks", [])
    accepted = accepted_chunks(retrieved, threshold)
    hit = any(expected_chunk_matches(chunk, case) for chunk in accepted)
    false_accept = not case["should_retrieve"] and bool(accepted)
    passed = hit if case["should_retrieve"] else not false_accept
    return {
        "case": case["name"],
        "query": case["query"],
        "query_type": case["query_type"],
        "retrieval_query": result.get("retrieval_query"),
        "retrieved_chunks": retrieved,
        "accepted_chunks": accepted,
        "hit": hit,
        "false_accept": false_accept,
        "passed": passed,
    }
```

The report summary must contain:

```python
{
    "case_count": len(rows),
    "positive_case_count": positive_count,
    "positive_hit_count": positive_hits,
    "hit_rate": positive_hits / positive_count if positive_count else 0.0,
    "negative_case_count": negative_count,
    "false_accept_count": false_accepts,
    "false_accept_rate": false_accepts / negative_count if negative_count else 0.0,
    "pass_count": sum(row["passed"] for row in rows),
    "failed_count": sum(not row["passed"] for row in rows),
    "top_k": top_k,
    "threshold": threshold,
}
```

CLI arguments:

```text
--top-k INT
--threshold FLOAT
--format markdown|json
--output PATH
```

- [x] **Step 7: Run tests and compile check**

```bash
.venv/bin/python -m unittest tests.test_retrieval_eval_report tests.test_rag_tool tests.test_langgraph_production_nodes -v
.venv/bin/python -m compileall -q clothing_assistant tests
```

Expected: all focused tests PASS.

- [x] **Step 8: Commit the evaluator slice**

```bash
git add clothing_assistant/config_data.py clothing_assistant/tools/rag_tool.py clothing_assistant/agent/nodes.py clothing_assistant/agent/retrieval_eval_cases.py clothing_assistant/agent/retrieval_eval_report.py tests/test_retrieval_eval_report.py
git commit -m "test: add real RAG retrieval evaluation"
```

---

### Task 2: Make Vector-Store Readiness Observable

**Why:** 索引是被 Git 忽略的派生产物。服务“存活”不等于 RAG “就绪”，必须能区分索引缺失、meta 缺失、源文件过期和正常可用。

**Files:**
- Modify: `clothing_assistant/infrastructure/vector_store.py:51-101, 184-207`
- Modify: `clothing_assistant/api/app.py:1-8, 148-156`
- Modify: `README.md:8-32, 58-67, 104-125`
- Create: `tests/test_vector_store.py`
- Modify: `tests/test_api.py:10-19`

**Interfaces:**
- Produces: `get_vector_store_status() -> dict`
- Produces API: `GET /health/rag`
- Keeps existing API: `GET /health -> {"status": "ok"}` unchanged

- [x] **Step 1: Write failing vector readiness tests**

Create `tests/test_vector_store.py` with temporary paths and patch module constants. Cover these exact states:

```text
missing_vector_store -> ready false
missing_meta         -> ready false
broken_meta          -> ready false
chunk_count_mismatch -> ready false
source_files_changed -> ready false
ready                -> ready true
```

The ready assertion must expect:

```python
{
    "ready": True,
    "reason": "ready",
    "chunk_count": 2,
    "version": "test-version",
    "built_at": "2026-07-10T00:00:00+00:00",
}
```

- [x] **Step 2: Verify RED**

```bash
.venv/bin/python -m unittest tests.test_vector_store -v
```

Expected: FAIL because `get_vector_store_status` does not exist.

- [x] **Step 3: Implement the minimum readiness function**

Add `get_vector_store_status()` to `infrastructure/vector_store.py`. It must:

1. Check `VECTOR_STORE_FILE`.
2. Check `VECTOR_STORE_META_FILE`.
3. Catch invalid JSON.
4. Load records and compare record count with `meta["chunk_count"]`.
5. Rebuild current source-file hashes with `load_knowledge_files()`, `build_knowledge_chunks()` and `build_source_file_meta()`; compare them with `meta["source_files"]`.
6. Return only readiness metadata, never embeddings or file contents.

Required result reasons:

```text
missing_vector_store
missing_vector_store_meta
invalid_vector_store
invalid_vector_store_meta
chunk_count_mismatch
source_files_changed
ready
```

- [x] **Step 4: Add a non-breaking RAG health endpoint test**

Append to `tests/test_api.py`:

```python
def test_rag_health_returns_vector_store_status(self):
    status = {
        "ready": True,
        "reason": "ready",
        "chunk_count": 34,
        "version": "test-version",
        "built_at": "2026-07-10T00:00:00+00:00",
    }
    with patch("clothing_assistant.api.app.get_vector_store_status", return_value=status):
        response = self.client.get("/health/rag")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json(), status)
```

- [x] **Step 5: Implement `GET /health/rag`**

Import `get_vector_store_status` and add:

```python
@app.get("/health/rag")
def rag_health():
    return get_vector_store_status()
```

Do not change the existing `/health` response because Java/container liveness may depend on it.

- [x] **Step 6: Document the existing rebuild command and real eval command**

Add to `README.md`:

```bash
.venv/bin/python -m clothing_assistant.infrastructure.vector_store
.venv/bin/python -m clothing_assistant.agent.retrieval_eval_report
```

Explain that the first command requires the embedding provider environment variable and that `chroma_db/` is local generated state.

- [x] **Step 7: Verify**

```bash
.venv/bin/python -m unittest tests.test_vector_store tests.test_api -v
.venv/bin/python -m compileall -q clothing_assistant tests
```

- [x] **Step 8: Commit readiness support**

```bash
git add clothing_assistant/infrastructure/vector_store.py clothing_assistant/api/app.py tests/test_vector_store.py tests/test_api.py README.md
git commit -m "feat: expose RAG index readiness"
```

---

### Task 3: Build The First Real Baseline

**Why:** 本任务不修复失败 case，只保存当前配置的真实结果，为后续补知识和调参提供对照组。

**Files:**
- Generate: `docs/evals/2026-07-10-rag-baseline.md`
- Read only: `clothing_assistant/chroma_db/vector_store_meta.json`

**Interfaces:**
- Consumes: configured embedding provider environment variable
- Produces: committed baseline report without secrets or embedding vectors

- [x] **Step 1: Confirm the Jina API key is present without printing it**

```bash
.venv/bin/python -c 'import clothing_assistant.config_data; import os; assert os.getenv("JINA_API_KEY"), "JINA_API_KEY is not configured"'
```

- [x] **Step 2: Rebuild from committed knowledge files**

```bash
.venv/bin/python -m clothing_assistant.infrastructure.vector_store
```

Expected: writes the local vector records and meta, then prints at least one retrieval result.

- [x] **Step 3: Confirm readiness**

```bash
.venv/bin/python -c 'from clothing_assistant.infrastructure.vector_store import get_vector_store_status; print(get_vector_store_status())'
```

Expected: `ready` is `True` and `chunk_count` is greater than zero.

- [x] **Step 4: Generate the immutable baseline**

```bash
mkdir -p docs/evals
.venv/bin/python -m clothing_assistant.agent.retrieval_eval_report \
  --top-k 3 \
  --threshold 0.7 \
  --format markdown \
  --output docs/evals/2026-07-11-rag-baseline.md
```

The report is allowed to contain failed cases. Do not change data or parameters until this file exists.

- [x] **Step 5: Classify each failure in the report**

Append exactly one reason to every failed row:

```text
knowledge_missing
retrieval_miss
threshold_rejected
noisy_retrieval
wrong_routing
```

`generation_error` is not used here because this report stops before answer generation.

- [x] **Step 6: Commit only the report, never the vector files**

```bash
git add docs/evals/2026-07-11-rag-baseline.md
git commit -m "docs: record initial real RAG baseline"
```

---

### Task 4: Expand Knowledge Only For Known Coverage Gaps

**Why:** 当前只有尺码、颜色和洗涤文件，但产品边界已经声明 RAG 还负责材质、版型和场景解释。新知识必须由失败 case 驱动，而不是追求文件数量。

**Files:**
- Modify: `clothing_assistant/config_data.py:21-33`
- Modify: `clothing_assistant/infrastructure/knowledge_base.py:56-159`
- Modify: `clothing_assistant/infrastructure/vector_store.py:117-135, 157-181`
- Modify: `clothing_assistant/tools/rag_tool.py:26-34`
- Modify: `clothing_assistant/agent/nodes.py:33-41`
- Modify: `clothing_assistant/ui/app_file_uploader.py:1-25, 126-139`
- Create: `clothing_assistant/data/场景穿搭.txt`
- Create: `clothing_assistant/data/材质知识.txt`
- Create: `clothing_assistant/data/版型知识.txt`
- Create: `tests/test_knowledge_base.py`
- Modify: `clothing_assistant/agent/retrieval_eval_cases.py`

**Interfaces:**
- Produces chunk metadata: `domain`
- Keeps existing chunk keys: `chunk_id`, `file_name`, `file_path`, `content`
- Expands the upload allowlist through `KNOWLEDGE_FILES`

- [x] **Step 1: Add failing generic numbered-section splitter tests**

Create `tests/test_knowledge_base.py`:

```python
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
        docs = [{"file_name": "场景穿搭.txt", "file_path": "/tmp/scene.txt", "content": "1. 通勤\n选择简洁基础款。"}]
        chunks = build_knowledge_chunks(docs)
        self.assertEqual(chunks[0]["domain"], "scene")
```

- [x] **Step 2: Verify RED**

```bash
.venv/bin/python -m unittest tests.test_knowledge_base -v
```

- [x] **Step 3: Add file/domain configuration**

Add constants and extend the file list:

```python
SCENE_KNOWLEDGE_FILE = "场景穿搭.txt"
MATERIAL_KNOWLEDGE_FILE = "材质知识.txt"
FIT_KNOWLEDGE_FILE = "版型知识.txt"

KNOWLEDGE_FILE_DOMAINS = {
    SIZE_KNOWLEDGE_FILE: "size",
    COLOR_KNOWLEDGE_FILE: "color",
    CARE_KNOWLEDGE_FILE: "care",
    SCENE_KNOWLEDGE_FILE: "scene",
    MATERIAL_KNOWLEDGE_FILE: "material",
    FIT_KNOWLEDGE_FILE: "fit",
}
```

- [x] **Step 4: Generalize the existing numbered-section splitter**

Rename `split_color_text_into_chunks` to `split_numbered_sections_into_chunks`, use it for color, scene, material and fit documents, and add `domain` in `build_knowledge_chunks`:

```python
"domain": KNOWLEDGE_FILE_DOMAINS.get(doc["file_name"], "general"),
```

Preserve `domain` in vector records, search results and `simplify_chunk()`.

- [x] **Step 5: Add the initial curated knowledge content**

Write short numbered sections, one complete principle per section:

`clothing_assistant/data/场景穿搭.txt` must cover:

```text
1. 通勤：简洁、基础色、低饱和、利落版型。
2. 校园：舒适、耐穿、好搭、预算友好。
3. 约会：保留一个视觉重点，避免多个强元素竞争。
4. 旅行：耐皱、易打理、可叠穿、鞋服适配。
5. 轻运动：活动量、透气性、速干性和场景强度。
```

`clothing_assistant/data/材质知识.txt` must cover pure cotton, linen, polyester, wool/cashmere, denim and down, including advantages, limitations and suitable scenes without price/stock facts.

`clothing_assistant/data/版型知识.txt` must cover straight, A-line, high-waist, relaxed, slim and oversized fits, explaining proportions and movement without making absolute body-shape promises.

- [x] **Step 6: Update allowed RAG sources and uploader copy**

Add the three files to `RAG_ALLOWED_SOURCES` for `product` and `recommendation`; add fit knowledge to `size`. Change uploader text from hard-coded `3` to `len(KNOWLEDGE_FILES)` everywhere.

- [x] **Step 7: Add new positive retrieval cases before rebuilding**

Add at least these six cases:

```text
学生党日常上课怎么穿更实用 -> 场景穿搭.txt
约会穿搭怎么避免元素太多 -> 场景穿搭.txt
亚麻为什么凉快但容易皱 -> 材质知识.txt
聚酯面料有什么优缺点 -> 材质知识.txt
中高腰和低腰对比例有什么影响 -> 版型知识.txt
宽松版和过度 oversized 有什么区别 -> 版型知识.txt
```

- [x] **Step 8: Run deterministic tests, rebuild, and rerun real eval**

```bash
.venv/bin/python -m unittest tests.test_knowledge_base tests.test_retrieval_eval_report tests.test_rag_tool -v
.venv/bin/python -m clothing_assistant.infrastructure.vector_store
.venv/bin/python -m clothing_assistant.agent.retrieval_eval_report \
  --top-k 3 --threshold 0.7 \
  --output docs/evals/2026-07-11-rag-expanded-knowledge.md
```

- [x] **Step 9: Commit knowledge and evidence**

```bash
git add clothing_assistant/config_data.py clothing_assistant/infrastructure/knowledge_base.py clothing_assistant/infrastructure/vector_store.py clothing_assistant/tools/rag_tool.py clothing_assistant/agent/nodes.py clothing_assistant/ui/app_file_uploader.py clothing_assistant/data tests/test_knowledge_base.py tests/test_vector_store.py tests/test_rag_tool.py tests/test_langgraph_production_nodes.py clothing_assistant/agent/retrieval_eval_cases.py docs/evals/2026-07-11-rag-expanded-knowledge.md
git commit -m "feat: expand grounded clothing knowledge"
```

---

### Task 5: Calibrate Top-K And Distance Threshold

**Why:** 知识覆盖稳定后才能调参。本任务不用“感觉更好”选参数，而用固定网格和确定的选择规则。

**Files:**
- Generate: `docs/evals/rag-sweep-k1-t020.md` through `docs/evals/rag-sweep-k5-t070.md`
- Modify after selection: `clothing_assistant/config_data.py`
- Generate: `docs/evals/2026-07-11-rag-parameter-decision.md`

**Selection rule:** 在 `false_accept_count == 0` 的组合中选择 `positive_hit_count` 最高者；平局时先选更小 `top_k`，再选更严格（数值更小）的距离阈值。

- [x] **Step 1: Run the fixed 3x3 grid**

```bash
mkdir -p docs/evals
for k in 1 3 5; do
  for threshold in 0.40 0.55 0.70; do
    suffix=$(printf '%s' "$threshold" | tr -d '.')
    .venv/bin/python -m clothing_assistant.agent.retrieval_eval_report \
      --top-k "$k" \
      --threshold "$threshold" \
      --output "docs/evals/rag-sweep-k${k}-t${suffix}.md"
  done
done
```

The original grid produced no configuration with `false_accept_count == 0`.
Because the closest invalid result scored below `0.40`, run this follow-up
grid before changing runtime values:

```bash
for k in 1 3 5; do
  for threshold in 0.20 0.25 0.30; do
    suffix=$(printf '%s' "$threshold" | tr -d '.')
    .venv/bin/python -m clothing_assistant.agent.retrieval_eval_report \
      --top-k "$k" \
      --threshold "$threshold" \
      --output "docs/evals/rag-sweep-k${k}-t${suffix}.md"
  done
done
```

- [x] **Step 2: Build the decision document**

Create `docs/evals/2026-07-11-rag-parameter-decision.md` with one row per configuration:

```text
top_k | threshold | positive_hit_count | hit_rate | false_accept_count | selected
```

Apply the exact selection rule above and explain failed alternatives in one sentence each.

- [x] **Step 3: Update only the two shared constants**

Change `RAG_TOP_K` and `RAG_DISTANCE_THRESHOLD` to the selected values. Do not change chunking, query expansion or prompts in the same commit.

- [x] **Step 4: Verify the selected runtime defaults**

Update the expected constants in `tests/test_retrieval_eval_report.py`, then run:

```bash
.venv/bin/python -m unittest tests.test_retrieval_eval_report tests.test_rag_tool tests.test_langgraph_production_nodes -v
.venv/bin/python -m clothing_assistant.agent.retrieval_eval_report
```

- [x] **Step 5: Commit the single-variable decision**

```bash
git add clothing_assistant/config_data.py tests/test_retrieval_eval_report.py docs/evals
git commit -m "perf: calibrate RAG retrieval defaults"
```

---

### Task 6: Add Deterministic Sources To RAG Answers

**Why:** 让模型自己生成引用会有编造来源的风险。第一版不做复杂 claim extraction，只由程序把实际 accepted chunks 的来源追加到答案。

**Files:**
- Modify: `clothing_assistant/application/answer_service.py:10-28`
- Modify: `clothing_assistant/agent/nodes.py:745-872`
- Modify: `tests/test_langgraph_production_nodes.py:121-167`
- Modify: `tests/test_answer_quality_report.py`

**Interfaces:**
- Produces: `format_rag_sources(chunks) -> str`
- Produces: `append_rag_sources(answer, chunks) -> str`

- [x] **Step 1: Write failing source formatting tests**

Add tests that require:

```text
参考资料：颜色选择.txt（颜色选择.txt-001）
```

Requirements:

- Duplicate chunk IDs appear once.
- Empty chunks add no footer.
- Structured inventory/price answers add no RAG footer.
- Weak/empty retrieval fallback adds no fake source.

- [x] **Step 2: Verify RED**

```bash
.venv/bin/python -m unittest tests.test_langgraph_production_nodes tests.test_answer_quality_report -v
```

- [x] **Step 3: Implement deterministic source formatting**

Add to `answer_service.py`:

```python
def format_rag_sources(chunks):
    seen = set()
    sources = []
    for chunk in chunks or []:
        chunk_id = chunk.get("chunk_id")
        file_name = chunk.get("file_name")
        key = (file_name, chunk_id)
        if not file_name or not chunk_id or key in seen:
            continue
        seen.add(key)
        sources.append(f"{file_name}（{chunk_id}）")
    return "、".join(sources)


def append_rag_sources(answer, chunks):
    sources = format_rag_sources(chunks)
    if not sources:
        return answer
    return f"{answer}\n\n参考资料：{sources}"
```

In `answer_validator_node`, append sources only for accepted RAG answers immediately before returning `stop_reason="final_answer"`.

- [x] **Step 4: Include source IDs in evidence summary**

Add:

```python
"rag_sources": [
    {"file_name": chunk.get("file_name"), "chunk_id": chunk.get("chunk_id")}
    for chunk in state.get("accepted_chunks", [])
],
```

- [x] **Step 5: Verify**

```bash
.venv/bin/python -m unittest tests.test_langgraph_production_nodes tests.test_answer_quality_report tests.test_agent_pipeline -v
```

- [x] **Step 6: Commit source traceability**

```bash
git add clothing_assistant/application/answer_service.py clothing_assistant/agent/nodes.py tests/test_langgraph_production_nodes.py tests/test_answer_quality_report.py
git commit -m "feat: cite accepted RAG sources"
```

---

### Task 7: Reject Strong Commerce Facts In Pure RAG Answers

**Why:** RAG 证据只能解释通用知识。即使检索正确，大模型仍可能在回答中额外编造“99 元”、“库存 8 件”或“SKU 已上架”。

**Files:**
- Modify: `clothing_assistant/agent/nodes.py:788-860`
- Modify: `tests/test_langgraph_production_nodes.py`
- Modify: `clothing_assistant/agent/answer_quality_cases.py`

**Interfaces:**
- Produces: `find_forbidden_rag_fact(answer) -> str | None`
- Reuses: existing `generation_attempts`, `max_generation_attempts`, `validation_feedback`, and fallback path

- [x] **Step 1: Add failing validator tests**

Cover these exact behaviors:

```text
Pure RAG draft "这件衣服库存 8 件" -> retry, then fallback if repeated
Pure RAG draft "售价 99 元"       -> retry
Pure RAG draft "SKU ABC 已上架"   -> retry
Java candidate recommendation containing real sale_price -> remains valid
Structured inventory/price answer -> remains valid
```

- [x] **Step 2: Implement minimal pattern detection**

Use compiled regular expressions:

```python
RAG_FORBIDDEN_FACT_PATTERNS = [
    re.compile(r"\bSKU\b", re.IGNORECASE),
    re.compile(r"库存\s*\d+"),
    re.compile(r"\d+(?:\.\d+)?\s*元"),
    re.compile(r"(?:有货|无货|已上架|已下架)"),
]
```

Apply only when:

```python
state.get("accepted_chunks") and not has_candidate_backed_recommendation(state)
```

Do not apply to structured lookup or Java candidate-backed recommendation answers.

- [x] **Step 3: Return retry feedback through the existing graph loop**

On detection return:

```python
{
    "validation_result": {
        "grounded": False,
        "retryable": True,
        "reason": "rag_answer_contains_forbidden_commerce_fact",
    },
    "validation_feedback": "删除价格、库存、SKU 和上下架结论，只使用已接受的解释性知识。",
    "trace_events": make_trace("answer_validated", grounded=False, retryable=True, reason="forbidden_rag_fact"),
}
```

- [x] **Step 4: Add answer quality cases**

Add deterministic fake-generator cases proving the second failed attempt routes to `answer_fallback` and the user-visible answer contains no strong commerce fact.

- [x] **Step 5: Verify**

```bash
.venv/bin/python -m unittest tests.test_langgraph_production_nodes tests.test_answer_quality_report tests.test_agent_pipeline -v
```

- [x] **Step 6: Commit**

```bash
git add clothing_assistant/agent/nodes.py clothing_assistant/agent/answer_quality_cases.py tests/test_langgraph_production_nodes.py tests/test_answer_quality_report.py
git commit -m "fix: block commerce facts in pure RAG answers"
```

---

### Task 8: Make Vector Rebuild Atomic And The Uploader Dynamic

**Why:** 上传更新时如果向量文件写到一半失败，不能破坏上一版可用索引。文件数增加后，界面也不能继续写死“3 个文件”。

**Files:**
- Modify: `clothing_assistant/infrastructure/vector_store.py:138-154`
- Modify: `clothing_assistant/ui/app_file_uploader.py`
- Create: `clothing_assistant/infrastructure/knowledge_upload.py`
- Modify: `tests/test_vector_store.py`
- Create: `tests/test_app_file_uploader.py`

**Interfaces:**
- Produces: `write_json_atomically(path, value) -> None`
- Keeps existing: `rebuild_vector_store(knowledge_chunks) -> list`

- [x] **Step 1: Write failing atomic-write tests**

Tests must prove:

- Successful write replaces the target.
- Serialization failure leaves the previous target untouched.
- Temporary files are removed after success or failure.

- [x] **Step 2: Implement atomic JSON writes with stdlib only**

Use a sibling temporary file and `Path.replace()`:

```python
def write_json_atomically(path, value):
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
```

Build all embeddings and metadata before replacing either target. Replace the vector file first and meta file last, so meta remains the readiness marker.

- [x] **Step 3: Extract uploader validation away from Streamlit side effects**

Create `infrastructure/knowledge_upload.py` and move only these pure helpers into it so tests never import and execute the Streamlit page:

```text
validate_uploaded_files
calculate_file_md5
compare_uploaded_files
```

Do not move Streamlit rendering or add a class hierarchy.

- [x] **Step 4: Make uploader copy dynamic**

Every count and label must use `len(KNOWLEDGE_FILES)`. The page must list the configured names instead of mentioning three fixed files.

- [x] **Step 5: Verify**

```bash
.venv/bin/python -m unittest tests.test_vector_store tests.test_app_file_uploader -v
.venv/bin/python -m compileall -q clothing_assistant tests
```

- [x] **Step 6: Commit safe updates**

```bash
git add clothing_assistant/infrastructure/vector_store.py clothing_assistant/infrastructure/knowledge_upload.py clothing_assistant/ui/app_file_uploader.py tests/test_vector_store.py tests/test_app_file_uploader.py
git commit -m "fix: preserve working RAG index during rebuild"
```

---

### Task 9: Run End-To-End Acceptance And Update Documentation

**Why:** 单元测试验证规则，真实检索报告验证 embedding/index，API 手动验收验证完整链路。三者都通过才能宣布 RAG 可用。

**Files:**
- Modify: `docs/eval-plan.md`
- Modify: `docs/data-boundary.md`
- Modify: `README.md`
- Modify: `docs/rag-learning-and-development-roadmap.md`
- Generate: `docs/evals/2026-07-10-rag-final.md`

- [ ] **Step 1: Run all deterministic verification**

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python -m compileall -q clothing_assistant tests
```

Expected: all tests PASS with no external model call.

- [ ] **Step 2: Rebuild and run the final real retrieval report**

```bash
.venv/bin/python -m clothing_assistant.infrastructure.vector_store
.venv/bin/python -m clothing_assistant.agent.retrieval_eval_report \
  --format markdown \
  --output docs/evals/2026-07-10-rag-final.md
```

Initial acceptance targets:

```text
Positive Hit@3 >= 90%
Negative refusal accuracy >= 90%
Price/inventory routed to RAG = 0
Candidate-pool-external product refs = 0
Accepted RAG answers with deterministic sources = 100%
```

- [ ] **Step 3: Start the API and inspect readiness**

```bash
.venv/bin/python -m uvicorn clothing_assistant.api.app:app --port 8000
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/health/rag
```

Expected: liveness is `ok`; RAG readiness is `true` and exposes only safe metadata.

- [ ] **Step 4: Manually verify four end-to-end questions**

Use the Streamlit QA workbench with debug enabled:

```text
纯棉T恤怎么洗？
日常通勤适合什么颜色？
这件衣服符合哪个防火服国家标准？
基础款纯棉T恤黑色L码有货吗？
```

Confirm respectively: grounded care answer with source, grounded color answer with source, conservative fallback, and structured inventory without RAG source.

- [ ] **Step 5: Update documentation with actual final values**

Document:

- Selected `top_k` and distance threshold.
- Real retrieval report command.
- Index rebuild command.
- `/health/rag` behavior.
- Knowledge domains and prohibited RAG facts.
- Baseline versus final metrics.

Mark roadmap checkboxes complete only when the matching evidence exists.

- [ ] **Step 6: Final commit**

```bash
git add README.md docs/eval-plan.md docs/data-boundary.md docs/rag-learning-and-development-roadmap.md docs/evals/2026-07-10-rag-final.md
git commit -m "docs: complete RAG reliability rollout"
```

---

## Completion Definition

The plan is complete only when all statements below are true:

- A clean environment can rebuild the local vector index from committed knowledge files.
- `/health` still reports service liveness and `/health/rag` separately reports index readiness.
- Real retrieval evaluation runs without fake chunks and produces Markdown/JSON reports.
- Baseline and final reports make parameter changes measurable.
- RAG knowledge contains no live price, stock, SKU or purchasability facts.
- Pure RAG answers cannot introduce strong commerce facts.
- Accepted RAG answers show deterministic sources derived from accepted chunks.
- Java-candidate recommendations continue working when RAG is missing or weak.
- The complete deterministic test suite passes without external model calls.

## Explicit Non-Goals

- No professional vector database migration at the current scale.
- No automatic MySQL-to-vector full synchronization.
- No LLM judge in the first reliability rollout.
- No frontend redesign.
- No Java-Python chat contract change.
- No change to Java's ownership of commerce facts.
