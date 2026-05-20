"""手写 MVP Agent 执行器。

这个模块是旧手写 pipeline：按固定顺序完成路由、记忆、工具、兜底和生成。
LangGraph 主线复用这里的业务阶段函数，用来保持迁移期间的行为一致。

Learning: 所有 mutate 函数现在使用 dict 语法访问 state（因为 AgentState 是 TypedDict），
并且返回 trace_events 列表而不是直接往 state 里 append。
这是为了配合 LangGraph 的 Annotated reducer，避免 trace 事件重复。
"""

from langchain_core.messages import HumanMessage, SystemMessage

from clothing_rag_demo.agent.router import (
    INTENT_CHAT,
    INTENT_POLICY_QA,
    INTENT_UNKNOWN,
    intent_router,
)
from clothing_rag_demo.agent.state import AgentState, make_trace
from clothing_rag_demo.agent.tool_registry import (
    build_default_tool_registry,
    execute_tool_spec,
    find_tool,
)
from clothing_rag_demo.agent.tracing import persist_trace_if_enabled
from clothing_rag_demo.rag import get_chat_model
from clothing_rag_demo.tools.memory_tool import run_memory_tool


def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def build_agent_query(user_query, memory_result):
    """决定工具实际检索用的问题。

    如果当前问题依赖历史，就用 memory_tool 改写后的 memory_query；
    否则直接使用用户原始问题。
    """
    if memory_result["need_history"]:
        return memory_result["memory_query"]

    return user_query


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
    """组装最终给大模型的上下文。

    Learning: 当前 MVP 还没有按意图切换 system prompt，所以这里先把
    RAG、尺码、政策三个工具结果统一塞进同一个 prompt。
    """
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
    """不需要工具和大模型时直接回答。

    这是一道早停门：闲聊、无法识别的问题不应该继续消耗 RAG 或 LLM。
    """
    if intent_result["intent"] == INTENT_CHAT:
        return "我是服装导购助手，可以帮你做尺码推荐、颜色搭配、洗涤养护和基础商品咨询。"

    if intent_result["intent"] == INTENT_UNKNOWN:
        return "这个问题我暂时无法准确判断。你可以补充想咨询的是尺码、颜色、洗涤、库存还是售后政策。"

    return None


# ── Mutate 函数 ──────────────────────────────────────────────────
# 这些函数直接修改 state dict（因为 AgentState 是 TypedDict = dict），
# 并返回 trace_events 列表。调用方收集 trace_events 后通过 Annotated reducer 合并。
# ─────────────────────────────────────────────────────────────────


def route_intent(state):
    """Pipeline 阶段 1：识别意图并写入 State。返回 trace_events。"""
    state["intent_result"] = intent_router(state["user_query"])
    return make_trace(
        "route_intent",
        intent=state["intent_result"]["intent"],
        query_type=state["intent_result"]["query_type"],
        need_history=state["intent_result"]["need_history"],
    )


def resolve_memory(state):
    """Pipeline 阶段 2：判断当前问题是否需要历史上下文。返回 trace_events。"""
    state["memory_result"] = run_memory_tool(
        state["user_query"],
        state["chat_history"],
        intent_result=state["intent_result"],
    )
    state["agent_query"] = build_agent_query(state["user_query"], state["memory_result"])
    return make_trace(
        "resolve_memory",
        need_history=state["memory_result"]["need_history"],
        ignored_history_reason=state["memory_result"]["ignored_history_reason"],
    )


def apply_direct_answer_gate(state):
    """Pipeline 阶段 3：能直接回答就短路，避免不必要的工具调用。

    返回 (是否短路, trace_events)。
    """
    direct_answer = build_direct_answer(state["user_query"], state["intent_result"])

    if not direct_answer:
        return False, []

    state["answer"] = direct_answer
    state["final_prompt"] = "direct_answer，不调用大模型。"
    state["stop_reason"] = "direct_answer"
    return True, make_trace("direct_answer", intent=state["intent_result"]["intent"])


def execute_matching_tools(state, tool_registry):
    """Pipeline 阶段 4：让 ToolRegistry 根据 State 选择并执行工具。返回 trace_events。"""
    traces = []
    for tool in tool_registry:
        if tool.should_run(state):
            traces.extend(execute_tool_spec(state, tool))
    return traces


def apply_policy_fallback_gate(state):
    """政策类问题的安全兜底。返回 (是否兜底, trace_events)。"""
    policy_result = state["tool_results"].get("policy_tool")

    if not policy_result:
        return False, []

    if policy_result["has_policy_source"]:
        return False, []

    state["answer"] = policy_result["policy_answer"]
    state["final_prompt"] = "policy_tool 无政策来源，直接兜底。"
    state["stop_reason"] = "policy_fallback"
    return True, make_trace("policy_fallback", reason=policy_result.get("reason"))


def apply_fallback_rag_tool(state, tool_registry):
    """最后一道工具兜底。返回 trace_events。"""
    if state["selected_tools"]:
        return []

    rag_tool = find_tool(tool_registry, "rag_tool")

    if not rag_tool:
        return []

    traces = make_trace("fallback_tool", tool="rag_tool")
    traces.extend(execute_tool_spec(state, rag_tool))
    return traces


def generate_pipeline_answer(state, answer_generator):
    """Pipeline 阶段 5：把 State 中的工具结果交给回答生成器。返回 trace_events。"""
    state["answer"], state["final_prompt"] = answer_generator(state)
    state["stop_reason"] = "final_answer"
    return make_trace("answer_generated", stop_reason=state["stop_reason"])


# ── 响应构建 ─────────────────────────────────────────────────────


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
        thread_id=state.get("thread_id"),
        run_id=state.get("run_id"),
    )


def run_agent(user_query, chat_history=None, tool_registry=None, answer_generator=None):
    """运行旧手写 Pipeline Agent。

    Learning: 这条线保留为 LangGraph 主线的行为对照，不再作为默认入口。
    """
    state: AgentState = {
        "user_query": user_query,
        "chat_history": chat_history or [],
        "selected_tools": [],
        "tool_call_count": 0,
        "tool_results": {},
        "trace_events": [],
    }
    registry = tool_registry or build_default_tool_registry()
    answer_generator = answer_generator or default_answer_generator

    all_traces: list[dict] = []

    # 固定顺序执行让 MVP 更容易理解和测试
    all_traces.extend(route_intent(state))
    all_traces.extend(resolve_memory(state))

    stopped, traces = apply_direct_answer_gate(state)
    all_traces.extend(traces)
    if stopped:
        return build_response_from_state(state, all_traces)

    all_traces.extend(execute_matching_tools(state, registry))

    stopped, traces = apply_policy_fallback_gate(state)
    all_traces.extend(traces)
    if stopped:
        return build_response_from_state(state, all_traces)

    all_traces.extend(apply_fallback_rag_tool(state, registry))
    all_traces.extend(generate_pipeline_answer(state, answer_generator))

    return build_response_from_state(state, all_traces)


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
        thread_id=None,
        run_id=None,
):
    """统一 Agent 输出契约。

    answer 是用户可见内容；debug 是学习、测试和 eval report 用的内部证据。
    """
    rag_result = tool_results.get("rag_tool") or {}

    return {
        "answer": answer,
        "debug": {
            "user_query": user_query,
            "thread_id": thread_id,
            "run_id": run_id,
            "intent_result": intent_result,
            "selected_tools": selected_tools,
            "used_history": memory_result["used_history"],
            "ignored_history_reason": memory_result["ignored_history_reason"],
            "retrieval_query": rag_result.get("retrieval_query"),
            "retrieved_chunks": rag_result.get("retrieved_chunks", []),
            "tool_results": tool_results,
            "tool_call_count": tool_call_count,
            "final_prompt": final_prompt,
            "stop_reason": stop_reason,
            "trace_events": trace_events or [],
        },
    }


def main():
    history = [
        {
            "user_query": "我身高168，体重65kg，想买一件日常穿的T恤",
            "assistant_answer": "建议选择 L 码。",
        }
    ]
    test_queries = [
        "这件衣服适合夏天吗？",
        "我身高175cm，体重70kg，这件T恤适合我吗？",
        "那我想宽松一点呢？",
        "可以退货吗？",
        "你是谁？",
    ]

    for query in test_queries:
        print(query)
        result = run_agent(query, chat_history=history)
        print(result["answer"])
        print(result["debug"]["selected_tools"])
        print("-" * 60)


if __name__ == "__main__":
    main()
