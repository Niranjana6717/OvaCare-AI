"""
Real, executed tests for app.logging_config — zero SQLAlchemy/FastAPI
imports (see its module docstring), so unlike most of this backend it runs
directly here. Covers the one thing that actually matters for a health app's
logging: sensitive fields never reach a log line unredacted.
"""
import io
import json
import logging
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.logging_config import JsonLogFormatter, log_structured, redact  # noqa: E402


class TestRedact(unittest.TestCase):
    def test_none_returns_empty_dict(self):
        self.assertEqual(redact(None), {})

    def test_password_and_tokens_are_redacted(self):
        data = {"password": "hunter2", "access_token": "abc.def.ghi", "refresh_token": "xyz"}
        result = redact(data)
        self.assertEqual(result["password"], "[redacted]")
        self.assertEqual(result["access_token"], "[redacted]")
        self.assertEqual(result["refresh_token"], "[redacted]")

    def test_raw_health_fields_are_redacted(self):
        data = {"raw_responses": {"age": 25}, "probability": 0.8, "explanation": {"factors": []}}
        result = redact(data)
        self.assertEqual(result["raw_responses"], "[redacted]")
        self.assertEqual(result["probability"], "[redacted]")
        self.assertEqual(result["explanation"], "[redacted]")

    def test_ordinary_fields_pass_through_unchanged(self):
        data = {"user_id": "abc-123", "status_code": 404, "path": "/api/v1/cycles"}
        self.assertEqual(redact(data), data)

    def test_key_matching_is_case_insensitive(self):
        result = redact({"PASSWORD": "x", "Access_Token": "y"})
        self.assertEqual(result["PASSWORD"], "[redacted]")
        self.assertEqual(result["Access_Token"], "[redacted]")

    def test_sensitive_key_is_kept_present_not_dropped(self):
        # A reader should be able to see THAT a sensitive field was there,
        # just not its value.
        result = redact({"password": "hunter2"})
        self.assertIn("password", result)


class TestJsonLogFormatterAndLogStructured(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test.ovacare.logging")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        self.stream = io.StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(JsonLogFormatter())
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def _emitted_json(self) -> dict:
        return json.loads(self.stream.getvalue().strip().splitlines()[-1])

    def test_emits_valid_json_with_expected_fields(self):
        log_structured(self.logger, logging.INFO, "auth.login_failed", ip_address="203.0.113.5")
        record = self._emitted_json()
        self.assertEqual(record["message"], "auth.login_failed")
        self.assertEqual(record["level"], "INFO")
        self.assertEqual(record["data"]["ip_address"], "203.0.113.5")

    def test_structured_data_is_redacted_in_the_actual_emitted_log_line(self):
        # End-to-end: this is the check that matters — not just that
        # redact() works in isolation, but that a real emitted log line
        # never contains the raw sensitive value anywhere in its text.
        log_structured(self.logger, logging.ERROR, "ml.inference_error", model_version="1.0.0", raw_responses={"age": 25})
        raw_line = self.stream.getvalue()
        self.assertNotIn("25", raw_line)  # the actual health value must not appear
        record = self._emitted_json()
        self.assertEqual(record["data"]["raw_responses"], "[redacted]")
        self.assertEqual(record["data"]["model_version"], "1.0.0")  # non-sensitive field preserved

    def test_exc_info_attaches_exception_and_is_not_logged_as_data(self):
        try:
            raise ValueError("boom")
        except ValueError:
            log_structured(self.logger, logging.ERROR, "ml.inference_error", exc_info=True, model_version="1.0.0")
        record = self._emitted_json()
        self.assertIn("exception", record)
        self.assertIn("ValueError", record["exception"])
        self.assertNotIn("exc_info", record.get("data", {}))


if __name__ == "__main__":
    unittest.main()
