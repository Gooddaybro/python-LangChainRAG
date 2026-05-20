"""LangGraph node functions for the clothing assistant graph.

The nodes keep the current business behavior stable while making the graph
structure explicit. Later production nodes can replace these wrappers one by
one without changing the graph assembly code.
"""

from clothing_rag_demo.agent.agent_executor import (
    apply_direct_answer_gate,
    apply_fallback_rag_tool,
    apply_policy_fallback_gate,
    default_answer_generator,
    generate_pipeline_answer,
    resolve_memory,
    route_intent,
)
from clothing_rag_demo.agent.state import make_trace
from clothing_rag_demo.agent.tool_registry import build_default_tool_registry, execute_tool_spec


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


def execute_tools_node(state, registry=None, max_tool_calls=3):
    registry = registry or build_default_tool_registry()
    traces = []

    for tool in registry:
        if not tool.should_run(state):
            continue

        if state.get("tool_call_count", 0) >= max_tool_calls:
            traces.extend(
                make_trace(
                    "tool_budget_reached",
                    max_tool_calls=max_tool_calls,
                    tool_call_count=state.get("tool_call_count", 0),
                )
            )
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


def fallback_rag_node(state, registry=None):
    registry = registry or build_default_tool_registry()
    traces = apply_fallback_rag_tool(state, registry)
    result = {"trace_events": traces}

    if state.get("selected_tools"):
        result["selected_tools"] = state["selected_tools"]
        result["tool_call_count"] = state["tool_call_count"]
        result["tool_results"] = state["tool_results"]

    return result


def generate_answer_node(state, answer_generator=None):
    answer_generator = answer_generator or default_answer_generator
    traces = generate_pipeline_answer(state, answer_generator)
    return {
        "answer": state["answer"],
        "final_prompt": state["final_prompt"],
        "stop_reason": state["stop_reason"],
        "trace_events": traces,
    }


def tool_budget_exhausted_node(state, max_tool_calls=3):
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


def route_after_direct_answer(state, max_tool_calls=3):
    if state.get("stop_reason"):
        return "stop"

    if state.get("tool_call_count", 0) >= max_tool_calls:
        return "budget_exhausted"

    return "execute_tools"


def route_after_policy_fallback(state, max_tool_calls=3):
    if state.get("stop_reason"):
        return "stop"

    if state.get("selected_tools"):
        return "generate_answer"

    if state.get("tool_call_count", 0) >= max_tool_calls:
        return "budget_exhausted"

    return "fallback_rag"
