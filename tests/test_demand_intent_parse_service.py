import json

import pytest
from pydantic import ValidationError

from clothing_assistant.application.demand_intent_parse_service import (
    DemandIntentParseError,
    DemandIntentParseService,
)
from clothing_assistant.domain.demand_intent_models import DemandIntentParseCandidate


VALID_CANDIDATE = {
    "schemaVersion": "1.0",
    "action": "MERGE",
    "slots": {"targetGender": "FEMALE", "category": "OUTERWEAR"},
    "slotConfidence": {"targetGender": 0.93, "category": 0.88},
    "evidence": {
        "targetGender": [{"text": "女朋友", "source": "CURRENT_MESSAGE"}],
        "category": [{"text": "外套", "source": "CURRENT_MESSAGE"}],
    },
    "needsClarification": False,
    "clarificationSlot": None,
    "clarificationQuestion": None,
}


def test_candidate_rejects_string_evidence():
    payload = dict(VALID_CANDIDATE)
    payload["evidence"] = {"targetGender": ["女朋友"]}

    with pytest.raises(ValidationError):
        DemandIntentParseCandidate.model_validate(payload)


def test_candidate_rejects_extra_fields():
    payload = dict(VALID_CANDIDATE, invented=True)

    with pytest.raises(ValidationError):
        DemandIntentParseCandidate.model_validate(payload)


def test_candidate_requires_metadata_for_each_slot():
    payload = dict(VALID_CANDIDATE)
    payload["slotConfidence"] = {"targetGender": 0.93}

    with pytest.raises(ValidationError):
        DemandIntentParseCandidate.model_validate(payload)


def test_service_parses_plain_json_and_mentions_history_evidence_rule():
    captured = {}

    def invoke(messages):
        captured["messages"] = messages
        return json.dumps(VALID_CANDIDATE, ensure_ascii=False)

    result = DemandIntentParseService(invoke=invoke).parse(
        {
            "currentMessage": "给女朋友找外套",
            "recentHistory": [{"userQuery": "我喜欢成熟风", "assistantAnswer": "好的"}],
            "lockedSlots": [],
        }
    )

    assert result.slots.target_gender == "FEMALE"
    assert "ordinary history" in captured["messages"][0]["content"]
    assert "must not be evidence" in captured["messages"][0]["content"]


@pytest.mark.parametrize("content", ["```json\n{}\n```", "not-json"])
def test_service_rejects_non_plain_json(content):
    with pytest.raises(DemandIntentParseError):
        DemandIntentParseService(invoke=lambda _: content).parse(
            {"currentMessage": "女性穿搭", "recentHistory": [], "lockedSlots": []}
        )
