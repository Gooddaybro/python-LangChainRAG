"""手写 MVP Agent 执行器。

这个模块是旧手写 pipeline：按固定顺序完成路由、记忆、工具、兜底和生成。
LangGraph 主线复用这里的业务阶段函数，用来保持迁移期间的行为一致。

Learning: 所有 mutate 函数现在使用 dict 语法访问 state（因为 AgentState 是 TypedDict），
并且返回 trace_events 列表而不是直接往 state 里 append。
这是为了配合 LangGraph 的 Annotated reducer，避免 trace 事件重复。
"""

from clothing_assistant.agent.router import intent_router
from clothing_assistant.agent.state import AgentState, make_trace
from clothing_assistant.agent.tool_registry import (
    build_default_tool_registry,
    execute_tool_spec,
    find_tool,
)
from clothing_assistant.application.answer_service import (
    build_agent_response,
    build_direct_answer,
    build_final_prompt,
    build_response_from_state,
    default_answer_generator,
    format_chunks,
    generate_final_answer,
)
from clothing_assistant.tools.memory_tool import run_memory_tool


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
