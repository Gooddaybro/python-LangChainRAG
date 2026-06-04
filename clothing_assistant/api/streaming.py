"""SSE helpers for the Java-facing assistant streaming endpoint."""

import json
from collections.abc import Iterable
from typing import Any


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    """Serialize one SSE event with a single-line JSON data payload."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def iter_answer_chunks(answer: str, chunk_size: int = 12) -> Iterable[str]:
    """Split final answer text into stable display chunks for SSE token events."""
    if not answer:
        return []

    for index in range(0, len(answer), chunk_size):
        yield answer[index:index + chunk_size]
 #   return [answer[index:index + chunk_size] for index in range(0, len(answer), chunk_size)]


def get_agent_intent(agent_result: dict[str, Any]) -> str:
    """Read the stable intent value from the existing agent debug payload."""
    debug = agent_result.get("debug") or {}
    intent_result = debug.get("intent_result") or {}
    return intent_result.get("intent") or "unknown"


def build_stream_done_payload(agent_result: dict[str, Any], request_id: str) -> dict[str, Any]:
    """Build the Python-to-Java done payload defined by the shared v1 contract."""
    return {
        "request_id": request_id,
        "answer": agent_result.get["answer",""],
        "intent": get_agent_intent(agent_result),
        "product_refs": [],
    }


def iter_stream_events(agent_result: dict[str, Any], request_id: str) -> Iterable[str]:
    """Yield token events followed by the final done event."""
    answer = agent_result.get("answer") or ""
    for chunk in iter_answer_chunks(answer):
        yield format_sse_event("token", {"content": chunk})

    yield format_sse_event("done", build_stream_done_payload(agent_result, request_id))


def build_error_event(code: str, message: str) -> str:
    """Build a safe SSE error event without exposing internal exception details."""
    return format_sse_event("error", {"code": code, "message": message})
