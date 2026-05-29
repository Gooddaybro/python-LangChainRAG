"""工具注册表。

这里把"什么时候能用某个工具"和"怎么调用这个工具"集中声明。
Learning: 这是从 if/else 调度走向 LangGraph Tool Node 的过渡层。
"""

from dataclasses import dataclass
from typing import Any, Callable

from clothing_assistant.agent.router import (
    INTENT_INVENTORY_CHECK,
    INTENT_POLICY_QA,
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
    has_measurement_signal,
)
from clothing_assistant.agent.state import AgentState, make_trace
from clothing_assistant.tools.policy_tool import run_policy_tool
from clothing_assistant.tools.rag_tool import run_rag_tool
from clothing_assistant.tools.size_tool import run_size_tool

# ToolRunner 负责执行工具；ToolPredicate 负责判断当前 State 是否需要这个工具。
ToolRunner = Callable[[AgentState], dict[str, Any]]
ToolPredicate = Callable[[AgentState], bool]

# 这些意图优先依赖商品知识库，所以默认先走 RAG。
RAG_FIRST_INTENTS = {
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_INVENTORY_CHECK,
}
PRODUCT_CONTEXT_WORDS = ["这件", "衣服", "商品", "T恤", "外套", "适合", "面料", "材质"]
SIZE_CONTEXT_WORDS = ["尺码", "码", "紧", "大", "小", "宽松", "合身", "适合我", "穿"]


@dataclass(frozen=True)
class ToolSpec:
    """一个工具的声明式说明。

    name/result_key 用于追踪和写回 State，should_run/run 则把选择和执行分开。
    """

    name: str
    result_key: str
    should_run: ToolPredicate
    run: ToolRunner
    output_description: str


def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def should_run_policy_tool(state):
    return state["intent_result"]["intent"] == INTENT_POLICY_QA


def should_run_rag_tool(state):
    intent = state["intent_result"]["intent"]

    if intent in RAG_FIRST_INTENTS:
        return True

    return intent == INTENT_SIZE_RECOMMENDATION and contains_any(
        state["user_query"],
        PRODUCT_CONTEXT_WORDS,
    )


def should_run_size_tool(state):
    intent = state["intent_result"]["intent"]
    used_history = state["memory_result"]["used_history"]

    if intent == INTENT_SIZE_RECOMMENDATION:
        return True

    if has_measurement_signal(state["user_query"]):
        return True

    # 用户追问"宽松一点"时，当前句子可能没有身高体重；
    # 如果 memory_tool 找到了历史尺码问题，这里仍然允许调用尺码工具。
    if used_history.get("measurements_query") and contains_any(state["user_query"], SIZE_CONTEXT_WORDS):
        return True

    return False


def build_default_tool_registry(
    policy_runner=run_policy_tool,
    rag_runner=run_rag_tool,
    size_runner=run_size_tool,
):
    """构建默认工具表。

    runner 参数支持测试注入 fake tools，避免评测时依赖真实向量库或大模型。
    """

    def run_policy(state):
        return policy_runner(state["agent_query"])

    def run_rag(state):
        return rag_runner(
            state["agent_query"],
            query_type=state["intent_result"]["query_type"],
        )

    def run_size(state):
        return size_runner(state["user_query"], chat_history=state["chat_history"])

    return [
        ToolSpec(
            name="policy_tool",
            result_key="policy_tool",
            should_run=should_run_policy_tool,
            run=run_policy,
            output_description="退换货、物流、售后政策来源检查和兜底。",
        ),
        ToolSpec(
            name="rag_tool",
            result_key="rag_tool",
            should_run=should_run_rag_tool,
            run=run_rag,
            output_description="商品知识库检索。",
        ),
        ToolSpec(
            name="size_tool",
            result_key="size_tool",
            should_run=should_run_size_tool,
            run=run_size,
            output_description="尺码规则匹配。",
        ),
    ]


def matching_tool_names(state, registry):
    return [tool.name for tool in registry if tool.should_run(state)]


def find_tool(registry, name):
    for tool in registry:
        if tool.name == name:
            return tool

    return None


def summarize_tool_result(result):
    """把工具结果压缩成 trace 友好的摘要，避免 debug log 过长。"""
    if not isinstance(result, dict):
        return {"type": type(result).__name__}

    summary = {}

    for key in ["source_count", "has_policy_source", "recommended_size", "retrieval_query"]:
        if key in result:
            summary[key] = result[key]

    if "retrieved_chunks" in result:
        summary["retrieved_chunk_count"] = len(result["retrieved_chunks"])

    return summary


def execute_tool_spec(state, tool):
    """执行一个 ToolSpec，把结果写回 State，并返回 trace_events 列表。

    Learning: 返回 trace_events 而不是直接往 state 里 append，
    是为了配合 LangGraph 的 Annotated reducer，避免 trace 事件重复。
    """
    state["selected_tools"].append(tool.name)
    state["tool_call_count"] += 1
    traces = make_trace("tool_selected", tool=tool.name, tool_call_count=state["tool_call_count"])
    result = tool.run(state)
    state["tool_results"][tool.result_key] = result
    traces.extend(make_trace("tool_result", tool=tool.name, result_summary=summarize_tool_result(result)))
    return traces
