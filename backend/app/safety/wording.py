"""
Canonical, pre-approved safety wording + a runtime guard.

This is the single source of truth for every string the product shows in
connection with a screening result, cycle estimate, or symptom-related
message. Services must import strings from here rather than writing their
own — that is what makes `assert_safe_wording` below meaningful as a second
line of defense (requirement #63/#64/#90: a screening result may never read
as a diagnosis or a false reassurance).
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Screening result wording (requirement #63, #64)
# ---------------------------------------------------------------------------

SCREENING_RESULT_TEXT = {
    "higher_indication": (
        "Your responses produced a screening result that may warrant further "
        "discussion with a healthcare professional."
    ),
    "lower_indication": (
        "The information you provided produced a lower screening indication in "
        "this model. This does not rule out PCOS or other health conditions."
    ),
    "insufficient_data": (
        "We don't have enough validated information to provide a reliable "
        "screening result from these inputs. Please review your information or "
        "consider discussing your concerns with a healthcare professional."
    ),
}

MEDICAL_DISCLAIMER = (
    "OvaCare's AI screening is for informational and health-awareness purposes "
    "only. It does not diagnose PCOS or any other medical condition.\n\n"
    "A healthcare professional should evaluate persistent, concerning, or "
    "clinically significant symptoms.\n\n"
    "Do not make medical decisions based solely on this screening result."
)

EXPLANATION_FRAMING_PREFIX = "These factors contributed to the screening result:"

# Exact wording required on every PDF health report export (distinct from
# MEDICAL_DISCLAIMER above, which is the longer in-app disclaimer) —
# app/services/report_pdf_service.py prints this verbatim, never a
# paraphrase.
PDF_REPORT_DISCLAIMER = (
    "This report is generated from an AI-based screening system. "
    "It is not a medical diagnosis."
)

# ---------------------------------------------------------------------------
# Cycle / period wording (requirement #16, #17, #82)
# ---------------------------------------------------------------------------

INSUFFICIENT_CYCLE_HISTORY_TEXT = (
    "We need more cycle history to provide a useful personalized estimate."
)

IRREGULAR_CYCLE_NEUTRAL_TEXT = (
    "Your recent cycle lengths have varied. Continue tracking your cycles, and "
    "consider discussing persistent changes with a qualified healthcare "
    "professional."
)

ESTIMATED_PERIOD_LABEL = "Estimated next period"

# ---------------------------------------------------------------------------
# Notification wording (requirement #20, #21)
# ---------------------------------------------------------------------------

NOTIFICATION_TEXT = {
    "upcoming_period": "Your estimated period may start in about {days} day(s).",
    "period_logging": "If your period has started, you can log it in OvaCare.",
    "cycle_tracking": "Keep your cycle history updated to improve your personal tracking estimates.",
    "symptom_logging": "You can update today's symptoms in OvaCare.",
}

PRIVATE_NOTIFICATION_TEXT = "You have an OvaCare reminder."

# ---------------------------------------------------------------------------
# Emergency / urgent wording (requirement #67)
# ---------------------------------------------------------------------------

URGENT_SAFETY_MESSAGE = (
    "Some symptoms can require urgent medical attention.\n\n"
    "If you are experiencing severe, rapidly worsening, or life-threatening "
    "symptoms, contact your local emergency medical service or seek immediate "
    "medical care."
)

# ---------------------------------------------------------------------------
# Runtime guard: banned diagnostic / reassurance phrasing
# ---------------------------------------------------------------------------
# This is a defense-in-depth check, not the primary control. The primary
# control is that every user-facing string is drawn from this file. This
# regex list exists to fail loudly in CI/tests if new code introduces
# diagnostic language elsewhere (see backend/tests/test_safety_wording.py).

_BANNED_PATTERNS = [
    r"\byou have pcos\b",
    r"\byou do not have pcos\b",
    r"\byou don't have pcos\b",
    r"\bthis proves\b",
    r"\bconfirms (you|that you) (have|don't have|do not have)\b",
    r"\bdiagnos(e|es|ed|is)\b.*\bpcos\b",
    r"\bpcos\b.*\bdiagnos",
    r"\byou are (healthy|fine|normal)\b",
    r"\bno need to see a doctor\b",
    r"\byou can rule out\b",
]
_BANNED_RE = re.compile("|".join(_BANNED_PATTERNS), re.IGNORECASE)

# A few narrow, deliberate exemptions: text whose JOB is to say what the
# system must NOT claim (e.g. the disclaimer itself, or this module's own
# docstrings/labels) legitimately contains the banned phrase while negating
# it. We only ever call the guard against strings we are about to SHOW the
# user for a result/estimate, so this list should stay short and explicit.
_EXEMPT_STRINGS = {MEDICAL_DISCLAIMER}


def assert_safe_wording(text: str) -> None:
    """Raise if `text` contains language the product must never surface.

    Intended to be called on any dynamically-assembled string before it is
    returned from an API response (see prediction_service, safety_service).
    """
    if text in _EXEMPT_STRINGS:
        return
    match = _BANNED_RE.search(text)
    if match:
        raise UnsafeWordingError(
            f"Blocked unsafe wording pattern {match.group(0)!r} in outbound text."
        )


class UnsafeWordingError(Exception):
    pass
