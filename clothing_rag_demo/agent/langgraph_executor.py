"""LangGraph executor for the clothing assistant.

This module owns graph assembly, compilation, checkpoint configuration, and
runtime request metadata. Business node functions live in ``nodes.py``.
"""

from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from clothing_rag_demo.agent.agent_executor import (
    build_response_from_state,
    default_answer_generator,
)
from clothing_rag_demo.agent.nodes import (
    direct_answer_node,
    execute_tools_node,
    fallback_rag_node,
    generate_answer_node,
    policy_fallback_node,
    resolve_memory_node,
    route_after_direct_answer,
    route_after_policy_fallback,
    route_intent_node,
    tool_budget_exhausted_node,
)
from clothing_rag_demo.agent.state import AgentState, make_trace
from clothing_rag_demo.agent.tool_registry import build_default_tool_registry


_DEFAULT_CHECKPOINTER = InMemorySaver()
_DEFAULT_LANGGRAPH_AGENT = None


def generate_thread_id():
    return f"thread-{uuid4()}"


def generate_run_id():
    return f"run-{uuid4()}"


def build_graph_invoke_config(thread_id):
    return {"configurable": {"thread_id": thread_id}}


def build_langgraph_agent(
    tool_registry=None,
    answer_generator=None,
    max_tool_calls=3,
    checkpointer=None,
):
    """Build and compile the LangGraph assistant graph."""
    registry = tool_registry or build_default_tool_registry()
    answer_generator = answer_generator or default_answer_generator

    graph = StateGraph(AgentState)
    graph.add_node("route_intent", route_intent_node)
    graph.add_node("resolve_memory", resolve_memory_node)
    graph.add_node("direct_answer", direct_answer_node)
    graph.add_node(
        "execute_tools",
        lambda state: execute_tools_node(state, registry=registry, max_tool_calls=max_tool_calls),
    )
    graph.add_node("policy_fallback", policy_fallback_node)
    graph.add_node("fallback_rag", lambda state: fallback_rag_node(state, registry=registry))
    graph.add_node(
        "generate_answer",
        lambda state: generate_answer_node(state, answer_generator=answer_generator),
    )
    graph.add_node(
        "tool_budget_exhausted",
        lambda state: tool_budget_exhausted_node(state, max_tool_calls=max_tool_calls),
    )

    graph.add_edge(START, "route_intent")
    graph.add_edge("route_intent", "resolve_memory")
    graph.add_edge("resolve_memory", "direct_answer")
    graph.add_conditional_edges(
        "direct_answer",
        lambda state: route_after_direct_answer(state, max_tool_calls=max_tool_calls),
        {
            "stop": END,
            "budget_exhausted": "tool_budget_exhausted",
            "execute_tools": "execute_tools",
        },
    )
    graph.add_edge("execute_tools", "policy_fallback")
    graph.add_conditional_edges(
        "policy_fallback",
        lambda state: route_after_policy_fallback(state, max_tool_calls=max_tool_calls),
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

    return graph.compile(checkpointer=checkpointer)


def get_default_langgraph_agent():
    """Return the cached production graph compiled with an in-memory checkpointer."""
    global _DEFAULT_LANGGRAPH_AGENT

    if _DEFAULT_LANGGRAPH_AGENT is None:
        _DEFAULT_LANGGRAPH_AGENT = build_langgraph_agent(checkpointer=_DEFAULT_CHECKPOINTER)

    return _DEFAULT_LANGGRAPH_AGENT


def should_use_default_graph(tool_registry, answer_generator, max_tool_calls):
    return tool_registry is None and answer_generator is None and max_tool_calls == 3


def build_initial_state(user_query, chat_history, thread_id, run_id):
    return {
        "user_query": user_query,
        "chat_history": chat_history or [],
        "thread_id": thread_id,
        "run_id": run_id,
        "selected_tools": [],
        "tool_call_count": 0,
        "tool_results": {},
        "trace_events": make_trace("run_started", thread_id=thread_id, run_id=run_id),
    }


def collect_current_run_traces(trace_events, run_id):
    run_start_index = None

    for index, event in enumerate(trace_events):
        data = event.get("data", {})
        if event.get("step") == "run_started" and data.get("run_id") == run_id:
            run_start_index = index

    if run_start_index is None:
        return trace_events

    return trace_events[run_start_index:]


def run_langgraph_agent(
    user_query,
    chat_history=None,
    tool_registry=None,
    answer_generator=None,
    max_tool_calls=3,
    thread_id=None,
):
    """Run the LangGraph assistant and return the stable Agent response shape."""
    resolved_thread_id = thread_id or generate_thread_id()
    run_id = generate_run_id()

    if should_use_default_graph(tool_registry, answer_generator, max_tool_calls):
        graph = get_default_langgraph_agent()
    else:
        graph = build_langgraph_agent(
            tool_registry=tool_registry,
            answer_generator=answer_generator,
            max_tool_calls=max_tool_calls,
            checkpointer=InMemorySaver(),
        )

    initial_state: AgentState = build_initial_state(
        user_query,
        chat_history,
        resolved_thread_id,
        run_id,
    )
    final_state = graph.invoke(
        initial_state,
        config=build_graph_invoke_config(resolved_thread_id),
    )
    trace_events = collect_current_run_traces(final_state.get("trace_events", []), run_id)

    return build_response_from_state(final_state, trace_events)
