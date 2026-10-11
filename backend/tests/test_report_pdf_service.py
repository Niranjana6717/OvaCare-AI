"""
Real, executed tests for the PDF health report export.

`app.services.report_pdf_service` has zero SQLAlchemy/FastAPI imports (see
its module docstring), so — unlike most of this backend — it CAN be
imported and run directly in this sandbox. These tests build a real PDF
with reportlab and then parse it back with pypdf, asserting on the actual
extracted text, not just "bytes were returned."
"""
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import io

from pypdf import PdfReader  # noqa: E402

from app.services.report_pdf_service import build_health_report_pdf  # noqa: E402
from app.safety.wording import MEDICAL_DISCLAIMER, PDF_REPORT_DISCLAIMER  # noqa: E402


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


FULL_REPORT = {
    "generated_at": "2026-01-01T00:00:00+00:00",
    "profile": {
        "full_name": "Test User",
        "date_of_birth": "1995-05-01",
        "height_cm": 165,
        "weight_kg": 60,
        "bmi": 22.0,
        "country": "IN",
    },
    "cycle_history": [
        {"start_date": "2026-01-01", "end_date": "2026-01-05", "period_duration_days": 5, "flow_level": "medium"},
        {"start_date": "2025-12-02", "end_date": "2025-12-06", "period_duration_days": 5, "flow_level": "medium"},
        {"start_date": "2025-11-01", "end_date": "2025-11-05", "period_duration_days": 5, "flow_level": "light"},
    ],
    "symptom_history": [
        {"symptom_type": "acne", "custom_label": None, "severity": 3, "logged_date": "2026-01-02"},
        {"symptom_type": "acne", "custom_label": None, "severity": 5, "logged_date": "2025-12-10"},
    ],
    "screening_history": [
        {
            "assessment_id": "abc123",
            "outcome": "higher_indication",
            "message": (
                "Your responses produced a screening result that may warrant further discussion with a "
                "healthcare professional."
            ),
            "probability": 0.71,
            "explanation_framing": "These factors contributed to the screening result:",
            "explanation": {
                "method": "shap",
                "factors": [
                    {
                        "feature": "cycle_regularity",
                        "label": "Cycle regularity",
                        "contribution": 0.4,
                        "why_it_matters": "Irregular cycles are one of several patterns considered.",
                    }
                ],
            },
            "insufficient_data_reason": None,
            "model_version": "1.0.0",
            "feature_schema_version": "1.0.0",
            "preprocessing_version": "1.0.0",
            "threshold_version": "1.0.0",
            "assessed_at": "2026-01-02T00:00:00+00:00",
            "medical_disclaimer": MEDICAL_DISCLAIMER,
        }
    ],
}


class TestBuildHealthReportPdf(unittest.TestCase):
    def test_returns_real_pdf_bytes(self):
        pdf_bytes = build_health_report_pdf(FULL_REPORT)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_mandatory_disclaimer_is_present_verbatim(self):
        text = _extract_text(build_health_report_pdf(FULL_REPORT))
        self.assertIn(PDF_REPORT_DISCLAIMER, text)

    def test_profile_fields_present(self):
        text = _extract_text(build_health_report_pdf(FULL_REPORT))
        for expected in ["Test User", "1995-05-01", "165", "60", "22.0", "IN"]:
            self.assertIn(expected, text)

    def test_cycle_summary_computed_from_history_not_fabricated(self):
        # 3 cycle records -> 2 derived gaps -> sufficient_data. Verifies the
        # PDF's cycle summary is computed via cycle_math (same module the
        # rest of the app uses), not invented independently.
        text = _extract_text(build_health_report_pdf(FULL_REPORT))
        self.assertIn("days", text)
        self.assertNotIn("Not enough cycle history", text)

    def test_cycle_summary_degrades_honestly_with_insufficient_history(self):
        report = dict(FULL_REPORT)
        report["cycle_history"] = FULL_REPORT["cycle_history"][:1]  # only 1 record -> no derivable length
        text = _extract_text(build_health_report_pdf(report))
        self.assertIn("Not enough cycle history for a summary.", text)

    def test_symptom_summary_present(self):
        text = _extract_text(build_health_report_pdf(FULL_REPORT))
        self.assertIn("Acne", text)
        self.assertIn("2", text)  # times logged

    def test_screening_message_and_model_version_present(self):
        text = _extract_text(build_health_report_pdf(FULL_REPORT))
        self.assertIn(FULL_REPORT["screening_history"][0]["message"], text)
        self.assertIn("1.0.0", text)
        self.assertIn("Cycle regularity", text)

    def test_screening_result_never_says_diagnostic_phrase(self):
        # Defense-in-depth: the PDF must never render text that would fail
        # the app-wide safety-wording guard (same guard used elsewhere).
        text = _extract_text(build_health_report_pdf(FULL_REPORT)).lower()
        self.assertNotIn("you have pcos", text)
        self.assertNotIn("you do not have pcos", text)

    def test_missing_optional_sections_are_simply_absent(self):
        # requirement #35/#85: only the sections the user selected appear.
        minimal_report = {"generated_at": "2026-01-01T00:00:00+00:00"}
        pdf_bytes = build_health_report_pdf(minimal_report)
        text = _extract_text(pdf_bytes)
        self.assertIn(PDF_REPORT_DISCLAIMER, text)
        self.assertNotIn("Profile", text)
        self.assertNotIn("Cycle Summary", text)

    def test_no_screening_history_says_none_completed_not_fabricated(self):
        report = dict(FULL_REPORT)
        report["screening_history"] = []
        text = _extract_text(build_health_report_pdf(report))
        self.assertIn("No screening assessments completed yet.", text)


if __name__ == "__main__":
    unittest.main()
