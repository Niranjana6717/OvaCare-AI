"""
Red-flag safety ruleset tests (requirement #90, tests 4 & 5 — irregular
cycles must not trigger a diagnosis, and urgent flags must be detected
independent of the ML path).

Run with: python3 -m unittest backend.tests.test_red_flag_rules -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.safety.red_flag_rules import any_red_flag_triggered, evaluate_red_flags  # noqa: E402
from app.services.safety_service import check_for_red_flags  # noqa: E402


class TestRedFlagRules(unittest.TestCase):
    def test_no_flags_on_ordinary_inputs(self):
        inputs = {"pelvic_pain_severity": 2, "fainting_or_severe_dizziness": False}
        self.assertFalse(any_red_flag_triggered(inputs))

    def test_severe_pain_triggers(self):
        inputs = {"pelvic_pain_severity": 5}
        triggered = evaluate_red_flags(inputs)
        self.assertEqual([r.rule_id for r in triggered], ["RF-002"])

    def test_heavy_bleeding_triggers(self):
        inputs = {"soaking_through_protection_hourly": True}
        self.assertTrue(any_red_flag_triggered(inputs))

    def test_fainting_triggers(self):
        inputs = {"fainting_or_severe_dizziness": True}
        self.assertTrue(any_red_flag_triggered(inputs))

    def test_chest_pain_triggers(self):
        inputs = {"chest_pain_or_breathing_difficulty": True}
        self.assertTrue(any_red_flag_triggered(inputs))

    def test_irregular_cycle_data_alone_never_triggers_a_flag(self):
        """Requirement #18/#83: irregular cycles must never be treated as an
        emergency, nor mapped to a PCOS conclusion. Feeding this ruleset
        nothing but cycle-irregularity-shaped data must produce zero flags."""
        inputs = {
            "cycle_regularity": "irregular",
            "average_cycle_length_days": 55,
            "cycle_variability_stdev_days": 15,
        }
        self.assertFalse(any_red_flag_triggered(inputs))


class TestSafetyServiceIntegration(unittest.TestCase):
    def test_urgent_result_includes_generic_non_diagnostic_message(self):
        result = check_for_red_flags({"chest_pain_or_breathing_difficulty": True})
        self.assertTrue(result.urgent)
        self.assertIn("emergency medical service", result.message)
        self.assertNotIn("pcos", result.message.lower())  # never names a cause
        self.assertEqual(result.triggered_rule_ids, ["RF-004"])

    def test_non_urgent_result_has_no_message(self):
        result = check_for_red_flags({"pelvic_pain_severity": 1})
        self.assertFalse(result.urgent)
        self.assertIsNone(result.message)
        self.assertEqual(result.triggered_rule_ids, [])


if __name__ == "__main__":
    unittest.main()
