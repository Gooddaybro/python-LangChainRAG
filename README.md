# AI Clothing Shopping Assistant System

面向服装电商客服和导购场景的 AI 助手系统，包含 Streamlit 演示入口和 FastAPI 后端入口。

- `app_file_uploader.py`：上传并重建本地知识库。
- `app_qa.py`：本地 Agent 调试台，可切换 LangGraph 主线和旧 Pipeline 对照。

## Setup

```powershell
pip install -r requirements.txt
$env:DASHSCOPE_API_KEY="your-dashscope-api-key"
```

## Run

先更新知识库：

```powershell
streamlit run clothing_rag_demo/app_file_uploader.py
```

再打开问答页：

```powershell
streamlit run clothing_rag_demo/app_qa.py
```

## FastAPI Backend

项目也提供 FastAPI 后端入口，适合把同一套 Agent 能力暴露给前端、App 或其他系统调用：

```powershell
uvicorn clothing_rag_demo.api.app:app --reload
```

启动后打开接口文档：

```text
http://127.0.0.1:8000/docs
```

如果本机 `8000` 端口已经被其他服务占用，可以改用：

```powershell
uvicorn clothing_rag_demo.api.app:app --reload --port 8001
```

当前接口：

- `GET /health`：健康检查。
- `POST /chat`：调用 LangGraph 主线 `run_langgraph_agent`。
- `POST /chat/pipeline`：调用旧手写 pipeline `run_agent`，用于迁移对照和回归检查。
- `POST /chat/langgraph`：兼容路径，同样调用 LangGraph 主线 `run_langgraph_agent`。

详细接口契约见 `docs/api-design.md`。

## Agent Executors

当前主线入口是 `clothing_rag_demo.agent.langgraph_executor.run_langgraph_agent`。
旧手写 pipeline 保留为 `clothing_rag_demo.agent.agent_executor.run_agent`，
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

结构化商品事实放在 `clothing_rag_demo/data/product_catalog.json`。
价格、库存、颜色列表、SKU、尺码规则 id 只从这个文件查询；
RAG 只负责颜色搭配、洗涤养护、风格场景这类解释性知识。

详细图结构和节点契约见 `docs/langgraph-flow.md`。
详细数据边界见 `docs/data-boundary.md`。
详细评测设计见 `docs/eval-plan.md`。

## Test

```powershell
python -m unittest discover -v
python -m compileall -q clothing_rag_demo tests
```

## Eval Report

生成确定性评测表。部分 case 会同时跑旧手写 pipeline 和 LangGraph 主线；
结构化查询等生产主线能力会标记为 LangGraph-only，避免把“迁移对照”
误当成“两个 executor 必须完全一致”。

```powershell
python -m clothing_rag_demo.agent.eval_report
```

## Local Agent Trace

Agent debug trace is always returned in `result["debug"]["trace_events"]`.
To also write local JSONL trace files:

```powershell
$env:AGENT_TRACE_TO_FILE="true"
streamlit run clothing_rag_demo/app_qa.py
```

Trace files are written to `clothing_rag_demo/traces/` by default and are ignored by git.

## Notes

`chat_history/`、`chroma_db/` 和 `_chroma_probe/` 是本地运行产物，不提交到版本库。知识文件仍放在 `clothing_rag_demo/data/`。
