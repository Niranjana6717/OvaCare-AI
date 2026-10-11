"""
Real, executable tests for the pure cycle-calculation engine. Run with:

    python3 -m unittest backend.tests.test_cycle_math -v

(pytest is not used here because it is not installable in every environment
this repo has been developed in — see docs/deployment.md. `unittest` is
Python's standard library and needs nothing else installed.)
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on sys.path

from app.services import cycle_math  # noqa: E402
from app.services.cycle_math import CycleEntry  # noqa: E402

INSUFFICIENT_MSG = "We need more cycle history to provide a useful personalized estimate."


class TestComputeDerivedFields(unittest.TestCase):
    def test_first_entry_has_no_cycle_length(self):
        entries = [CycleEntry(date(2026, 1, 1), date(2026, 1, 5))]
        derived = cycle_math.compute_derived_fields(entries)
        self.assertIsNone(derived[0].cycle_length_days)
        self.assertEqual(derived[0].period_duration_days, 5)  # inclusive: Jan 1-5 = 5 days

    def test_second_entry_cycle_length_is_gap_between_starts(self):
        entries = [
            CycleEntry(date(2026, 1, 1), date(2026, 1, 5)),
            CycleEntry(date(2026, 1, 30), date(2026, 2, 3)),
        ]
        derived = cycle_math.compute_derived_fields(entries)
        self.assertIsNone(derived[0].cycle_length_days)
        self.assertEqual(derived[1].cycle_length_days, 29)

    def test_no_end_date_means_no_period_duration(self):
        entries = [CycleEntry(date(2026, 1, 1), None)]
        derived = cycle_math.compute_derived_fields(entries)
        self.assertIsNone(derived[0].period_duration_days)

    def test_does_not_assume_28_days(self):
        """The literal, explicit requirement: two cycles 35 days apart must
        report 35, not silently default to 28."""
        entries = [
            CycleEntry(date(2026, 1, 1), None),
            CycleEntry(date(2026, 2, 5), None),  # 35 days later
        ]
        derived = cycle_math.compute_derived_fields(entries)
        self.assertEqual(derived[1].cycle_length_days, 35)


class TestSummarize(unittest.TestCase):
    def test_insufficient_with_zero_or_one_cycle(self):
        summary = cycle_math.summarize([], INSUFFICIENT_MSG)
        self.assertFalse(summary.sufficient_data)
        self.assertEqual(summary.message, INSUFFICIENT_MSG)

        one_entry = [CycleEntry(date(2026, 1, 1), None)]
        summary_one = cycle_math.summarize(one_entry, INSUFFICIENT_MSG)
        self.assertFalse(summary_one.sufficient_data)

    def test_sufficient_with_two_cycles_computes_real_average(self):
        entries = [
            CycleEntry(date(2026, 1, 1), date(2026, 1, 5)),
            CycleEntry(date(2026, 1, 31), date(2026, 2, 4)),  # 30-day cycle
            CycleEntry(date(2026, 3, 4), date(2026, 3, 8)),  # 32-day cycle
        ]
        summary = cycle_math.summarize(entries, INSUFFICIENT_MSG)
        self.assertTrue(summary.sufficient_data)
        self.assertAlmostEqual(summary.average_cycle_length_days, 31.0)
        self.assertEqual(summary.average_period_duration_days, 5.0)

    def test_never_fabricates_never_defaults_to_28(self):
        """Every cycle in this history is 40 days — the average must be 40,
        proving the engine derives from real history rather than a
        hardcoded assumption."""
        entries = [
            CycleEntry(date(2026, 1, 1), None),
            CycleEntry(date(2026, 2, 10), None),  # +40
            CycleEntry(date(2026, 3, 22), None),  # +40
        ]
        summary = cycle_math.summarize(entries, INSUFFICIENT_MSG)
        self.assertEqual(summary.average_cycle_length_days, 40.0)
        self.assertNotEqual(summary.average_cycle_length_days, 28.0)

    def test_high_variability_flagged_without_diagnostic_claim(self):
        entries = [
            CycleEntry(date(2026, 1, 1), None),
            CycleEntry(date(2026, 1, 25), None),  # 24-day cycle
            CycleEntry(date(2026, 3, 10), None),  # 44-day cycle
        ]
        summary = cycle_math.summarize(entries, INSUFFICIENT_MSG)
        self.assertTrue(summary.is_high_variability)
        # The dataclass carries no field that could encode a diagnostic
        # conclusion — this assertion documents that invariant.
        self.assertFalse(hasattr(summary, "pcos_risk"))
        self.assertFalse(hasattr(summary, "diagnosis"))


class TestEstimateNextPeriod(unittest.TestCase):
    def test_insufficient_with_no_history(self):
        estimate = cycle_math.estimate_next_period([], INSUFFICIENT_MSG)
        self.assertFalse(estimate.sufficient_data)
        self.assertIsNone(estimate.estimated_start_date)

    def test_insufficient_with_only_one_cycle(self):
        entries = [CycleEntry(date(2026, 1, 1), None)]
        estimate = cycle_math.estimate_next_period(entries, INSUFFICIENT_MSG)
        self.assertFalse(estimate.sufficient_data)

    def test_estimate_uses_actual_average_not_28_days(self):
        entries = [
            CycleEntry(date(2026, 1, 1), None),
            CycleEntry(date(2026, 2, 4), None),  # 34-day cycle
            CycleEntry(date(2026, 3, 10), None),  # 34-day cycle
        ]
        estimate = cycle_math.estimate_next_period(entries, INSUFFICIENT_MSG)
        self.assertTrue(estimate.sufficient_data)
        self.assertEqual(estimate.estimated_start_date, date(2026, 4, 13))  # Mar 10 + 34
        self.assertEqual(estimate.based_on_cycle_count, 2)


if __name__ == "__main__":
    unittest.main()
