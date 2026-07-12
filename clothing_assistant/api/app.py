import logging
import re

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from clothing_assistant.api.schemas import LegacyChatRequest, PythonChatRequest, PythonChatResponse, FeedbackRequest
from clothing_assistant.api.streaming import build_error_event, iter_stream_events
from clothing_assistant.agent.agent_executor import run_agent
from clothing_assistant.agent.langgraph_executor import run_langgraph_agent
from clothing_assistant.config_data import PROJECT_API_TITLE, is_debug_response_enabled
from clothing_assistant.infrastructure.vector_store import get_vector_store_status

logger = logging.getLogger(__name__)
INTERNAL_ERROR_MESSAGE = "AI service failed to process the request."
SAFE_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


app = FastAPI(
    title=PROJECT_API_TITLE,
    description="服装尺寸与商品问答助手的 API 入口。",
    version="0.2.0",
)


async def extract_safe_request_id(request: Request) -> str | None:
    try:
        body = await request.json()
    except Exception:
        return None

    if not isinstance(body, dict):
        return None

    request_id = body.get("request_id")
    if not isinstance(request_id, str):
        return None

    return request_id if SAFE_REQUEST_ID_PATTERN.fullmatch(request_id) else None


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器：捕获所有未被处理的系统内部异常，防止服务直接崩溃。

    统一返回 500 错误格式，并在日志中记录详细错误栈。
    """
    logger.exception("处理请求时发生未捕获的异常 %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "request_id": await extract_safe_request_id(request),
            "message": INTERNAL_ERROR_MESSAGE,
        },
    )


from fastapi.exceptions import RequestValidationError


async def extract_safe_request_body(request: Request):
    request_id = await extract_safe_request_id(request)
    if request_id is None:
        return None

    return {"request_id": request_id}


def sanitize_validation_errors(errors):
    sanitized = []
    for error in errors:
        sanitized.append(
            {
                key: value
                for key, value in error.items()
                if key not in {"input", "ctx", "url"}
            }
        )

    return sanitized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验异常处理器：当客户端(Java端)发送的请求数据格式不符合 Pydantic 模型（如缺少必填字段）时触发。

    返回 422 错误，并详细提示哪个字段校验失败。
    """
    safe_body = await extract_safe_request_body(request)
    safe_errors = sanitize_validation_errors(exc.errors())
    logger.warning(
        "422 validation error request_id=%s method=%s path=%s errors=%s",
        (safe_body or {}).get("request_id"),
        request.method,
        request.url.path,
        safe_errors,
    )
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"detail": safe_errors, "body": safe_body}),
    )


def build_legacy_chat_response(agent_result, include_debug):
    """构建旧版本聊天响应：根据是否需要调试信息，返回简化版的问答结果。"""
    include_debug = include_debug and is_debug_response_enabled()
    if include_debug:
        return agent_result

    return {"answer": agent_result["answer"]}


def get_agent_intent(agent_result):
    """提取意图：从 AI 代理的执行结果中提取用户的聊天意图（如：商品查询、尺寸建议等）。"""
    debug = agent_result.get("debug", {})
    return debug.get("intent_result", {}).get("intent") or "unknown"


def build_suggested_actions(agent_result):
    """构建建议动作：如果 AI 发现缺少必要信息（如未提供身高体重），

    则向前端/Java后端下发“请求追加信息 (ask_follow_up)”的动作指令。
    """
    debug = agent_result.get("debug", {})

    if debug.get("stop_reason") == "missing_info":
        return [{"type": "ask_follow_up"}]

    return []


def build_contract_chat_response(agent_result, request_id, include_debug):
    """构建符合最新契约的聊天响应：将 AI 执行的结果包装成 Java 侧所期望的标准 JSON 格式。

    包含了答案、意图、推荐商品列表以及建议动作。
    """
    include_debug = include_debug and is_debug_response_enabled()
    response = PythonChatResponse(
        request_id=request_id,
        answer=agent_result["answer"],
        intent=get_agent_intent(agent_result),
        product_refs=agent_result.get("product_refs", []),
        suggested_actions=build_suggested_actions(agent_result),
        debug=agent_result.get("debug") if include_debug else None,
    )
    return response.model_dump(exclude_none=True)


@app.get("/health")
def health():
    """健康检查接口：用于 Kubernetes 等容器服务或负载均衡器检查当前 Python 服务是否正常存活。"""
    return {"status": "ok"}


@app.get("/health/rag")
def rag_health():
    """Return RAG index readiness separately from service liveness."""
    return get_vector_store_status()


@app.post("/chat")
async def chat(chat_request: PythonChatRequest, request: Request):
    """主聊天接口（阻塞式）：接收用户的提问，调用 LangGraph 主工作流进行处理。

    这个接口会等待模型完全生成结果后，一次性返回完整的对话 JSON 响应。
    """
    try:
        result = run_langgraph_agent(
            chat_request.query.strip(),
            chat_history=chat_request.chat_history_dicts(),
            thread_id=chat_request.thread_id or chat_request.session_id,
            request_id=chat_request.request_id,
            session_id=chat_request.session_id,
            user_context=chat_request.user_context_dict(),
            candidates=chat_request.candidate_dicts(),
            demand_intent=(
                chat_request.demand_intent.model_dump(exclude_none=True, exclude_unset=True)
                if chat_request.demand_intent
                else None
            ),
        )
    except Exception:
        logger.exception("POST /chat 接口发生未捕获异常")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "request_id": await extract_safe_request_id(request),
                "message": INTERNAL_ERROR_MESSAGE,
            },
        )

    return build_contract_chat_response(result, chat_request.request_id, chat_request.debug)


def generate_chat_stream(request: PythonChatRequest):
    """流式生成器：运行 LangGraph 工作流，并将执行过程中的事件和打字机文本流

    转换为 Server-Sent Events (SSE) 格式，分块推送给 Java 后端。
    """
    try:
        result = run_langgraph_agent(
            request.query.strip(),
            chat_history=request.chat_history_dicts(),
            thread_id=request.thread_id or request.session_id,
            request_id=request.request_id,
            session_id=request.session_id,
            user_context=request.user_context_dict(),
            candidates=request.candidate_dicts(),
            demand_intent=(
                request.demand_intent.model_dump(exclude_none=True, exclude_unset=True)
                if request.demand_intent
                else None
            ),
        )
    except Exception:
        logger.exception("POST /chat/stream 接口发生未捕获异常")
        yield build_error_event("internal_error", INTERNAL_ERROR_MESSAGE)
        return

    yield from iter_stream_events(result, request.request_id)


@app.post("/chat/stream")
def chat_stream(request: PythonChatRequest):
    """流式聊天接口：前端和 Java 端用于获取“打字机效果”回复的主要接口。

    返回一个持续推送文本的 StreamingResponse，实现一边思考一边输出的功能。
    """
    return StreamingResponse(
        generate_chat_stream(request),
        media_type="text/event-stream;charset=utf-8",
        headers={
            "Cache-Control":"no-cache",
            "Connection":"keep-alive",
        },
    )


@app.post("/chat/pipeline")
def chat_pipeline(request: LegacyChatRequest):
    """旧版聊天接口：保留了旧的手写 pipeline 逻辑，主要用于开发和测试阶段，

    方便开发者比对与验证新旧工作流（LangGraph与Pipeline）的差异。
    """
    result = run_agent(request.query.strip(), chat_history=request.chat_history)
    return build_legacy_chat_response(result, request.debug)


@app.post("/chat/langgraph")
def chat_langgraph(request: LegacyChatRequest):
    result = run_langgraph_agent(
        request.query.strip(),
        chat_history=request.chat_history,
        thread_id=request.thread_id,
    )
    return build_legacy_chat_response(result, request.debug)


@app.post("/chat/feedback")
def receive_feedback(request: FeedbackRequest):
    """反馈收集接口：接收 Java 层转发过来的用户“点赞/踩”反馈。

    通过记录日志落盘，用于后期对 AI 推荐的准确度进行评估和模型微调。
    """
    # 根据契约：第一步先做简单落盘，把收到的点赞/踩信息打印到日志里
    logger.info(f"[Feedback Log] User {request.userId} rated {request.feedbackType} for message {request.messageId}")

    # 返回契约规定的 JSON 格式
    return {"status": "success", "message": "Feedback recorded"}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
