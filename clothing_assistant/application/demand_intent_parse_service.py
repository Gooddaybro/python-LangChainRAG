"""Parse ambiguous shopping language into a strictly validated candidate patch."""

import json
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from clothing_assistant.domain.demand_intent_models import DemandIntentParseCandidate
from clothing_assistant.infrastructure.llm_client import DependencyError, invoke_chat_content


SYSTEM_PROMPT = """You extract only shopping-demand slot changes from the current message.
Return one plain JSON object matching schemaVersion 1.0; never use Markdown fences.
Use only MERGE or CLARIFY and uppercase canonical enum values.
Omit slots that the current turn does not change; never use an empty array to mean unchanged.
Evidence must be an exact quotation with source CURRENT_MESSAGE or PENDING_CLARIFICATION.
Recent ordinary history may help understand pronouns and context, but ordinary history must not be evidence.
Never override lockedSlots. Ask one concise clarification when a hard condition is uncertain.
CLARIFY must use empty slots, slotConfidence and evidence, and put any candidate in
clarificationCandidateValue. MERGE must set needsClarification false and all clarification fields null.
"""


class DemandIntentParseError(RuntimeError):
    """Safe protocol error raised when the model violates the parse contract."""


class DemandIntentParseService:
    def __init__(self, invoke: Callable[[list[dict[str, str]]], str] | None = None):
        self._invoke = invoke or invoke_chat_content

    def parse(self, request: dict[str, Any]) -> DemandIntentParseCandidate:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(request, ensure_ascii=False, separators=(",", ":")),
            },
        ]
        try:
            raw = self._invoke(messages)
            if not isinstance(raw, str) or raw.lstrip().startswith("```"):
                raise ValueError("response is not plain JSON")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("response root must be an object")
            return DemandIntentParseCandidate.model_validate(payload)
        except (
            ValueError,
            TypeError,
            json.JSONDecodeError,
            ValidationError,
            DependencyError,
        ) as error:
            raise DemandIntentParseError("invalid demand intent parse response") from error
