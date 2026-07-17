# AI Clothing Shopping Assistant System

面向服装电商客服和导购场景的 AI 助手系统，包含 Streamlit 演示入口和 FastAPI 后端入口。

- `ui/app_file_uploader.py`：上传并重建本地知识库。
- `ui/app_qa.py`：本地 Agent 调试台，可切换 LangGraph 主线和旧 Pipeline 对照。

## Setup

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
```

在项目根目录的 `.env` 中填写：

```dotenv
# 建立或查询 RAG 向量索引必填
JINA_API_KEY=your-jina-api-key

# 生成最终回答时必填；只重建索引和跑检索评测时可以留空
MOONSHOT_API_KEY=your-moonshot-api-key
```

`.env` 已被 Git 忽略，不能提交或发送。Jina 只负责将知识块和用户问题转换为向量；Kimi 只负责基于已检索证据生成最终回答。

如需启用“学生党、显高显瘦、平价百搭”等模糊需求的大模型结构化映射，再额外设置：

```powershell
$env:ENABLE_LLM_PREFERENCE_MAPPER="true"
```

未开启时系统使用规则版 preference parser，不会额外调用大模型。

## Run

先更新知识库：

```powershell
streamlit run clothing_assistant/ui/app_file_uploader.py
```

再打开问答页：

```powershell
streamlit run clothing_assistant/ui/app_qa.py
```

也可以直接从已提交的知识文件全量重建本地向量索引：

```bash
.venv/bin/python -m clothing_assistant.infrastructure.vector_store
```

该命令需要先配置 `JINA_API_KEY`。生成的 `clothing_assistant/chroma_db/` 是本地 JSON 向量索引（派生数据），不提交到 Git。

## FastAPI Backend

项目也提供 FastAPI 后端入口，适合把同一套 Agent 能力暴露给前端、App 或其他系统调用：

```powershell
uvicorn clothing_assistant.api.app:app --reload
```

启动后打开接口文档：

```text
http://127.0.0.1:8000/docs
```

如果本机 `8000` 端口已经被其他服务占用，可以改用：

```powershell
uvicorn clothing_assistant.api.app:app --reload --port 8001
```

当前接口：

- `GET /health`：健康检查。
- `GET /health/rag`：检查本地 RAG 索引是否就绪。
- `POST /chat`：调用 LangGraph 主线 `run_langgraph_agent`。
- `POST /chat/stream`：按 `..\outfit-project-contract\contracts\assistant-streaming-chat\v1.md` 输出 `token`、`done`、`error` SSE 事件，供 Java 后端流式转发。
- `POST /chat/pipeline`：调用旧手写 pipeline `run_agent`，用于迁移对照和回归检查。
- `POST /chat/langgraph`：兼容路径，同样调用 LangGraph 主线 `run_langgraph_agent`。

详细接口契约见 `docs/api-design.md`。
Java 后端联动契约见 `docs/integration/java-python-chat-contract.md`。
Java/Python 接口调整开发文档见 `docs/integration/java-python-chat-interface-development.md`。
Java/Python 接口调试文档见 `docs/integration/java-python-chat-interface-debugging.md`。
跨项目架构边界见 `docs/architecture/java-ai-clothing-mall-architecture.md`。

### Safe model-time streaming

`POST /chat/stream` consumes real Kimi provider fragments while the model is
generating. Python retains a safety tail and applies the same deterministic
commerce-fact rules used by the normal answer validator before releasing text.
`done.answer` is always the exact concatenation of emitted token contents.

Direct answers, Java-candidate answers, size rules, and fallback answers are
deterministic and may be emitted as one token event. A provider call may retry
only before public text is emitted. Client disconnect closes the request-scoped
stream and prevents later graph work or a `done` event.

Runtime defaults are `LLM_TIMEOUT_SECONDS=30`, `LLM_MAX_RETRIES=2`,
`LLM_MAX_CONCURRENCY=8`, `RAG_TIMEOUT_SECONDS=20`, and
`STREAM_SAFETY_TAIL_CHARS=64`.

### Local PostgreSQL Checkpoints

Development and tests use an in-memory checkpointer. To run the production
checkpointer locally, execute the following from the workspace root. The DSN
must use a password supplied through your local `.env` or shell, never a value
committed to this repository:

```bash
sh scripts/start-local-deps.sh
cd AI-Clothing-Shopping-Assistant-System
AI_RUNTIME_ENV=production \
LANGGRAPH_CHECKPOINTER_BACKEND=postgres \
LANGGRAPH_CHECKPOINTER_DSN='postgresql://...' \
.venv/bin/python -m uvicorn clothing_assistant.api.app:app
```

PostgreSQL checkpoint tables are LangGraph runtime metadata only. Java/MySQL
continues to own conversation messages, user identity, product facts, and
transaction state. Request payload channels are untracked and do not appear in
durable checkpoints; `PostgresSaver.setup()` creates the checkpointer tables on
Python startup.

## Agent Executors

当前主线入口是 `clothing_assistant.agent.langgraph_executor.run_langgraph_agent`。
旧手写 pipeline 保留为 `clothing_assistant.agent.agent_executor.run_agent`，
通过 `/chat/pipeline` 和 Streamlit 工作台中的 `Pipeline 对照` 模式用于行为对照。

LangGraph 主线现在按生产节点边界组织：

```text
intent_router
-> context_resolver
-> direct_answer_gate
-> missing_info_gate
-> structured_lookup
-> rag_retriever
-> retrieval_grader
-> answer_generator
-> answer_validator
-> trace_logger
```

结构化商品事实放在 `clothing_assistant/data/product_catalog.json`。
价格、库存、颜色列表、SKU、尺码规则 id 只从这个文件查询；
RAG 只负责颜色搭配、洗涤养护、风格场景这类解释性知识。

详细图结构和节点契约见 `docs/langgraph-flow.md`。
详细数据边界见 `docs/data-boundary.md`。
详细评测设计见 `docs/eval-plan.md`。

## Test

```powershell
python -m unittest discover -v
python -m compileall -q clothing_assistant tests
```

## Eval Report

生成确定性评测表。部分 case 会同时跑旧手写 pipeline 和 LangGraph 主线；
结构化查询等生产主线能力会标记为 LangGraph-only，避免把“迁移对照”
误当成“两个 executor 必须完全一致”。

```powershell
python -m clothing_assistant.agent.eval_report
```

生成答案质量评测表。这个报告不检查“有没有走对节点”，而是检查最终给用户看的答案是否包含关键事实、是否没有编造价格/库存、是否没有泄露 debug 字段。

```powershell
python -m clothing_assistant.agent.answer_quality_report
python -m unittest tests.test_answer_quality_report -v
```

生成真实向量检索报告。它不使用 fake chunks，专门统计正向问题的命中率和超出知识范围问题的错误接受率：

```bash
.venv/bin/python -m clothing_assistant.agent.retrieval_eval_report
.venv/bin/python -m clothing_assistant.agent.retrieval_eval_report \
  --top-k 3 \
  --threshold 0.7 \
  --output docs/evals/rag-retrieval.md
```

上述索引重建和检索评测只需要 Jina key；只有调用聊天回答、或开启 `ENABLE_LLM_PREFERENCE_MAPPER=true` 时才需要 Moonshot/Kimi key。

## RAG Reliability Status

当前 RAG 使用 6 份解释性知识文件（颜色、洗涤、尺码、场景、材质、版型），
共 51 个文本块。运行时参数由真实检索评测选择：`top_k=3`、距离阈值 `0.25`。

最终检索报告：正向命中 `13/14`（92.86%），知识外问题错误接受 `0/2`。
详细结果见 `docs/evals/2026-07-11-rag-final.md`，参数选择过程见
`docs/evals/2026-07-11-rag-parameter-decision.md`。

RAG 回答只会引用已接受的知识块，例如：

```text
参考资料：洗涤养护.txt（洗涤养护.txt-001）
```

价格、库存、SKU、上下架仍只来自 Java/MySQL 的结构化数据；纯 RAG 草稿出现
这些强业务事实时会重试一次，仍不合格则返回保守兜底。

检查索引状态：

```bash
curl -s http://127.0.0.1:8000/health/rag
```

返回只包含 `ready`、原因、chunk 数、版本和构建时间，不会暴露知识正文或向量。

## Local Agent Trace

Agent debug trace is always returned in `result["debug"]["trace_events"]`.
To also write local JSONL trace files:

```powershell
$env:AGENT_TRACE_TO_FILE="true"
streamlit run clothing_assistant/ui/app_qa.py
```

Trace files are written to `clothing_assistant/traces/` by default and are ignored by git.

## Notes

`chat_history/`、`chroma_db/` 和 `_chroma_probe/` 是本地运行产物，不提交到版本库。知识文件仍放在 `clothing_assistant/data/`。
