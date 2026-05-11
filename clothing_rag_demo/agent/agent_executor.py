from langchain_core.messages import HumanMessage, SystemMessage

from clothing_rag_demo.agent.router import (
    INTENT_CHAT,
    INTENT_INVENTORY_CHECK,
    INTENT_POLICY_QA,
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
    INTENT_UNKNOWN,
    has_measurement_signal,
    intent_router,
)
from clothing_rag_demo.rag import get_chat_model
from clothing_rag_demo.tools.memory_tool import run_memory_tool
from clothing_rag_demo.tools.policy_tool import run_policy_tool
from clothing_rag_demo.tools.rag_tool import run_rag_tool
from clothing_rag_demo.tools.size_tool import run_size_tool


RAG_FIRST_INTENTS = {
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_INVENTORY_CHECK,
}

PRODUCT_CONTEXT_WORDS = ["这件", "衣服", "商品", "T恤", "外套", "适合", "面料", "材质"]
SIZE_CONTEXT_WORDS = ["尺码", "码", "紧", "大", "小", "宽松", "合身", "适合我", "穿"]


def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def should_call_rag_tool(user_query, intent_result):
    intent = intent_result["intent"]

    if intent in RAG_FIRST_INTENTS:
        return True

    # 尺码问题如果提到“这件衣服/商品属性”，先查商品知识，再补尺码工具。
    return intent == INTENT_SIZE_RECOMMENDATION and contains_any(user_query, PRODUCT_CONTEXT_WORDS)


def should_call_size_tool(user_query, intent_result, memory_result):
    intent = intent_result["intent"]
    used_history = memory_result["used_history"]

    if intent == INTENT_SIZE_RECOMMENDATION:
        return True

    if has_measurement_signal(user_query):
        return True

    if used_history.get("measurements_query") and contains_any(user_query, SIZE_CONTEXT_WORDS):
        return True

    return False


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


def build_direct_answer(user_query, intent_result):
    if intent_result["intent"] == INTENT_CHAT:
        return "我是服装导购助手，可以帮你做尺码推荐、颜色搭配、洗涤养护和基础商品咨询。"

    if intent_result["intent"] == INTENT_UNKNOWN:
        return "这个问题我暂时无法准确判断。你可以补充想咨询的是尺码、颜色、洗涤、库存还是售后政策。"

    return None


def run_agent(user_query, chat_history=None):
    chat_history = chat_history or []
    intent_result = intent_router(user_query)
    memory_result = run_memory_tool(user_query, chat_history, intent_result=intent_result)
    selected_tools = []
    tool_results = {}
    agent_query = build_agent_query(user_query, memory_result)

    direct_answer = build_direct_answer(user_query, intent_result)

    if direct_answer:
        final_prompt = "direct_answer，不调用大模型。"
        return build_agent_response(
            direct_answer,
            user_query,
            intent_result,
            selected_tools,
            memory_result,
            tool_results,
            final_prompt,
        )

    if intent_result["intent"] == INTENT_POLICY_QA:
        selected_tools.append("policy_tool")
        tool_results["policy_tool"] = run_policy_tool(agent_query)

        if not tool_results["policy_tool"]["has_policy_source"]:
            return build_agent_response(
                tool_results["policy_tool"]["policy_answer"],
                user_query,
                intent_result,
                selected_tools,
                memory_result,
                tool_results,
                "policy_tool 无政策来源，直接兜底。",
            )

    if should_call_rag_tool(user_query, intent_result):
        selected_tools.append("rag_tool")
        tool_results["rag_tool"] = run_rag_tool(
            agent_query,
            query_type=intent_result["query_type"],
        )

    if should_call_size_tool(user_query, intent_result, memory_result):
        selected_tools.append("size_tool")
        tool_results["size_tool"] = run_size_tool(user_query, chat_history=chat_history)

    if not selected_tools:
        selected_tools.append("rag_tool")
        tool_results["rag_tool"] = run_rag_tool(agent_query, query_type=intent_result["query_type"])

    answer, final_prompt = generate_final_answer(
        user_query,
        intent_result,
        memory_result,
        tool_results,
    )

    return build_agent_response(
        answer,
        user_query,
        intent_result,
        selected_tools,
        memory_result,
        tool_results,
        final_prompt,
    )


def build_agent_response(
    answer,
    user_query,
    intent_result,
    selected_tools,
    memory_result,
    tool_results,
    final_prompt,
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
