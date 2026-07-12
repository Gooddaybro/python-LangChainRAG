import os
import unittest
from unittest.mock import patch

from clothing_assistant.config_data import is_debug_response_enabled


class DebugResponseConfigurationTests(unittest.TestCase):
    def test_debug_response_enabled_only_for_normalized_true(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_debug_response_enabled())

            os.environ["DEBUG_RESPONSE_ENABLED"] = "false"
            self.assertFalse(is_debug_response_enabled())

            os.environ["DEBUG_RESPONSE_ENABLED"] = " TrUe "
            self.assertTrue(is_debug_response_enabled())

            os.environ["DEBUG_RESPONSE_ENABLED"] = "1"
            self.assertFalse(is_debug_response_enabled())
