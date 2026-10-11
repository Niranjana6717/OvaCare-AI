"""
Real, executed tests for ML monitoring + drift detection.

app.services.monitoring_service's distribution/drift/counter functions have
zero SQLAlchemy imports at module scope (the DB-facing get_monitoring_snapshot
defers that import inside the function body) — so, like cycle_math.py and
report_pdf_service.py, this module runs directly in this sandbox.
"""
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.monitoring_service import (  # noqa: E402
    PredictionRow,
    compute_assessment_missing_field_rate,
    compute_drift_signal,
    compute_prediction_distribution,
    get_inference_error_count,
    get_latency_stats,
    record_inference_outcome,
    reset_counters_for_tests,
)


class TestComputePredictionDistribution(unittest.TestCase):
    def test_empty_rows_returns_honest_nones_not_zeros(self):
        result = compute_prediction_distribution([])
        self.assertEqual(result["total_predictions"], 0)
        self.assertIsNone(result["missing_data_rate_pct"])
        self.assertIsNone(result["model_unavailable_rate_pct"])

    def test_outcome_and_version_distribution_counts_are_real_tallies(self):
        rows = [
            PredictionRow(outcome="higher_indication", model_version="1.0.0"),
            PredictionRow(outcome="higher_indication", model_version="1.0.0"),
            PredictionRow(outcome="lower_indication", model_version="1.0.0"),
            PredictionRow(outcome="insufficient_data", model_version="1.0.0", insufficient_data_reason="Some required information was missing: Age."),
        ]
        result = compute_prediction_distribution(rows)
        self.assertEqual(result["total_predictions"], 4)
        self.assertEqual(result["outcome_distribution"], {"higher_indication": 2, "lower_indication": 1, "insufficient_data": 1})
        self.assertEqual(result["outcome_distribution_pct"]["higher_indication"], 50.0)
        self.assertEqual(result["model_version_distribution"], {"1.0.0": 4})

    def test_missing_data_and_model_unavailable_are_distinguished(self):
        rows = [
            PredictionRow(
                outcome="insufficient_data",
                model_version="1.0.0",
                insufficient_data_reason="Some required information was missing: Age.",
            ),
            PredictionRow(
                outcome="insufficient_data",
                model_version="unavailable",
                insufficient_data_reason=(
                    "No validated production screening model is currently deployed. "
                    "This is a deliberate safety default, not an error to work around."
                ),
            ),
        ]
        result = compute_prediction_distribution(rows)
        self.assertEqual(result["missing_data_rate_pct"], 50.0)
        self.assertEqual(result["model_unavailable_rate_pct"], 50.0)


class TestAssessmentMissingFieldRate(unittest.TestCase):
    def test_none_when_no_assessments(self):
        self.assertIsNone(compute_assessment_missing_field_rate([]))

    def test_computes_real_fraction_with_any_gap(self):
        lists = [[], ["fsh"], [], ["fsh", "lh"]]
        self.assertEqual(compute_assessment_missing_field_rate(lists), 50.0)

    def test_all_complete_is_zero_not_none(self):
        self.assertEqual(compute_assessment_missing_field_rate([[], []]), 0.0)


class TestComputeDriftSignal(unittest.TestCase):
    def test_unavailable_when_no_baseline(self):
        rows = [PredictionRow(outcome="higher_indication", model_version="1.0.0")] * 25
        result = compute_drift_signal(rows, baseline_positive_rate=None)
        self.assertFalse(result["available"])

    def test_unavailable_below_minimum_sample_size(self):
        rows = [PredictionRow(outcome="higher_indication", model_version="1.0.0")] * 5
        result = compute_drift_signal(rows, baseline_positive_rate=0.33)
        self.assertFalse(result["available"])
        self.assertIn("need at least", result["reason"])

    def test_matching_distribution_gives_near_zero_psi_and_no_flag(self):
        # Baseline positive rate 0.5, current also ~0.5 -> PSI should be ~0.
        rows = [PredictionRow(outcome="higher_indication", model_version="1.0.0")] * 15 + [
            PredictionRow(outcome="lower_indication", model_version="1.0.0")
        ] * 15
        result = compute_drift_signal(rows, baseline_positive_rate=0.5)
        self.assertTrue(result["available"])
        self.assertAlmostEqual(result["population_stability_index"], 0.0, places=3)
        self.assertFalse(result["notable_drift"])

    def test_sharply_different_distribution_flags_notable_drift(self):
        # Baseline positive rate 0.33 (training set), but current window is
        # almost entirely higher_indication -> should exceed PSI 0.25.
        rows = [PredictionRow(outcome="higher_indication", model_version="1.0.0")] * 28 + [
            PredictionRow(outcome="lower_indication", model_version="1.0.0")
        ] * 2
        result = compute_drift_signal(rows, baseline_positive_rate=0.33)
        self.assertTrue(result["available"])
        self.assertGreater(result["population_stability_index"], 0.25)
        self.assertTrue(result["notable_drift"])

    def test_insufficient_data_rows_excluded_from_decided_count(self):
        # 30 rows but only 10 are decided -> still below the 20 minimum.
        rows = [PredictionRow(outcome="insufficient_data", model_version="1.0.0")] * 20 + [
            PredictionRow(outcome="higher_indication", model_version="1.0.0")
        ] * 10
        result = compute_drift_signal(rows, baseline_positive_rate=0.33)
        self.assertFalse(result["available"])

    def test_result_is_a_signal_never_an_instruction_to_retrain(self):
        # The note's job is to say what must NOT happen automatically — it
        # legitimately contains "retrained" as part of that negation (same
        # pattern as app.safety.wording's own disclaimer text), so this
        # checks for the negation, not bare string absence.
        rows = [PredictionRow(outcome="higher_indication", model_version="1.0.0")] * 30
        result = compute_drift_signal(rows, baseline_positive_rate=0.1)
        note = result["note"].lower()
        self.assertIn("no model is retrained", note)
        self.assertIn("review", note)


class TestInferenceCounters(unittest.TestCase):
    def setUp(self):
        reset_counters_for_tests()

    def test_starts_at_zero(self):
        self.assertEqual(get_inference_error_count(), 0)

    def test_only_failures_increment_error_count(self):
        record_inference_outcome(succeeded=True, latency_ms=12.0)
        record_inference_outcome(succeeded=True, latency_ms=8.0)
        record_inference_outcome(succeeded=False, latency_ms=5.0)
        self.assertEqual(get_inference_error_count(), 1)

    def test_latency_stats_reflect_real_recorded_samples(self):
        for ms in [10.0, 20.0, 30.0, 40.0, 50.0]:
            record_inference_outcome(succeeded=True, latency_ms=ms)
        stats = get_latency_stats()
        self.assertEqual(stats["n_samples"], 5)
        self.assertEqual(stats["p50_ms"], 30.0)

    def test_no_samples_gives_honest_nones(self):
        stats = get_latency_stats()
        self.assertIsNone(stats["p50_ms"])
        self.assertEqual(stats["n_samples"], 0)


if __name__ == "__main__":
    unittest.main()
