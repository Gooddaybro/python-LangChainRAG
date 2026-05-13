from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """一次 Agent 请求在 pipeline 中流转的状态容器。

    Learning: 这就是手写 MVP 版本的“圆盘状态”。后续迁移 LangGraph 时，
    这些字段会自然对应到图里的 State。
    """

    # 输入侧：用户问题和可选历史，是一次运行的真实数据来源。
    user_query: str
    chat_history: list[dict[str, Any]] = field(default_factory=list)

    # 中间结果：每个 pipeline 阶段只负责填充自己产生的数据。
    intent_result: dict[str, Any] | None = None
    memory_result: dict[str, Any] | None = None
    agent_query: str | None = None
    selected_tools: list[str] = field(default_factory=list)
    # Learning: selected_tools 记录“调了哪些工具”，tool_call_count 记录“工具节点实际跑了几次”。
    # 后续 LangGraph 加入重试/循环时，这个计数就是最小的死循环保护器。
    tool_call_count: int = 0
    tool_results: dict[str, Any] = field(default_factory=dict)

    # 输出侧：answer 给用户看，final_prompt 和 stop_reason 给调试/评测看。
    answer: str | None = None
    final_prompt: str | None = None
    stop_reason: str | None = None
    trace_events: list[dict[str, Any]] = field(default_factory=list)

    def add_trace(self, step: str, **data: Any) -> None:
        """记录本地调试事件，帮助你复盘 Agent 每一步为什么这么走。"""
        self.trace_events.append(
            {
                "step": step,
                "data": data,
            }
        )
