"""
Red-flag safety ruleset.

This is intentionally a plain, deterministic, human-readable ruleset —
NOT a model, and not derived from the PCOS screening ML pipeline. Per
requirement #68/#69, safety rules must be independently reviewable and must
never be conflated with the ML model's output.

STATUS: `RULESET_REVIEW_STATUS` below is honestly "pending_clinical_review".
No qualified clinician has reviewed this ruleset in this environment, so the
product must not claim it is "clinically reviewed" (requirement #69, #92)
until that review actually happens and this constant is updated alongside
a real reviewer identity and date.

The rules below only ever gate whether the generic, non-diagnostic
`URGENT_SAFETY_MESSAGE` is shown — they never attempt to name a cause. That
keeps this module inside "recognize a red flag and point to care," not
"diagnose the emergency," which is the line requirement #66/#67 draws.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RULESET_VERSION = "1.0.0-draft"
RULESET_REVIEW_STATUS = "pending_clinical_review"  # see module docstring


@dataclass(frozen=True)
class RedFlagRule:
    rule_id: str
    description: str
    check: "callable"  # Callable[[dict], bool]


def _severe_bleeding(inputs: dict[str, Any]) -> bool:
    return bool(inputs.get("soaking_through_protection_hourly")) or bool(
        inputs.get("bleeding_with_dizziness_or_fainting")
    )


def _severe_pain(inputs: dict[str, Any]) -> bool:
    pain_severity = inputs.get("pelvic_pain_severity")  # expected 1-5 scale, or None
    return isinstance(pain_severity, (int, float)) and pain_severity >= 5


def _fainting_or_severe_dizziness(inputs: dict[str, Any]) -> bool:
    return bool(inputs.get("fainting_or_severe_dizziness"))


def _chest_pain_or_breathing_difficulty(inputs: dict[str, Any]) -> bool:
    return bool(inputs.get("chest_pain_or_breathing_difficulty"))


RED_FLAG_RULES: list[RedFlagRule] = [
    RedFlagRule(
        rule_id="RF-001",
        description="Heavy bleeding reported as soaking through protection hourly, or with fainting/dizziness.",
        check=_severe_bleeding,
    ),
    RedFlagRule(
        rule_id="RF-002",
        description="Pelvic/abdominal pain reported at maximum severity.",
        check=_severe_pain,
    ),
    RedFlagRule(
        rule_id="RF-003",
        description="Fainting or severe dizziness reported.",
        check=_fainting_or_severe_dizziness,
    ),
    RedFlagRule(
        rule_id="RF-004",
        description="Chest pain or difficulty breathing reported.",
        check=_chest_pain_or_breathing_difficulty,
    ),
]


def evaluate_red_flags(inputs: dict[str, Any]) -> list[RedFlagRule]:
    """Return the list of triggered rules (empty if none). Pure function,
    independent of the ML model — see module docstring."""
    return [rule for rule in RED_FLAG_RULES if rule.check(inputs)]


def any_red_flag_triggered(inputs: dict[str, Any]) -> bool:
    return len(evaluate_red_flags(inputs)) > 0
