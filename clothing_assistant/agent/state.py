"""Agent 状态定义。

AgentState 从 dataclass 迁移到 TypedDict，这是 LangGraph 的原生状态类型。
LangGraph 用 TypedDict 做状态合并/持久化，比 dataclass 更适合图执行模型。

Learning: Annotated[list, operator.add] 是 LangGraph 的 Reducer 机制。
它告诉 LangGraph："遇到这个字段时，不要覆盖，请把新数据追加到老数据后面。"
这样每个节点提交的 trace_events 都会被保留，形成完整的心路历程。
"""

from collections.abc import Sequence
from typing import Annotated, Any, TypedDict

from langgraph.channels import UntrackedValue
from langgraph.channels.base import BaseChannel, MISSING


class UntrackedTraceEvents(BaseChannel[list[dict[str, Any]], list[dict[str, Any]], None]):
    """Append trace updates during a run without writing them to checkpoints."""

    __slots__ = ("value",)

    def __init__(self) -> None:
        super().__init__(list[dict[str, Any]])
        self.value: list[dict[str, Any]] = []

    @property
    def ValueType(self):
        return self.typ

    @property
    def UpdateType(self):
        return self.typ

    def copy(self):
        copied = self.__class__()
        copied.key = self.key
        copied.value = list(self.value)
        return copied

    def checkpoint(self):
        return MISSING

    def from_checkpoint(self, checkpoint):
        restored = self.__class__()
        restored.key = self.key
        return restored

    def update(self, values: Sequence[list[dict[str, Any]]]) -> bool:
        if not values:
            return False
        for value in values:
            self.value.extend(value)
        return True

    def get(self):
        return self.value

    def is_available(self) -> bool:
        return True


class AgentState(TypedDict, total=False):
    """一次 Agent 请求在 LangGraph 图中流转的状态容器。

    total=False 表示所有字段都是可选的，LangGraph 节点可以只返回自己修改的字段。
    """

    # 输入侧：用户问题和可选历史。
    user_query: Annotated[str, UntrackedValue]
    chat_history: Annotated[list[dict[str, Any]], UntrackedValue]
    request_id: str
    session_id: str
    thread_id: str
    run_id: str
    user_context: Annotated[dict[str, Any], UntrackedValue]
    candidates: Annotated[list[dict[str, Any]], UntrackedValue]
    demand_intent: Annotated[dict[str, Any], UntrackedValue]
    allow_demo_catalog: bool

    # 中间结果：每个节点只负责填充自己产生的数据。
    intent_result: Annotated[dict[str, Any], UntrackedValue]
    memory_result: Annotated[dict[str, Any], UntrackedValue]
    agent_query: Annotated[str, UntrackedValue]
    missing_info_result: Annotated[dict[str, Any], UntrackedValue]
    structured_result: Annotated[dict[str, Any], UntrackedValue]
    accepted_chunks: Annotated[list[dict[str, Any]], UntrackedValue]
    rejected_chunks: Annotated[list[dict[str, Any]], UntrackedValue]
    retrieval_route: Annotated[dict[str, Any], UntrackedValue]
    draft_answer: Annotated[str, UntrackedValue]
    validation_result: Annotated[dict[str, Any], UntrackedValue]
    generation_attempts: int
    max_generation_attempts: int
    validation_feedback: Annotated[str, UntrackedValue]
    fallback_result: Annotated[dict[str, Any], UntrackedValue]
    evidence_summary: Annotated[dict[str, Any], UntrackedValue]
    selected_tools: list[str]
    # tool_call_count 记录工具节点实际跑了几次，是死循环保护器。
    tool_call_count: int
    tool_results: Annotated[dict[str, Any], UntrackedValue]

    # 输出侧：answer 给用户看，final_prompt 和 stop_reason 给调试/评测看。
    answer: Annotated[str, UntrackedValue]
    final_prompt: Annotated[str, UntrackedValue]
    stop_reason: str

    # Annotated[list, operator.add] 是 Reducer：多个节点提交的 trace 会自动追加合并。
    # 节点返回 {"trace_events": [新事件]}，LangGraph 会执行 老数据 + 新数据。
    trace_events: Annotated[list[dict[str, Any]], UntrackedTraceEvents()]


def make_trace(step: str, **data: Any) -> list[dict[str, Any]]:
    """创建 trace 事件列表，供 mutate 函数返回。

    Learning: mutate 函数不再直接往 state 里 append，而是返回 trace 事件。
    由调用方（langgraph 节点）收集后统一返回给 LangGraph，通过 Annotated reducer 合并。
    这样避免了"mutate 函数 append 一次 + reducer 又 append 一次"的重复问题。
    """
    return [{"step": step, "data": data}]
