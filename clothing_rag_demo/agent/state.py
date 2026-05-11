from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """State container for one agent run."""

    user_query: str
    chat_history: list[dict[str, Any]] = field(default_factory=list)
    intent_result: dict[str, Any] | None = None
    memory_result: dict[str, Any] | None = None
    agent_query: str | None = None
    selected_tools: list[str] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)
    answer: str | None = None
    final_prompt: str | None = None
    stop_reason: str | None = None
    trace_events: list[dict[str, Any]] = field(default_factory=list)

    def add_trace(self, step: str, **data: Any) -> None:
        self.trace_events.append(
            {
                "step": step,
                "data": data,
            }
        )
