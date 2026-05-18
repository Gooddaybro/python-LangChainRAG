"""LangGraph 执行器（从 shadow 升级为主线）。

把手写 pipeline 的阶段函数包成 LangGraph 节点，但不改变业务逻辑。
每个节点调用 agent_executor 里的 mutate 函数，然后返回一个 dict，
告诉 LangGraph "我改了哪些字段"。LangGraph 用 Annotated reducer 合并 trace_events。

Learning: 节点返回 dict 是 LangGraph 的核心约定。
LangGraph 会用 TypedDict 里的 Annotated reducer 来决定怎么合并每个字段。
trace_events 用 operator.add（追加），其他字段用默认 replace（覆盖）。
"""

from langgraph.graph import END, START, StateGraph

from clothing_rag_demo.agent.agent_executor import (
    apply_direct_answer_gate,
    apply_fallback_rag_tool,
    apply_policy_fallback_gate,
    build_response_from_state,
    default_answer_generator,
    execute_matching_tools,
    generate_pipeline_answer,
    resolve_memory,
    route_intent,
)
from clothing_rag_demo.agent.state import AgentState, make_trace
from clothing_rag_demo.agent.tool_registry import build_default_tool_registry, execute_tool_spec


def build_langgraph_agent(tool_registry=None, answer_generator=None, max_tool_calls=3):
    """构建 LangGraph 图。

    tool_registry 和 answer_generator 仍支持测试注入，这样 eval report 可以公平对比
    pipeline 和 LangGraph 两条执行路径。
    """
    registry = tool_registry or build_default_tool_registry()
    answer_generator = answer_generator or default_answer_generator

    # ── 节点适配层 ────────────────────────────────────────────────
    # 每个节点调用 agent_executor 里的 mutate 函数，收集返回的 trace_events，
    # 然后返回一个 dict，只包含自己修改的 state 字段。
    # LangGraph 会用 reducer 合并这些 dict 到图状态里。
    # ──────────────────────────────────────────────────────────────

    def route_intent_node(state):
        traces = route_intent(state)
        return {
            "intent_result": state["intent_result"],
            "trace_events": traces,
        }

    def resolve_memory_node(state):
        traces = resolve_memory(state)
        return {
            "memory_result": state["memory_result"],
            "agent_query": state["agent_query"],
            "trace_events": traces,
        }

    def direct_answer_node(state):
        stopped, traces = apply_direct_answer_gate(state)
        result = {"trace_events": traces}
        if stopped:
            result["answer"] = state["answer"]
            result["final_prompt"] = state["final_prompt"]
            result["stop_reason"] = state["stop_reason"]
        return result

    def execute_tools_node(state):
        traces = []
        for tool in registry:
            if not tool.should_run(state):
                continue

            # Learning: LangGraph v0.2 开始让"图"自己控制工具预算。
            # 这还不是完整 retry，但已经是未来循环/重试前必须先有的刹车。
            if state.get("tool_call_count", 0) >= max_tool_calls:
                traces.extend(make_trace(
                    "tool_budget_reached",
                    max_tool_calls=max_tool_calls,
                    tool_call_count=state.get("tool_call_count", 0),
                ))
                break

            traces.extend(execute_tool_spec(state, tool))

        return {
            "selected_tools": state["selected_tools"],
            "tool_call_count": state["tool_call_count"],
            "tool_results": state["tool_results"],
            "trace_events": traces,
        }

    def policy_fallback_node(state):
        stopped, traces = apply_policy_fallback_gate(state)
        result = {"trace_events": traces}
        if stopped:
            result["answer"] = state["answer"]
            result["final_prompt"] = state["final_prompt"]
            result["stop_reason"] = state["stop_reason"]
        return result

    def fallback_rag_node(state):
        traces = apply_fallback_rag_tool(state, registry)
        result = {"trace_events": traces}
        if state.get("selected_tools"):
            result["selected_tools"] = state["selected_tools"]
            result["tool_call_count"] = state["tool_call_count"]
            result["tool_results"] = state["tool_results"]
        return result

    def generate_answer_node(state):
        traces = generate_pipeline_answer(state, answer_generator)
        return {
            "answer": state["answer"],
            "final_prompt": state["final_prompt"],
            "stop_reason": state["stop_reason"],
            "trace_events": traces,
        }

    def tool_budget_exhausted_node(state):
        return {
            "answer": "工具调用次数已达到上限，当前无法继续自动调用工具。",
            "final_prompt": "tool budget exhausted",
            "stop_reason": "tool_budget_exhausted",
            "trace_events": make_trace(
                "tool_budget_exhausted",
                max_tool_calls=max_tool_calls,
                tool_call_count=state.get("tool_call_count", 0),
            ),
        }

    # ── 条件路由 ──────────────────────────────────────────────────

    def route_after_direct_answer(state):
        # stop_reason 是所有早停门的统一信号；有值就结束图执行。
        if state.get("stop_reason"):
            return "stop"

        if state.get("tool_call_count", 0) >= max_tool_calls:
            return "budget_exhausted"

        return "execute_tools"

    def route_after_policy_fallback(state):
        if state.get("stop_reason"):
            return "stop"

        # 已经有工具结果时直接生成答案，不再额外走 fallback RAG。
        if state.get("selected_tools"):
            return "generate_answer"

        if state.get("tool_call_count", 0) >= max_tool_calls:
            return "budget_exhausted"

        return "fallback_rag"

    # ── 图结构 ────────────────────────────────────────────────────
    # 和手写 run_agent 的顺序保持一致，方便 eval report 做一对一对照。
    graph = StateGraph(AgentState)
    graph.add_node("route_intent", route_intent_node)
    graph.add_node("resolve_memory", resolve_memory_node)
    graph.add_node("direct_answer", direct_answer_node)
    graph.add_node("execute_tools", execute_tools_node)
    graph.add_node("policy_fallback", policy_fallback_node)
    graph.add_node("fallback_rag", fallback_rag_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("tool_budget_exhausted", tool_budget_exhausted_node)

    graph.add_edge(START, "route_intent")
    graph.add_edge("route_intent", "resolve_memory")
    graph.add_edge("resolve_memory", "direct_answer")
    graph.add_conditional_edges(
        "direct_answer",
        route_after_direct_answer,
        {
            "stop": END,
            "budget_exhausted": "tool_budget_exhausted",
            "execute_tools": "execute_tools",
        },
    )
    graph.add_edge("execute_tools", "policy_fallback")
    graph.add_conditional_edges(
        "policy_fallback",
        route_after_policy_fallback,
        {
            "stop": END,
            "generate_answer": "generate_answer",
            "budget_exhausted": "tool_budget_exhausted",
            "fallback_rag": "fallback_rag",
        },
    )
    graph.add_edge("fallback_rag", "generate_answer")
    graph.add_edge("generate_answer", END)
    graph.add_edge("tool_budget_exhausted", END)

    return graph.compile()


def run_langgraph_agent(
    user_query,
    chat_history=None,
    tool_registry=None,
    answer_generator=None,
    max_tool_calls=3,
):
    """运行 LangGraph Agent，并返回与主线 run_agent 一致的结构。"""
    graph = build_langgraph_agent(
        tool_registry=tool_registry,
        answer_generator=answer_generator,
        max_tool_calls=max_tool_calls,
    )
    initial_state: AgentState = {
        "user_query": user_query,
        "chat_history": chat_history or [],
        "selected_tools": [],
        "tool_call_count": 0,
        "tool_results": {},
        "trace_events": [],
    }
    final_state = graph.invoke(initial_state)

    return build_response_from_state(final_state, final_state.get("trace_events", []))
