"""
Reminder scheduling.

Converts a user's cycle estimate + their NotificationPreference into a
concrete, timezone-aware `Notification` row. Delivery to a real push
provider is out of scope for this environment (see the Notification model's
docstring) — what's implemented and tested here is the part that is
genuinely safety/privacy relevant: computing the correct UTC fire time from
a local wall-clock preference (requirement #45) and choosing the correct
text for the user's privacy setting (requirement #21/#84).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.database.models.notification import Notification, NotificationPreference, NotificationType
from app.logging_config import log_structured
from app.safety.wording import NOTIFICATION_TEXT, PRIVATE_NOTIFICATION_TEXT, assert_safe_wording

logger = logging.getLogger("ovacare.notifications")


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        # Not a user-facing error — a reminder still gets scheduled, just
        # in UTC instead of their intended local time. Logged (not the
        # user id — only the invalid value itself, which isn't sensitive)
        # so an unexpectedly-common bad timezone string is visible.
        log_structured(logger, logging.WARNING, "notifications.unknown_timezone_fallback_utc", tz_name=tz_name)
        return ZoneInfo("UTC")


def _local_datetime_to_utc(local_date: date, local_time, tz_name: str) -> datetime:
    tz = _resolve_timezone(tz_name)
    local_dt = datetime.combine(local_date, local_time, tzinfo=tz)
    return local_dt.astimezone(ZoneInfo("UTC"))


def build_notification_text(notification_type: NotificationType, preference: NotificationPreference, **kwargs) -> tuple[str, str]:
    template = NOTIFICATION_TEXT[notification_type.value]
    full_text = template.format(**kwargs) if kwargs else template
    assert_safe_wording(full_text)
    assert_safe_wording(PRIVATE_NOTIFICATION_TEXT)
    return full_text, PRIVATE_NOTIFICATION_TEXT


def schedule_upcoming_period_reminder(
    db: Session,
    user_id: str,
    preference: NotificationPreference,
    estimated_start_date: date,
) -> Notification | None:
    if not preference.period_reminders_enabled:
        return None

    reminder_date = estimated_start_date - timedelta(days=preference.days_before_period)
    scheduled_for_utc = _local_datetime_to_utc(reminder_date, preference.notification_time, preference.timezone)

    # Never schedule a reminder in the past relative to "now" — a stale
    # estimate (e.g. recomputed after the reminder date already passed)
    # should not silently create a notification that will never fire.
    if scheduled_for_utc <= datetime.now(scheduled_for_utc.tzinfo):
        return None

    full_text, private_text = build_notification_text(
        NotificationType.UPCOMING_PERIOD, preference, days=preference.days_before_period
    )

    notification = Notification(
        user_id=user_id,
        notification_type=NotificationType.UPCOMING_PERIOD,
        scheduled_for=scheduled_for_utc,
        full_text=full_text,
        private_text=private_text,
    )
    db.add(notification)
    db.flush()
    return notification


def get_display_text(notification: Notification, preference: NotificationPreference) -> str:
    """What actually renders on a lock screen / preview, honoring privacy_mode."""
    return notification.private_text if preference.privacy_mode else notification.full_text
