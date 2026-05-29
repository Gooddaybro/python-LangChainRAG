import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from clothing_assistant.api.schemas import LegacyChatRequest, PythonChatRequest, PythonChatResponse
from clothing_assistant.agent.agent_executor import run_agent
from clothing_assistant.agent.langgraph_executor import run_langgraph_agent
from clothing_assistant.config_data import PROJECT_API_TITLE

logger = logging.getLogger(__name__)


app = FastAPI(
    title=PROJECT_API_TITLE,
    description="API entrypoint for the clothing size and product QA assistant.",
    version="0.2.0",
)


async def extract_request_id(request: Request):
    try:
        body = await request.json()
    except Exception:
        return None

    if not isinstance(body, dict):
        return None

    return body.get("request_id")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "request_id": await extract_request_id(request),
            "message": "AI service failed to process the request.",
        },
    )


def build_legacy_chat_response(agent_result, include_debug):
    if include_debug:
        return agent_result

    return {"answer": agent_result["answer"]}


def get_agent_intent(agent_result):
    debug = agent_result.get("debug", {})
    return debug.get("intent_result", {}).get("intent") or "unknown"


def build_suggested_actions(agent_result):
    debug = agent_result.get("debug", {})

    if debug.get("stop_reason") == "missing_info":
        return [{"type": "ask_follow_up"}]

    return []


def build_contract_chat_response(agent_result, request_id, include_debug):
    response = PythonChatResponse(
        request_id=request_id,
        answer=agent_result["answer"],
        intent=get_agent_intent(agent_result),
        product_refs=[],
        suggested_actions=build_suggested_actions(agent_result),
        debug=agent_result.get("debug") if include_debug else None,
    )
    return response.model_dump(exclude_none=True)


@app.get("/health")
def health():
    return {"status": "ok"}


# /chat 现在走 LangGraph 主工作流（原主线 pipeline 保留在 /chat/pipeline）。
@app.post("/chat")
def chat(request: PythonChatRequest):
    try:
        result = run_langgraph_agent(
            request.query.strip(),
            chat_history=request.chat_history_dicts(),
            thread_id=request.thread_id or request.session_id,
            request_id=request.request_id,
            session_id=request.session_id,
            user_context=request.user_context_dict(),
            candidates=request.candidate_dicts(),
        )
    except Exception:
        logger.exception("Unhandled exception on POST /chat")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "request_id": request.request_id,
                "message": "AI service failed to process the request.",
            },
        )

    return build_contract_chat_response(result, request.request_id, request.debug)


# 旧手写 pipeline 对照入口，方便和 LangGraph 做行为对比。
@app.post("/chat/pipeline")
def chat_pipeline(request: LegacyChatRequest):
    result = run_agent(request.query.strip(), chat_history=request.chat_history)
    return build_legacy_chat_response(result, request.debug)


# 保留旧的 /chat/langgraph 路径，避免破坏已有调用方。+++++++
@app.post("/chat/langgraph")
def chat_langgraph(request: LegacyChatRequest):
    result = run_langgraph_agent(
        request.query.strip(),
        chat_history=request.chat_history,
        thread_id=request.thread_id,
    )
    return build_legacy_chat_response(result, request.debug)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
