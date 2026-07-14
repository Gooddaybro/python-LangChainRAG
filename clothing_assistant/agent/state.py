"""Agent 状态定义。

AgentState 从 dataclass 迁移到 TypedDict，这是 LangGraph 的原生状态类型。
LangGraph 用 TypedDict 做状态合并/持久化，比 dataclass 更适合图执行模型。

Sensitive request data remains available while the graph runs but is never
written to a checkpointer.
"""

from typing import Annotated, Any, Self, Sequence, TypedDict

from langgraph.channels import UntrackedValue
from langgraph.channels.base import MISSING


class UntrackedTraceEvents(UntrackedValue[list[dict[str, Any]]]):
    """Append trace events during a run without checkpointing their payloads."""

    def __init__(self, typ, guard: bool = False):
        super().__init__(typ, guard=guard)
        self.value: list[dict[str, Any]] = []

    def copy(self) -> Self:
        copied = self.__class__(self.typ, self.guard)
        copied.key = self.key
        copied.value = self.value.copy()
        return copied

    def checkpoint(self):
        return MISSING

    def from_checkpoint(self, checkpoint) -> Self:
        copied = self.__class__(self.typ, self.guard)
        copied.key = self.key
        return copied

    def update(self, values: Sequence[list[dict[str, Any]]]) -> bool:
        if not values:
            return False
        for events in values:
            self.value.extend(events)
        return True

    def get(self) -> list[dict[str, Any]]:
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
    intent_result: dict[str, Any]
    memory_result: Annotated[dict[str, Any], UntrackedValue]
    agent_query: Annotated[str, UntrackedValue]
    missing_info_result: dict[str, Any]
    structured_result: Annotated[dict[str, Any], UntrackedValue]
    accepted_chunks: Annotated[list[dict[str, Any]], UntrackedValue]
    rejected_chunks: Annotated[list[dict[str, Any]], UntrackedValue]
    retrieval_route: dict[str, Any]
    draft_answer: Annotated[str, UntrackedValue]
    validation_result: dict[str, Any]
    generation_attempts: int
    max_generation_attempts: int
    validation_feedback: Annotated[str, UntrackedValue]
    fallback_result: dict[str, Any]
    evidence_summary: Annotated[dict[str, Any], UntrackedValue]
    selected_tools: list[str]
    # tool_call_count 记录工具节点实际跑了几次，是死循环保护器。
    tool_call_count: int
    tool_results: Annotated[dict[str, Any], UntrackedValue]

    # 输出侧：answer 给用户看，final_prompt 和 stop_reason 给调试/评测看。
    answer: Annotated[str, UntrackedValue]
    final_prompt: Annotated[str, UntrackedValue]
    stop_reason: str

    trace_events: Annotated[list[dict[str, Any]], UntrackedTraceEvents]


def make_trace(step: str, **data: Any) -> list[dict[str, Any]]:
    """创建 trace 事件列表，供 mutate 函数返回。

    Learning: mutate 函数不再直接往 state 里 append，而是返回 trace 事件。
    由调用方（langgraph 节点）收集后统一返回给 LangGraph，通过 Annotated reducer 合并。
    这样避免了"mutate 函数 append 一次 + reducer 又 append 一次"的重复问题。
    """
    return [{"step": step, "data": data}]
