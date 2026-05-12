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
from clothing_rag_demo.agent.state import AgentState
from clothing_rag_demo.agent.tool_registry import build_default_tool_registry


def build_langgraph_agent(tool_registry=None, answer_generator=None):
    registry = tool_registry or build_default_tool_registry()
    answer_generator = answer_generator or default_answer_generator

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
        execute_matching_tools(state, registry)
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

    def route_by_stop_reason(state):
        if state.stop_reason:
            return "stop"

        return "continue"

    graph = StateGraph(AgentState)
    graph.add_node("route_intent", route_intent_node)
    graph.add_node("resolve_memory", resolve_memory_node)
    graph.add_node("direct_answer", direct_answer_node)
    graph.add_node("execute_tools", execute_tools_node)
    graph.add_node("policy_fallback", policy_fallback_node)
    graph.add_node("fallback_rag", fallback_rag_node)
    graph.add_node("generate_answer", generate_answer_node)

    graph.add_edge(START, "route_intent")
    graph.add_edge("route_intent", "resolve_memory")
    graph.add_edge("resolve_memory", "direct_answer")
    graph.add_conditional_edges(
        "direct_answer",
        route_by_stop_reason,
        {
            "stop": END,
            "continue": "execute_tools",
        },
    )
    graph.add_edge("execute_tools", "policy_fallback")
    graph.add_conditional_edges(
        "policy_fallback",
        route_by_stop_reason,
        {
            "stop": END,
            "continue": "fallback_rag",
        },
    )
    graph.add_edge("fallback_rag", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()


def coerce_agent_state(state_value):
    if isinstance(state_value, AgentState):
        return state_value

    return AgentState(**state_value)


def run_langgraph_agent(user_query, chat_history=None, tool_registry=None, answer_generator=None):
    graph = build_langgraph_agent(
        tool_registry=tool_registry,
        answer_generator=answer_generator,
    )
    initial_state = AgentState(
        user_query=user_query,
        chat_history=chat_history or [],
    )
    final_state = coerce_agent_state(graph.invoke(initial_state))

    return build_response_from_state(final_state)
