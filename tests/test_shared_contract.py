import json
import unittest
from pathlib import Path

from clothing_assistant.api.schemas import (
    ChatHistoryItem,
    ProductCandidate,
    ProductRef,
    PythonChatRequest,
    PythonChatResponse,
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

    def test_python_response_models_match_shared_contract(self):
        self.assert_model_fields_match_contract(PythonChatResponse, "python_chat_response")
        self.assert_model_fields_match_contract(ProductRef, "product_ref")
        self.assert_model_fields_match_contract(SuggestedAction, "suggested_action")
