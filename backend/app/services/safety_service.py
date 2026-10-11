"""
Safety orchestration service.

This is the ONE place that decides whether an urgent-care banner should be
shown, and it runs independently of the ML prediction path (requirement
#68: "Safety rules must not automatically be treated as equivalent to the
ML model"). Callers (assessments API, symptoms API) call
`check_for_red_flags` on every submission, before or in parallel with any ML
call, and never gate it on the ML result completing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.safety.red_flag_rules import evaluate_red_flags
from app.safety.wording import URGENT_SAFETY_MESSAGE, assert_safe_wording


@dataclass
class SafetyCheckResult:
    urgent: bool
    message: str | None
    triggered_rule_ids: list[str]


def check_for_red_flags(inputs: dict[str, Any]) -> SafetyCheckResult:
    triggered = evaluate_red_flags(inputs)
    if not triggered:
        return SafetyCheckResult(urgent=False, message=None, triggered_rule_ids=[])

    assert_safe_wording(URGENT_SAFETY_MESSAGE)
    return SafetyCheckResult(
        urgent=True,
        message=URGENT_SAFETY_MESSAGE,
        triggered_rule_ids=[rule.rule_id for rule in triggered],
    )
