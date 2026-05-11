import json
import os
from datetime import datetime
from pathlib import Path

from clothing_rag_demo.config_data import BASE_DIR


DEFAULT_TRACE_DIR = BASE_DIR / "traces"

# 记录输入输出，方便调试
def is_trace_to_file_enabled():
    return os.environ.get("AGENT_TRACE_TO_FILE", "").strip().lower() == "true"


def get_trace_dir():
    configured_dir = os.environ.get("AGENT_TRACE_DIR")

    if configured_dir:
        return Path(configured_dir)

    return DEFAULT_TRACE_DIR


def build_trace_record(state):
    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_query": state.user_query,
        "selected_tools": state.selected_tools,
        "stop_reason": state.stop_reason,
        "answer": state.answer,
        "trace_events": state.trace_events,
    }


def persist_trace_if_enabled(state):
    if not is_trace_to_file_enabled():
        return None

    trace_dir = get_trace_dir()
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"agent_trace_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jsonl"

    with trace_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(build_trace_record(state), ensure_ascii=False) + "\n")

    return str(trace_file)
