from fastapi.testclient import TestClient

from clothing_assistant.api import app as app_module
from clothing_assistant.domain.demand_intent_models import DemandIntentParseCandidate


VALID = DemandIntentParseCandidate.model_validate(
    {
        "schemaVersion": "1.0",
        "action": "MERGE",
        "slots": {"targetGender": "FEMALE"},
        "slotConfidence": {"targetGender": 0.93},
        "evidence": {
            "targetGender": [{"text": "女性", "source": "CURRENT_MESSAGE"}]
        },
        "needsClarification": False,
    }
)


class StubService:
    def __init__(self):
        self.received = None

    def parse(self, request):
        self.received = request
        return VALID


def request_body():
    return {
        "schemaVersion": "1.0",
        "requestId": "req-1",
        "sessionId": "session-1",
        "currentMessage": "女性穿搭",
        "currentDemand": {"targetGender": "FEMALE"},
        "deterministicPatch": {},
        "lockedSlots": [],
        "matchedFragments": [],
        "unresolvedText": "女性穿搭",
        "recentHistory": [],
        "pendingClarification": None,
    }


def test_internal_parse_endpoint_uses_auth_and_returns_aliases(monkeypatch):
    service = StubService()
    app_module.app.dependency_overrides[app_module.get_demand_intent_parse_service] = lambda: service
    monkeypatch.setattr(app_module, "is_internal_auth_required", lambda: False)
    try:
        response = TestClient(app_module.app).post(
            "/internal/demand-intent/parse", json=request_body()
        )
    finally:
        app_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["schemaVersion"] == "1.0"
    assert response.json()["slots"]["targetGender"] == "FEMALE"
    assert service.received["currentMessage"] == "女性穿搭"


def test_internal_parse_endpoint_rejects_missing_token(monkeypatch):
    monkeypatch.setattr(app_module, "is_internal_auth_required", lambda: True)
    monkeypatch.setattr(app_module, "get_internal_api_token", lambda: "secret")

    response = TestClient(app_module.app).post(
        "/internal/demand-intent/parse", json=request_body()
    )

    assert response.status_code == 401
    assert response.json()["error"] == "internal_auth_required"


def test_internal_parse_endpoint_requires_schema_and_current_demand(monkeypatch):
    monkeypatch.setattr(app_module, "is_internal_auth_required", lambda: False)
    body = request_body()
    body.pop("schemaVersion")
    body.pop("currentDemand")

    response = TestClient(app_module.app).post("/internal/demand-intent/parse", json=body)

    assert response.status_code == 422
