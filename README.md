# AI Clothing Shopping Assistant System

面向服装电商客服和导购场景的 AI 助手系统，包含 Streamlit 演示入口和 FastAPI 后端入口。

- `app_file_uploader.py`：上传并重建本地知识库。
- `app_qa.py`：普通 RAG 问答，可勾选启用导购 Agent。

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
- `POST /chat`：调用主线 `run_agent`。
- `POST /chat/langgraph`：调用 LangGraph shadow `run_langgraph_agent`。

## Agent Executors

当前主线入口仍是 `clothing_rag_demo.agent.agent_executor.run_agent`。
项目还提供 LangGraph 影子入口 `clothing_rag_demo.agent.langgraph_executor.run_langgraph_agent`，
用于验证现有 pipeline 能否迁移到 LangGraph，不默认接入 Streamlit。

## Test

```powershell
python -m unittest discover -v
python -m compileall -q clothing_rag_demo tests
```

## Eval Report

生成主线 Agent 和 LangGraph shadow 的确定性评测对比表：

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
