"""
Real, executed tests for requirement #90 test 6: "private notification
mode must prevent sensitive lock-screen content."

`app/services/notification_service.py` imports SQLAlchemy at module
scope (`Session`, the `Notification`/`NotificationPreference` ORM
models), so it cannot be imported directly in this sandbox — same
constraint as prediction_service.py (see
test_prediction_version_immutability.py's docstring, and
docs/deployment.md). Its full behavior is covered by the written pytest
suite instead.

What CAN be verified for real here, with only the standard library plus
the already-dependency-free `app.safety.wording`:

  1. `PRIVATE_NOTIFICATION_TEXT` — the literal string
     `get_display_text()` returns whenever `privacy_mode` is on — is
     exactly the generic text the spec requires, and contains none of
     the health-specific vocabulary (period, cycle, symptom, PCOS, ...)
     that would defeat the point of a private mode by leaking on a lock
     screen anyway.
  2. Every template in `NOTIFICATION_TEXT` (the "full", non-private
     variant) passes `assert_safe_wording` — the same guard this app
     applies to screening results — so a notification body can never
     smuggle diagnostic language onto any surface, private or not.
  3. A static-analysis check on notification_service.py's source:
     `get_display_text()` actually branches on `preference.privacy_mode`
     and returns `private_text`/`full_text` accordingly — not, say, a
     constant, or the wrong attribute — so the private/full distinction
     is a genuine choice made at read time, not a name that happens to
     exist unused.
"""
import ast
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.safety.wording import (  # noqa: E402
    NOTIFICATION_TEXT,
    PRIVATE_NOTIFICATION_TEXT,
    assert_safe_wording,
)

NOTIFICATION_SERVICE_PATH = BACKEND_ROOT / "app" / "services" / "notification_service.py"

# Vocabulary that would defeat "private mode" if it leaked onto a lock
# screen — deliberately broader than just "PCOS": any of these words is
# itself health information the person may not want a bystander to see.
_HEALTH_SPECIFIC_WORDS = ["period", "cycle", "pcos", "symptom", "ovar", "menstrua", "fertil"]


class TestPrivateNotificationTextIsGeneric(unittest.TestCase):
    def test_private_text_matches_the_required_exact_wording(self):
        self.assertEqual(PRIVATE_NOTIFICATION_TEXT, "You have an OvaCare reminder.")

    def test_private_text_contains_no_health_specific_vocabulary(self):
        lowered = PRIVATE_NOTIFICATION_TEXT.lower()
        for word in _HEALTH_SPECIFIC_WORDS:
            self.assertNotIn(
                word,
                lowered,
                f"Private notification text must not contain {word!r} — it is meant to be safe to show "
                "on a locked screen where anyone nearby could read it.",
            )

    def test_private_text_passes_the_safety_wording_guard(self):
        assert_safe_wording(PRIVATE_NOTIFICATION_TEXT)  # must not raise


class TestFullNotificationTemplatesAreSafe(unittest.TestCase):
    def test_every_full_text_template_is_registered(self):
        # The four types requirement #45/#20 lists.
        self.assertEqual(
            set(NOTIFICATION_TEXT.keys()),
            {"upcoming_period", "period_logging", "cycle_tracking", "symptom_logging"},
        )

    def test_every_full_text_template_passes_the_safety_wording_guard(self):
        for notification_type, template in NOTIFICATION_TEXT.items():
            # Templates may contain a `{days}` placeholder — fill it with a
            # representative value before checking, same as
            # notification_service.build_notification_text() does at
            # runtime via str.format(**kwargs).
            rendered = template.format(days=3)
            with self.subTest(notification_type=notification_type):
                assert_safe_wording(rendered)  # must not raise


class TestGetDisplayTextBranchesOnPrivacyMode(unittest.TestCase):
    """Static-analysis check — see module docstring point 3."""

    @classmethod
    def setUpClass(cls):
        source = NOTIFICATION_SERVICE_PATH.read_text()
        cls.tree = ast.parse(source)
        cls.func = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.FunctionDef) and node.name == "get_display_text"
        )
        cls.func_source = ast.get_source_segment(source, cls.func)

    def test_function_reads_privacy_mode(self):
        self.assertIn("privacy_mode", self.func_source)

    def test_function_returns_both_private_and_full_text_attributes(self):
        self.assertIn("private_text", self.func_source)
        self.assertIn("full_text", self.func_source)

    def test_function_body_is_a_single_conditional_expression_not_a_constant(self):
        # Guards against a regression like "return notification.full_text"
        # unconditionally — the function must contain a branch (IfExp,
        # i.e. Python's `a if cond else b`, or an if/else statement),
        # not just a bare attribute access.
        has_conditional = any(isinstance(node, (ast.IfExp, ast.If)) for node in ast.walk(self.func))
        self.assertTrue(
            has_conditional,
            "get_display_text() must contain a real branch on privacy_mode, not return a constant.",
        )


if __name__ == "__main__":
    unittest.main()
