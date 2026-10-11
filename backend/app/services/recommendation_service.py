"""
Insights: cycle trends + symptom trends + static educational content.

Kept structurally separate from ML predictions (requirement #27, #41): this
module never imports app.ml.* and never reads Prediction rows to generate
its text. Educational content items carry the same review-status metadata
as the rest of the safety copy (app.safety.content_review) so an insight can
never silently ship unreviewed medical claims.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.safety.content_review import get_review_record
from app.services.cycle_service import get_cycle_summary
from app.services.symptom_service import get_symptom_trends

# Static, versioned educational snippets. See docs/clinical_safety.md —
# these are pending_review in this codebase (no clinician has reviewed them
# here) and are labeled as such in the API response rather than silently
# presented as clinically approved.
_EDUCATIONAL_CONTENT = [
    {
        "content_id": "educational_content_cycle_and_symptoms",
        "title": "Cycle length naturally varies",
        "body": (
            "A typical menstrual cycle can range from about 21 to 35 days, and "
            "some variation from cycle to cycle is common. Persistent, "
            "significant changes are worth discussing with a healthcare "
            "professional."
        ),
    },
    {
        "content_id": "educational_content_cycle_and_symptoms",
        "title": "Tracking helps conversations with a clinician",
        "body": (
            "Keeping a record of your cycles and symptoms over time can make it "
            "easier to describe patterns to a healthcare professional, even "
            "though OvaCare itself does not interpret those patterns as a "
            "diagnosis."
        ),
    },
]


def get_insights(db: Session, user_id: str) -> dict:
    cycle_summary, _history = get_cycle_summary(db, user_id)
    symptom_trends = get_symptom_trends(db, user_id)

    educational = []
    for item in _EDUCATIONAL_CONTENT:
        review = get_review_record(item["content_id"])
        educational.append(
            {
                **item,
                "review_status": review.review_status if review else "unknown",
            }
        )

    return {
        "cycle_trends": {
            "sufficient_data": cycle_summary.sufficient_data,
            "message": cycle_summary.message,
            "average_cycle_length_days": cycle_summary.average_cycle_length_days,
            "average_period_duration_days": cycle_summary.average_period_duration_days,
            "cycle_variability_stdev_days": cycle_summary.cycle_variability_stdev_days,
            "is_high_variability": cycle_summary.is_high_variability,
        },
        "symptom_trends": symptom_trends,
        "educational_content": educational,
        "source": "non_diagnostic_insights",  # explicit tag: never ML output
    }
