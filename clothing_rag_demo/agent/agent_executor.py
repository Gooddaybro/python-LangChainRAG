from langchain_core.messages import HumanMessage, SystemMessage

from clothing_rag_demo.agent.router import (
    INTENT_CHAT,
    INTENT_POLICY_QA,
    INTENT_UNKNOWN,
    intent_router,
)
from clothing_rag_demo.agent.state import AgentState
from clothing_rag_demo.agent.tool_registry import (
    build_default_tool_registry,
    execute_tool_spec,
    find_tool,
)
from clothing_rag_demo.agent.tracing import persist_trace_if_enabled
from clothing_rag_demo.rag import get_chat_model
from clothing_rag_demo.tools.memory_tool import run_memory_tool

# pipeline 调度转动

def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def build_agent_query(user_query, memory_result):
    if memory_result["need_history"]:
        return memory_result["memory_query"]

    return user_query


def format_chunks(chunks):
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
5. 不要输出 debug JSON，只输出给用户看的答案。
""".strip()


def generate_final_answer(user_query, intent_result, memory_result, tool_results):
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
        state.user_query,
        state.intent_result,
        state.memory_result,
        state.tool_results,
    )


def build_direct_answer(user_query, intent_result):
    if intent_result["intent"] == INTENT_CHAT:
        return "我是服装导购助手，可以帮你做尺码推荐、颜色搭配、洗涤养护和基础商品咨询。"

    if intent_result["intent"] == INTENT_UNKNOWN:
        return "这个问题我暂时无法准确判断。你可以补充想咨询的是尺码、颜色、洗涤、库存还是售后政策。"

    return None


def route_intent(state):
    state.intent_result = intent_router(state.user_query)
    state.add_trace(
        "route_intent",
        intent=state.intent_result["intent"],
        query_type=state.intent_result["query_type"],
        need_history=state.intent_result["need_history"],
    )


def resolve_memory(state):
    state.memory_result = run_memory_tool(
        state.user_query,
        state.chat_history,
        intent_result=state.intent_result,
    )
    state.agent_query = build_agent_query(state.user_query, state.memory_result)
    state.add_trace(
        "resolve_memory",
        need_history=state.memory_result["need_history"],
        ignored_history_reason=state.memory_result["ignored_history_reason"],
    )


def apply_direct_answer_gate(state):
    direct_answer = build_direct_answer(state.user_query, state.intent_result)

    if not direct_answer:
        return False

    state.answer = direct_answer
    state.final_prompt = "direct_answer，不调用大模型。"
    state.stop_reason = "direct_answer"
    state.add_trace("direct_answer", intent=state.intent_result["intent"])
    return True


def execute_matching_tools(state, tool_registry):
    for tool in tool_registry:
        if tool.should_run(state):
            execute_tool_spec(state, tool)


def apply_policy_fallback_gate(state):
    policy_result = state.tool_results.get("policy_tool")

    if not policy_result:
        return False

    if policy_result["has_policy_source"]:
        return False

    state.answer = policy_result["policy_answer"]
    state.final_prompt = "policy_tool 无政策来源，直接兜底。"
    state.stop_reason = "policy_fallback"
    state.add_trace("policy_fallback", reason=policy_result.get("reason"))
    return True


def apply_fallback_rag_tool(state, tool_registry):
    if state.selected_tools:
        return

    rag_tool = find_tool(tool_registry, "rag_tool")

    if not rag_tool:
        return

    state.add_trace("fallback_tool", tool="rag_tool")
    execute_tool_spec(state, rag_tool)


def generate_pipeline_answer(state, answer_generator):
    state.answer, state.final_prompt = answer_generator(state)
    state.stop_reason = "final_answer"
    state.add_trace("answer_generated", stop_reason=state.stop_reason)


def build_response_from_state(state):
    persist_trace_if_enabled(state)
    return build_agent_response(
        state.answer,
        state.user_query,
        state.intent_result,
        state.selected_tools,
        state.memory_result,
        state.tool_results,
        state.final_prompt,
        stop_reason=state.stop_reason,
        trace_events=state.trace_events,
    )


def run_agent(user_query, chat_history=None, tool_registry=None, answer_generator=None):
    state = AgentState(
        user_query=user_query,
        chat_history=chat_history or [],
    )
    registry = tool_registry or build_default_tool_registry()
    answer_generator = answer_generator or default_answer_generator

    route_intent(state)
    resolve_memory(state)

    if apply_direct_answer_gate(state):
        return build_response_from_state(state)

    execute_matching_tools(state, registry)

    if apply_policy_fallback_gate(state):
        return build_response_from_state(state)

    apply_fallback_rag_tool(state, registry)
    generate_pipeline_answer(state, answer_generator)

    return build_response_from_state(state)


def build_agent_response(
        answer,
        user_query,
        intent_result,
        selected_tools,
        memory_result,
        tool_results,
        final_prompt,
        stop_reason=None,
        trace_events=None,
):
    rag_result = tool_results.get("rag_tool") or {}

    return {
        "answer": answer,
        "debug": {
            "user_query": user_query,
            "intent_result": intent_result,
            "selected_tools": selected_tools,
            "used_history": memory_result["used_history"],
            "ignored_history_reason": memory_result["ignored_history_reason"],
            "retrieval_query": rag_result.get("retrieval_query"),
            "retrieved_chunks": rag_result.get("retrieved_chunks", []),
            "tool_results": tool_results,
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
