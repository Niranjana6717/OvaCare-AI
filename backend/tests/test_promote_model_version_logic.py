"""
Real, executed tests for scripts/promote_model_version.py's dependency-free
decision logic (decide_promotion_plan). The SQLAlchemy/filesystem-using
promote() function is written-but-not-executed in this sandbox — same
disclosed category as the rest of the backend.
"""
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from promote_model_version import PromotionRefusedError, decide_promotion_plan  # noqa: E402


class TestDecidePromotionPlan(unittest.TestCase):
    def test_refuses_when_not_staging(self):
        for bad_stage in ["development", "validation", "production", "archived"]:
            with self.subTest(bad_stage=bad_stage):
                with self.assertRaises(PromotionRefusedError):
                    decide_promotion_plan(bad_stage, has_existing_production=False)

    def test_promotes_with_no_existing_production(self):
        plan = decide_promotion_plan("staging", has_existing_production=False)
        self.assertEqual(plan, "promote_no_existing_production")

    def test_promotes_and_archives_existing_production(self):
        plan = decide_promotion_plan("staging", has_existing_production=True)
        self.assertEqual(plan, "promote_and_archive_existing")

    def test_refusal_message_never_claims_the_promotion_happened(self):
        try:
            decide_promotion_plan("development", has_existing_production=False)
            self.fail("expected PromotionRefusedError")
        except PromotionRefusedError as exc:
            self.assertIn("Refusing", str(exc))


if __name__ == "__main__":
    unittest.main()
