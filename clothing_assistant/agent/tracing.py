"""本地 trace 持久化。

trace_events 是学习和调试 Agent 的关键证据：它能告诉你一次请求经过了哪些阶段、
选中了哪些工具、在哪里早停。默认不写文件，只有打开环境变量时才落盘。
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from clothing_assistant.config_data import BASE_DIR


DEFAULT_TRACE_DIR = BASE_DIR / "traces"
SENSITIVE_TEXT_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^\s,;]+"),
]


def is_trace_to_file_enabled():
    """通过环境变量控制是否写 trace 文件，避免默认产生大量调试文件。"""
    return os.environ.get("AGENT_TRACE_TO_FILE", "").strip().lower() == "true"


def get_trace_dir():
    """允许用 AGENT_TRACE_DIR 覆盖默认 traces 目录，方便本地实验隔离。"""
    configured_dir = os.environ.get("AGENT_TRACE_DIR")

    if configured_dir:
        return Path(configured_dir)

    return DEFAULT_TRACE_DIR


def redact_sensitive_text(value):
    """Mask obvious secret-bearing fragments before optional local trace persistence."""
    if not isinstance(value, str):
        return value

    redacted = value
    for pattern in SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}[已隐藏]", redacted)

    return redacted


def redact_sensitive_values(value):
    """Recursively redact strings inside trace structures without changing their shape."""
    if isinstance(value, dict):
        return {key: redact_sensitive_values(item) for key, item in value.items()}

    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_sensitive_values(item) for item in value)

    return redact_sensitive_text(value)


def build_trace_record(state, trace_events):
    """只保存复盘需要的字段，不把完整 prompt 或大对象默认写进 trace。"""
    return redact_sensitive_values({
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_query": state["user_query"],
        "thread_id": state.get("thread_id"),
        "run_id": state.get("run_id"),
        "selected_tools": state.get("selected_tools", []),
        "tool_call_count": state.get("tool_call_count", 0),
        "stop_reason": state.get("stop_reason"),
        "answer": state.get("answer"),
        "trace_events": trace_events,
    })


def persist_trace_if_enabled(state, trace_events=None):
    """在启用时把一次 Agent 运行追加写入 jsonl trace 文件。"""
    if not is_trace_to_file_enabled():
        return None

    if trace_events is None:
        trace_events = state.get("trace_events", [])

    trace_dir = get_trace_dir()
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"agent_trace_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jsonl"

    with trace_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(build_trace_record(state, trace_events), ensure_ascii=False) + "\n")

    return str(trace_file)
