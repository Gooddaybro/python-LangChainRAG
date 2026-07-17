"""LangGraph executor for the clothing assistant.

This module owns graph assembly, compilation, checkpoint configuration, and
runtime request metadata. Business node functions live in ``nodes.py``.
"""

from dataclasses import dataclass
from queue import Empty, Queue
import threading
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.channels import UntrackedValue
from langgraph.graph import END, START, StateGraph

from clothing_assistant.application.answer_service import (
    build_answer_messages,
    build_final_prompt,
    build_response_from_state,
    default_answer_generator,
)
from clothing_assistant.api.streaming import SafeTokenBuffer, UnsafeStreamContent
from clothing_assistant.config_data import (
    get_checkpointer_backend,
    get_checkpointer_dsn,
    get_stream_safety_tail_chars,
)
from clothing_assistant.infrastructure.llm_client import DependencyError, stream_chat_content
from clothing_assistant.infrastructure.checkpointer import create_checkpointer_runtime
from clothing_assistant.agent.nodes import (
    answer_generator_node,
    answer_validator_node,
    direct_answer_node,
    fallback_answer_node,
    find_forbidden_rag_fact,
    has_candidate_backed_recommendation,
    missing_info_gate_node,
    policy_fallback_node,
    rag_retriever_node,
    resolve_memory_node,
    retrieval_grader_node,
    route_after_answer_validator,
    route_after_direct_answer,
    route_after_missing_info,
    route_after_policy_fallback,
    route_after_retrieval_grader,
    route_after_structured_lookup,
    route_intent_node,
    structured_lookup_node,
    trace_logger_node,
    tool_budget_exhausted_node,
)
from clothing_assistant.agent.state import AgentState, make_trace
from clothing_assistant.agent.tool_registry import build_default_tool_registry


_DEFAULT_LANGGRAPH_AGENT = None
_RUNTIME_CHECKPOINTER = None


@dataclass
class AgentStreamEvent:
    """Internal event translated to the stable Java-facing SSE contract."""

    kind: str
    content: str = ""
    result: dict | None = None
    code: str = ""


class StreamCancelled(RuntimeError):
    """Stop graph work after the request consumer disconnects."""


def initialize_runtime_checkpointer() -> Any:
    global _RUNTIME_CHECKPOINTER
    if _RUNTIME_CHECKPOINTER is None:
        _RUNTIME_CHECKPOINTER = create_checkpointer_runtime(
            get_checkpointer_backend(),
            get_checkpointer_dsn(),
        )
    return _RUNTIME_CHECKPOINTER.saver


def get_runtime_checkpointer() -> Any:
    return initialize_runtime_checkpointer()


def close_runtime_checkpointer() -> None:
    global _RUNTIME_CHECKPOINTER
    if _RUNTIME_CHECKPOINTER is not None:
        _RUNTIME_CHECKPOINTER.close()
        _RUNTIME_CHECKPOINTER = None


def generate_thread_id():
    return f"thread-{uuid4()}"


def generate_run_id():
    return f"run-{uuid4()}"


def resolve_thread_id(thread_id=None, session_id=None):
    if thread_id:
        return thread_id

    if session_id:
        return session_id

    return generate_thread_id()


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
    graph.add_node("fallback_answer", fallback_answer_node)
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
    graph.add_conditional_edges(
        "retrieval_grader",
        route_after_retrieval_grader,
        {
            "answer_generator": "answer_generator",
            "fallback_answer": "fallback_answer",
        },
    )
    graph.add_edge("answer_generator", "answer_validator")
    graph.add_conditional_edges(
        "answer_validator",
        route_after_answer_validator,
        {
            "trace_logger": "trace_logger",
            "answer_generator": "answer_generator",
            "fallback_answer": "fallback_answer",
        },
    )
    graph.add_edge("fallback_answer", "trace_logger")
    graph.add_edge("tool_budget_exhausted", "trace_logger")
    graph.add_edge("trace_logger", END)

    compiled_graph = graph.compile(checkpointer=checkpointer)
    # LangGraph checkpoints the raw input under __start__ before it reaches
    # AgentState's typed channels, so this channel must be untracked as well.
    compiled_graph.channels[START] = UntrackedValue(AgentState)
    compiled_graph.channels[START].key = START
    return compiled_graph


def get_default_langgraph_agent():
    """Return the cached graph with local checkpoint history for debug replay."""
    global _DEFAULT_LANGGRAPH_AGENT

    if _DEFAULT_LANGGRAPH_AGENT is None:
        _DEFAULT_LANGGRAPH_AGENT = build_langgraph_agent(checkpointer=InMemorySaver())

    return _DEFAULT_LANGGRAPH_AGENT


def should_use_default_graph(tool_registry, answer_generator, max_tool_calls):
    return tool_registry is None and answer_generator is None and max_tool_calls == 3


def build_run_state_defaults():
    return {
        "intent_result": {},
        "memory_result": {},
        "agent_query": "",
        "missing_info_result": {},
        "structured_result": {},
        "accepted_chunks": [],
        "rejected_chunks": [],
        "retrieval_route": {},
        "draft_answer": "",
        "validation_result": {},
        "fallback_result": {},
        "evidence_summary": {},
        "selected_tools": [],
        "tool_call_count": 0,
        "tool_results": {},
        "generation_attempts": 0,
        "max_generation_attempts": 2,
        "validation_feedback": "",
        "answer": "",
        "final_prompt": "",
        "stop_reason": "",
    }


def build_initial_state(
    user_query,
    chat_history,
    thread_id,
    run_id,
    request_id=None,
    session_id=None,
    user_context=None,
    candidates=None,
    demand_intent=None,
    allow_demo_catalog=False,
):
    return {
        **build_run_state_defaults(),
        "user_query": user_query,
        "chat_history": chat_history or [],
        "request_id": request_id,
        "session_id": session_id,
        "thread_id": thread_id,
        "run_id": run_id,
        "user_context": user_context or {},
        "candidates": candidates or [],
        "demand_intent": demand_intent or {},
        "allow_demo_catalog": allow_demo_catalog,
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
    demand_intent=None,
    use_cached_graph=False,
    allow_demo_catalog=False,
    checkpointer=None,
):
    """Run the LangGraph assistant and return the stable Agent response shape."""
    resolved_thread_id = resolve_thread_id(thread_id=thread_id, session_id=session_id)
    run_id = generate_run_id()

    if (
        use_cached_graph
        and checkpointer is None
        and should_use_default_graph(tool_registry, answer_generator, max_tool_calls)
    ):
        graph = get_default_langgraph_agent()
    else:
        graph = build_langgraph_agent(
            tool_registry=tool_registry,
            answer_generator=answer_generator,
            max_tool_calls=max_tool_calls,
            checkpointer=checkpointer or get_runtime_checkpointer(),
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
        demand_intent=demand_intent,
        allow_demo_catalog=allow_demo_catalog,
    )
    final_state = graph.invoke(
        initial_state,
        config=build_graph_invoke_config(resolved_thread_id),
        durability="exit",
    )
    trace_events = collect_current_run_traces(final_state.get("trace_events", []), run_id)

    return build_response_from_state(final_state, trace_events)


def stream_langgraph_agent(
    user_query,
    chat_history=None,
    tool_registry=None,
    max_tool_calls=3,
    thread_id=None,
    request_id=None,
    session_id=None,
    user_context=None,
    candidates=None,
    demand_intent=None,
    allow_demo_catalog=False,
    checkpointer=None,
    stop_requested=None,
    stream_content=None,
):
    """Run the existing graph while emitting safe provider fragments."""
    event_queue = Queue()
    stop_event = threading.Event()
    public_parts = []
    stream_content = stream_content or stream_chat_content
    external_stop = stop_requested or (lambda: False)

    def should_stop():
        return stop_event.is_set() or external_stop()

    def streaming_answer_generator(state):
        final_prompt = build_final_prompt(
            state["user_query"],
            state["intent_result"],
            state["memory_result"],
            state["tool_results"],
        )
        messages = build_answer_messages(final_prompt)
        pure_rag = bool(state.get("accepted_chunks")) and not has_candidate_backed_recommendation(state)
        validator = find_forbidden_rag_fact if pure_rag else lambda _: None
        buffer = SafeTokenBuffer(get_stream_safety_tail_chars(), validator)
        provider_stream = stream_content(messages, stop_requested=should_stop)

        try:
            for fragment in provider_stream:
                if should_stop():
                    raise StreamCancelled()
                try:
                    safe_fragments = buffer.push(fragment)
                except UnsafeStreamContent:
                    if public_parts:
                        raise
                    return buffer.text, final_prompt

                for safe_fragment in safe_fragments:
                    public_parts.append(safe_fragment)
                    event_queue.put(AgentStreamEvent(kind="token", content=safe_fragment))
        finally:
            close = getattr(provider_stream, "close", None)
            if close is not None:
                close()

        if should_stop():
            raise StreamCancelled()
        return buffer.text, final_prompt

    def worker():
        try:
            result = run_langgraph_agent(
                user_query,
                chat_history=chat_history,
                tool_registry=tool_registry,
                answer_generator=streaming_answer_generator,
                max_tool_calls=max_tool_calls,
                thread_id=thread_id,
                request_id=request_id,
                session_id=session_id,
                user_context=user_context,
                candidates=candidates,
                demand_intent=demand_intent,
                allow_demo_catalog=allow_demo_catalog,
                checkpointer=checkpointer,
            )
            if should_stop():
                return

            answer = result.get("answer", "")
            public_text = "".join(public_parts)
            if not answer.startswith(public_text):
                event_queue.put(AgentStreamEvent(kind="error", code="validation_failed"))
                return

            remaining = answer[len(public_text):]
            if remaining:
                public_parts.append(remaining)
                event_queue.put(AgentStreamEvent(kind="token", content=remaining))
            event_queue.put(AgentStreamEvent(kind="result", result=result))
        except StreamCancelled:
            pass
        except UnsafeStreamContent:
            event_queue.put(AgentStreamEvent(kind="error", code="validation_failed"))
        except DependencyError as error:
            event_queue.put(AgentStreamEvent(kind="error", code=error.reason))
        except Exception:
            event_queue.put(AgentStreamEvent(kind="error", code="internal_error"))
        finally:
            event_queue.put(AgentStreamEvent(kind="_end"))

    worker_thread = threading.Thread(target=worker, name="assistant-stream-worker")
    worker_thread.start()
    try:
        while True:
            try:
                event = event_queue.get(timeout=0.1)
            except Empty:
                if should_stop():
                    break
                yield AgentStreamEvent(kind="heartbeat")
                continue
            if event.kind == "_end":
                break
            yield event
    finally:
        stop_event.set()
        worker_thread.join()
