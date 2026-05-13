"""LangGraph shadow 执行器。

它把手写 pipeline 的阶段函数包成 LangGraph 节点，但不改变业务逻辑。
Learning: 当前目标是“行为对齐”，不是马上引入复杂循环、重试或 Checkpointer。
"""

from langgraph.graph import END, START, StateGraph

from clothing_rag_demo.agent.agent_executor import (
    apply_direct_answer_gate,
    apply_fallback_rag_tool,
    apply_policy_fallback_gate,
    build_response_from_state,
    default_answer_generator,
    generate_pipeline_answer,
    resolve_memory,
    route_intent,
)
from clothing_rag_demo.agent.state import AgentState
from clothing_rag_demo.agent.tool_registry import build_default_tool_registry, execute_tool_spec


def build_langgraph_agent(tool_registry=None, answer_generator=None, max_tool_calls=3):
    """构建 shadow graph。

    tool_registry 和 answer_generator 仍支持测试注入，这样 eval report 可以公平对比
    pipeline 和 LangGraph 两条执行路径。
    """
    registry = tool_registry or build_default_tool_registry()
    answer_generator = answer_generator or default_answer_generator

    # 这些 node 只是很薄的适配层：真正的业务逻辑仍然复用 agent_executor.py。
    # 这样可以先验证图结构，不急着重写已有稳定代码。
    def route_intent_node(state):
        route_intent(state)
        return state

    def resolve_memory_node(state):
        resolve_memory(state)
        return state

    def direct_answer_node(state):
        apply_direct_answer_gate(state)
        return state

    def execute_tools_node(state):
        for tool in registry:
            if not tool.should_run(state):
                continue

            # Learning: LangGraph v0.2 开始让“图”自己控制工具预算。
            # 这还不是完整 retry，但已经是未来循环/重试前必须先有的刹车。
            if state.tool_call_count >= max_tool_calls:
                state.add_trace(
                    "tool_budget_reached",
                    max_tool_calls=max_tool_calls,
                    tool_call_count=state.tool_call_count,
                )
                break

            execute_tool_spec(state, tool)

        return state

    def policy_fallback_node(state):
        apply_policy_fallback_gate(state)
        return state

    def fallback_rag_node(state):
        apply_fallback_rag_tool(state, registry)
        return state

    def generate_answer_node(state):
        generate_pipeline_answer(state, answer_generator)
        return state

    def tool_budget_exhausted_node(state):
        state.answer = "工具调用次数已达到上限，当前无法继续自动调用工具。"
        state.final_prompt = "tool budget exhausted"
        state.stop_reason = "tool_budget_exhausted"
        state.add_trace(
            "tool_budget_exhausted",
            max_tool_calls=max_tool_calls,
            tool_call_count=state.tool_call_count,
        )
        return state

    def route_after_direct_answer(state):
        # stop_reason 是所有早停门的统一信号；有值就结束图执行。
        if state.stop_reason:
            return "stop"

        if state.tool_call_count >= max_tool_calls:
            return "budget_exhausted"

        return "execute_tools"

    def route_after_policy_fallback(state):
        if state.stop_reason:
            return "stop"

        # 已经有工具结果时直接生成答案，不再额外走 fallback RAG。
        if state.selected_tools:
            return "generate_answer"

        if state.tool_call_count >= max_tool_calls:
            return "budget_exhausted"

        return "fallback_rag"

    # 图结构和手写 run_agent 的顺序保持一致，方便 eval report 做一对一对照。
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


def coerce_agent_state(state_value):
    """兼容 LangGraph 可能返回 dict 或 dataclass 的情况。"""
    if isinstance(state_value, AgentState):
        return state_value

    return AgentState(**state_value)


def run_langgraph_agent(
    user_query,
    chat_history=None,
    tool_registry=None,
    answer_generator=None,
    max_tool_calls=3,
):
    """运行 LangGraph shadow Agent，并返回与主线 run_agent 一致的结构。"""
    graph = build_langgraph_agent(
        tool_registry=tool_registry,
        answer_generator=answer_generator,
        max_tool_calls=max_tool_calls,
    )
    initial_state = AgentState(
        user_query=user_query,
        chat_history=chat_history or [],
    )
    final_state = coerce_agent_state(graph.invoke(initial_state))

    return build_response_from_state(final_state)
