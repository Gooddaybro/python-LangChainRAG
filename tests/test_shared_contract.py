import json
import unittest
from pathlib import Path

from clothing_assistant.api.schemas import (
    ChatHistoryItem,
    DemandIntent,
    IntentConstraint,
    MatchedDimension,
    ProductCandidate,
    ProductRef,
    PythonChatRequest,
    PythonChatResponse,
    SubjectMeasurements,
    SuggestedAction,
    UserContext,
)


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "outfit-project-contract"
    / "contracts"
    / "java-python-chat"
    / "v1.fields.json"
)


class SharedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CONTRACT_PATH.exists():
            raise AssertionError(f"shared Java-Python contract is missing: {CONTRACT_PATH}")

        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def assert_model_fields_match_contract(self, model_class, field_set_name):
        actual_fields = set(model_class.model_fields)
        expected_fields = set(self.contract["field_sets"][field_set_name])

        self.assertEqual(actual_fields, expected_fields)

    def test_python_request_models_match_shared_contract(self):
        self.assert_model_fields_match_contract(PythonChatRequest, "python_chat_request")
        self.assert_model_fields_match_contract(ChatHistoryItem, "chat_history_item")
        self.assert_model_fields_match_contract(UserContext, "user_context")
        self.assert_model_fields_match_contract(ProductCandidate, "product_candidate")
        self.assert_model_fields_match_contract(DemandIntent, "demand_intent")
        self.assert_model_fields_match_contract(SubjectMeasurements, "subject_measurements")
        self.assert_model_fields_match_contract(IntentConstraint, "intent_constraint")

    def test_python_response_models_match_shared_contract(self):
        self.assert_model_fields_match_contract(PythonChatResponse, "python_chat_response")
        self.assert_model_fields_match_contract(ProductRef, "product_ref")
        self.assert_model_fields_match_contract(MatchedDimension, "matched_dimension")
        self.assert_model_fields_match_contract(SuggestedAction, "suggested_action")

    def test_v3_demand_intent_parses_and_serializes_constraints(self):
        demand_intent = DemandIntent.model_validate(
            {
                "version": "demand-intent-v3",
                "requestType": "OUTFIT_ADVICE",
                "requestedCapabilities": ["RECOMMENDATION"],
                "hardFilters": [
                    {
                        "id": "turn-7-category",
                        "field": "category",
                        "operator": "EQUALS",
                        "values": ["外套"],
                        "strength": "HARD",
                        "origin": "USER_EXPLICIT",
                        "originTurnId": "turn-7",
                        "derivedFromConstraintId": None,
                        "scope": "CURRENT_SESSION",
                        "weight": None,
                    }
                ],
                "softPreferences": [
                    {
                        "id": "turn-7-style",
                        "field": "style",
                        "operator": "CONTAINS",
                        "values": ["通勤"],
                        "strength": "SOFT",
                        "origin": "USER_EXPLICIT",
                        "originTurnId": "turn-7",
                        "derivedFromConstraintId": None,
                        "scope": "CURRENT_SESSION",
                        "weight": 0.8,
                    }
                ],
                "subjectMeasurements": {
                    "heightCm": 168,
                    "weightKg": 55,
                    "originalText": "168cm 55kg",
                    "normalizedFrom": "METRIC",
                    "subject": "SELF",
                    "scope": "CURRENT_SESSION",
                    "source": "USER_EXPLICIT",
                },
            }
        )

        serialized = demand_intent.model_dump(exclude_none=True)

        self.assertEqual(serialized["hardFilters"][0]["values"], ["外套"])
        self.assertEqual(serialized["softPreferences"][0]["weight"], 0.8)
        self.assertEqual(serialized["subjectMeasurements"]["heightCm"], 168)

    def test_product_ref_parses_and_serializes_outfit_role(self):
        product_ref = ProductRef.model_validate(
            {
                "spu_id": 1001,
                "sku_id": 2001,
                "reason": "适合作为通勤外搭。",
                "rank_score": 0.96,
                "matched_dimensions": [],
                "outfit_role": "OUTER",
            }
        )

        self.assertEqual(product_ref.model_dump()["outfit_role"], "OUTER")
