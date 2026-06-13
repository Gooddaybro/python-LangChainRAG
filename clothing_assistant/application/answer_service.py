"""Shared answer construction for the legacy pipeline and LangGraph nodes."""

from langchain_core.messages import HumanMessage, SystemMessage

from clothing_assistant.agent.router import INTENT_CHAT, INTENT_UNKNOWN
from clothing_assistant.agent.tracing import persist_trace_if_enabled
from clothing_assistant.application.recommendation_service import build_product_refs
from clothing_assistant.infrastructure.llm_client import get_chat_model


def format_chunks(chunks):
    """把 RAG chunk 转成最终 prompt 可读的中文资料块。"""
    if not chunks:
        return "无可用知识库资料。"

    lines = []

    for index, chunk in enumerate(chunks, start=1):
        lines.append(
            "\n".join(
                [
                    f"资料{index}",
                    f"来源：{chunk['file_name']} | {chunk['chunk_id']}",
                    f"内容：{chunk['content']}",
                ]
            )
        )

    return "\n\n".join(lines)


def build_final_prompt(user_query, intent_result, memory_result, tool_results):
    """组装最终给大模型的上下文。"""
    rag_result = tool_results.get("rag_tool")
    size_result = tool_results.get("size_tool")
    policy_result = tool_results.get("policy_tool")

    rag_context = "未调用 RAG 工具。"

    if rag_result:
        rag_context = format_chunks(rag_result["retrieved_chunks"])

    return f"""
你是一个电商服装导购客服 Agent。
你必须基于工具结果回答，不要编造知识库外的信息。
如果工具结果不足，直接说明需要用户补充或联系人工客服。

用户问题：
{user_query}

意图判断：
{intent_result}

有效历史：
{memory_result["used_history"]}

RAG 检索资料：
{rag_context}

尺码工具结果：
{size_result}

政策工具结果：
{policy_result}

回答要求：
1. 中文回答，简洁，像客服。
2. 如果有 RAG 资料，先结合商品属性。
3. 如果问题需要尺码，再结合尺码工具结果。
4. 如果政策工具显示没有政策来源，不能编造退换货、物流、售后规则。
5. 如果尺码工具 match_type 是 measurement_conflict，只说明当前尺码表无法给出单一可靠尺码，引导用户补充胸围、肩宽、衣长或试穿确认，不要输出两个跨度很大的尺码作为推荐。
6. 不要输出 debug JSON，只输出给用户看的答案。
""".strip()


def generate_final_answer(user_query, intent_result, memory_result, tool_results):
    """调用真实聊天模型生成最终回答。测试里会用 fake answer_generator 替代它。"""
    final_prompt = build_final_prompt(user_query, intent_result, memory_result, tool_results)
    chat_model = get_chat_model()
    messages = [
        SystemMessage(content="你是可靠的电商服装导购客服 Agent。"),
        HumanMessage(content=final_prompt),
    ]
    response = chat_model.invoke(messages)

    return response.content, final_prompt


def default_answer_generator(state):
    return generate_final_answer(
        state["user_query"],
        state["intent_result"],
        state["memory_result"],
        state["tool_results"],
    )


def build_direct_answer(user_query, intent_result):
    """不需要工具和大模型时直接回答。"""
    if intent_result["intent"] == INTENT_CHAT:
        return "我是服装导购助手，可以帮你做尺码推荐、颜色搭配、洗涤养护和基础商品咨询。"

    if intent_result["intent"] == INTENT_UNKNOWN:
        return "这个问题我暂时无法准确判断。你可以补充想咨询的是尺码、颜色、洗涤、库存还是售后政策。"

    return None


def build_response_from_state(state, trace_events=None):
    """把内部 State 转成外部调用方稳定使用的 response/debug 结构。"""
    traces = trace_events if trace_events is not None else state.get("trace_events", [])
    persist_trace_if_enabled(state, traces)
    return build_agent_response(
        state["answer"],
        state["user_query"],
        state["intent_result"],
        state["selected_tools"],
        state["memory_result"],
        state["tool_results"],
        state["final_prompt"],
        stop_reason=state.get("stop_reason"),
        tool_call_count=state.get("tool_call_count", 0),
        trace_events=traces,
        request_id=state.get("request_id"),
        session_id=state.get("session_id"),
        thread_id=state.get("thread_id"),
        run_id=state.get("run_id"),
        user_context=state.get("user_context", {}),
        candidates=state.get("candidates", []),
        missing_info_result=state.get("missing_info_result", {}),
        structured_result=state.get("structured_result", {}),
        accepted_chunks=state.get("accepted_chunks", []),
        rejected_chunks=state.get("rejected_chunks", []),
        draft_answer=state.get("draft_answer", ""),
        validation_result=state.get("validation_result", {}),
        evidence_summary=state.get("evidence_summary", {}),
    )


def build_agent_response(
        answer,
        user_query,
        intent_result,
        selected_tools,
        memory_result,
        tool_results,
        final_prompt,
        stop_reason=None,
        tool_call_count=0,
        trace_events=None,
        request_id=None,
        session_id=None,
        thread_id=None,
        run_id=None,
        user_context=None,
        candidates=None,
        missing_info_result=None,
        structured_result=None,
        accepted_chunks=None,
        rejected_chunks=None,
        draft_answer=None,
        validation_result=None,
        evidence_summary=None,
):
    """统一 Agent 输出契约。"""
    rag_result = tool_results.get("rag_tool") or {}
    product_refs = build_product_refs(
        candidates,
        intent_result,
        user_query,
        user_context,
        tool_results,
    )

    return {
        "answer": answer,
        "product_refs": product_refs,
        "debug": {
            "user_query": user_query,
            "request_id": request_id,
            "session_id": session_id,
            "thread_id": thread_id,
            "run_id": run_id,
            "user_context": user_context or {},
            "candidates": candidates or [],
            "product_refs": product_refs,
            "intent_result": intent_result,
            "selected_tools": selected_tools,
            "used_history": memory_result["used_history"],
            "ignored_history_reason": memory_result["ignored_history_reason"],
            "retrieval_query": rag_result.get("retrieval_query"),
            "retrieved_chunks": rag_result.get("retrieved_chunks", []),
            "missing_info_result": missing_info_result or {},
            "structured_result": structured_result or {},
            "accepted_chunks": accepted_chunks or [],
            "rejected_chunks": rejected_chunks or [],
            "draft_answer": draft_answer or "",
            "validation_result": validation_result or {},
            "evidence_summary": evidence_summary or {},
            "tool_results": tool_results,
            "tool_call_count": tool_call_count,
            "final_prompt": final_prompt,
            "stop_reason": stop_reason,
            "trace_events": trace_events or [],
        },
    }
