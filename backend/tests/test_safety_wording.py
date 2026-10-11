"""
Clinical safety wording tests (requirement #90, tests 1 & 2).

Run with: python3 -m unittest backend.tests.test_safety_wording -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.safety.wording import (  # noqa: E402
    MEDICAL_DISCLAIMER,
    SCREENING_RESULT_TEXT,
    UnsafeWordingError,
    assert_safe_wording,
)


class TestScreeningResultWording(unittest.TestCase):
    def test_lower_indication_never_says_no_pcos(self):
        """Test 1 (requirement #90): a low screening result must never
        display 'No PCOS.'"""
        text = SCREENING_RESULT_TEXT["lower_indication"].lower()
        self.assertNotIn("no pcos", text)
        self.assertNotIn("you do not have pcos", text)
        self.assertNotIn("you don't have pcos", text)
        # And it must not imply exclusion of other conditions either.
        self.assertIn("does not rule out", text)

    def test_higher_indication_never_says_you_have_pcos(self):
        """Test 2 (requirement #90): a high screening result must never
        display 'You have PCOS.'"""
        text = SCREENING_RESULT_TEXT["higher_indication"].lower()
        self.assertNotIn("you have pcos", text)
        self.assertIn("may warrant further discussion", text)

    def test_insufficient_data_text_does_not_guess(self):
        text = SCREENING_RESULT_TEXT["insufficient_data"].lower()
        self.assertNotIn("pcos", text)  # says nothing about outcome at all
        self.assertIn("don't have enough validated information", text)

    def test_disclaimer_present_and_explicit(self):
        self.assertIn("does not diagnose pcos", MEDICAL_DISCLAIMER.lower())


class TestAssertSafeWording(unittest.TestCase):
    def test_rejects_direct_diagnostic_claim(self):
        with self.assertRaises(UnsafeWordingError):
            assert_safe_wording("You have PCOS.")

    def test_rejects_false_reassurance(self):
        with self.assertRaises(UnsafeWordingError):
            assert_safe_wording("You do not have PCOS.")
        with self.assertRaises(UnsafeWordingError):
            assert_safe_wording("Great news — you are healthy.")

    def test_rejects_proof_claim(self):
        with self.assertRaises(UnsafeWordingError):
            assert_safe_wording("This proves you have a hormonal imbalance.")

    def test_allows_approved_screening_text(self):
        for text in SCREENING_RESULT_TEXT.values():
            assert_safe_wording(text)  # must not raise

    def test_disclaimer_is_exempt_despite_containing_diagnose(self):
        # The disclaimer's job IS to say "does not diagnose" — must not
        # trip the guard that exists to catch the opposite claim.
        assert_safe_wording(MEDICAL_DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
