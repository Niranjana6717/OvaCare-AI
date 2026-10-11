"""
Clinical/content review tracking (requirement #69).

Tracks review metadata for the pieces of the product that carry health
meaning: screening wording, safety messages, red-flag rules, educational
content, and questionnaire wording. This is metadata bookkeeping, not a
substitute for the review itself — `reviewed_by_role`/`reviewed_at` are only
ever set when a real review actually occurred, and every entry here starts
"pending_review" honestly rather than defaulting to "reviewed".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class ContentReviewRecord:
    content_id: str
    content_version: str
    review_status: str  # "pending_review" | "approved" | "changes_requested"
    reviewed_by_role: Optional[str] = None
    reviewed_at: Optional[date] = None
    next_review_date: Optional[date] = None


# Registry of the reviewable content surfaces shipped in this codebase.
# All start `pending_review` — see docs/clinical_safety.md for the process
# this repo expects a real clinical reviewer to follow before any of these
# flip to "approved" and before the product can honestly claim "clinically
# reviewed" anywhere in its UI or marketing (requirement #92).
CONTENT_REVIEW_REGISTRY: list[ContentReviewRecord] = [
    ContentReviewRecord(
        content_id="screening_result_wording",
        content_version="1.0.0",
        review_status="pending_review",
    ),
    ContentReviewRecord(
        content_id="red_flag_ruleset",
        content_version="1.0.0-draft",
        review_status="pending_review",
    ),
    ContentReviewRecord(
        content_id="questionnaire_wording",
        content_version="1.0.0",
        review_status="pending_review",
    ),
    ContentReviewRecord(
        content_id="educational_content_cycle_and_symptoms",
        content_version="1.0.0",
        review_status="pending_review",
    ),
    ContentReviewRecord(
        content_id="medical_disclaimer",
        content_version="1.0.0",
        review_status="pending_review",
    ),
]


def get_review_record(content_id: str) -> Optional[ContentReviewRecord]:
    return next((r for r in CONTENT_REVIEW_REGISTRY if r.content_id == content_id), None)


def is_content_approved(content_id: str) -> bool:
    record = get_review_record(content_id)
    return record is not None and record.review_status == "approved"
