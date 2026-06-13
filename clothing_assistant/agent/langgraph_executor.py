"""LangGraph executor for the clothing assistant.

This module owns graph assembly, compilation, checkpoint configuration, and
runtime request metadata. Business node functions live in ``nodes.py``.
"""

from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from clothing_assistant.application.answer_service import (
    build_response_from_state,
    default_answer_generator,
)
from clothing_assistant.agent.nodes import (
    answer_generator_node,
    answer_validator_node,
    direct_answer_node,
    missing_info_gate_node,
    policy_fallback_node,
    rag_retriever_node,
    resolve_memory_node,
    retrieval_grader_node,
    route_after_direct_answer,
    route_after_missing_info,
    route_after_policy_fallback,
    route_after_structured_lookup,
    route_intent_node,
    structured_lookup_node,
    trace_logger_node,
    tool_budget_exhausted_node,
)
from clothing_assistant.agent.state import AgentState, make_trace
from clothing_assistant.agent.tool_registry import build_default_tool_registry


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
    graph.add_node("intent_router", route_intent_node)
    graph.add_node("context_resolver", resolve_memory_node)
    graph.add_node("direct_answer_gate", direct_answer_node)
    graph.add_node("missing_info_gate", missing_info_gate_node)
    graph.add_node(
        "structured_lookup",
        lambda state: structured_lookup_node(state, registry=registry, max_tool_calls=max_tool_calls),
    )
    graph.add_node("policy_fallback", policy_fallback_node)
    graph.add_node(
        "rag_retriever",
        lambda state: rag_retriever_node(state, registry=registry, max_tool_calls=max_tool_calls),
    )
    graph.add_node("retrieval_grader", retrieval_grader_node)
    graph.add_node(
        "answer_generator",
        lambda state: answer_generator_node(state, answer_generator=answer_generator),
    )
    graph.add_node("answer_validator", answer_validator_node)
    graph.add_node("trace_logger", trace_logger_node)
    graph.add_node(
        "tool_budget_exhausted",
        lambda state: tool_budget_exhausted_node(state, max_tool_calls=max_tool_calls),
    )

    graph.add_edge(START, "intent_router")
    graph.add_edge("intent_router", "context_resolver")
    graph.add_edge("context_resolver", "direct_answer_gate")
    graph.add_conditional_edges(
        "direct_answer_gate",
        lambda state: route_after_direct_answer(state, max_tool_calls=max_tool_calls),
        {
            "stop": "trace_logger",
            "budget_exhausted": "tool_budget_exhausted",
            "missing_info": "missing_info_gate",
        },
    )
    graph.add_conditional_edges(
        "missing_info_gate",
        lambda state: route_after_missing_info(state, max_tool_calls=max_tool_calls),
        {
            "stop": "trace_logger",
            "budget_exhausted": "tool_budget_exhausted",
            "structured_lookup": "structured_lookup",
        },
    )
    graph.add_conditional_edges(
        "structured_lookup",
        lambda state: route_after_structured_lookup(
            state,
            registry=registry,
            max_tool_calls=max_tool_calls,
        ),
        {
            "stop": "trace_logger",
            "policy_fallback": "policy_fallback",
            "budget_exhausted": "tool_budget_exhausted",
            "rag_retriever": "rag_retriever",
            "answer_generator": "answer_generator",
        },
    )
    graph.add_conditional_edges(
        "policy_fallback",
        lambda state: route_after_policy_fallback(state, max_tool_calls=max_tool_calls),
        {
            "stop": "trace_logger",
            "answer_generator": "answer_generator",
            "budget_exhausted": "tool_budget_exhausted",
        },
    )
    graph.add_edge("rag_retriever", "retrieval_grader")
    graph.add_edge("retrieval_grader", "answer_generator")
    graph.add_edge("answer_generator", "answer_validator")
    graph.add_edge("answer_validator", "trace_logger")
    graph.add_edge("tool_budget_exhausted", "trace_logger")
    graph.add_edge("trace_logger", END)

    return graph.compile(checkpointer=checkpointer)


def get_default_langgraph_agent():
    """Return the cached production graph compiled without cross-request state."""
    global _DEFAULT_LANGGRAPH_AGENT

    if _DEFAULT_LANGGRAPH_AGENT is None:
        _DEFAULT_LANGGRAPH_AGENT = build_langgraph_agent(checkpointer=None)

    return _DEFAULT_LANGGRAPH_AGENT


def should_use_default_graph(tool_registry, answer_generator, max_tool_calls):
    return tool_registry is None and answer_generator is None and max_tool_calls == 3


def build_initial_state(
    user_query,
    chat_history,
    thread_id,
    run_id,
    request_id=None,
    session_id=None,
    user_context=None,
    candidates=None,
):
    return {
        "user_query": user_query,
        "chat_history": chat_history or [],
        "request_id": request_id,
        "session_id": session_id,
        "thread_id": thread_id,
        "run_id": run_id,
        "user_context": user_context or {},
        "candidates": candidates or [],
        "selected_tools": [],
        "tool_call_count": 0,
        "tool_results": {},
        "trace_events": make_trace(
            "run_started",
            request_id=request_id,
            session_id=session_id,
            thread_id=thread_id,
            run_id=run_id,
        ),
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
    request_id=None,
    session_id=None,
    user_context=None,
    candidates=None,
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
        request_id=request_id,
        session_id=session_id,
        user_context=user_context,
        candidates=candidates,
    )
    final_state = graph.invoke(
        initial_state,
        config=build_graph_invoke_config(resolved_thread_id),
    )
    trace_events = collect_current_run_traces(final_state.get("trace_events", []), run_id)

    return build_response_from_state(final_state, trace_events)
