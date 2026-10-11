/// Pure period-reminder fire-time calculation — the on-device mirror of
/// backend/app/services/notification_service.py's
/// `schedule_upcoming_period_reminder()`. Takes the same real
/// cycle-history-based estimate the app already fetches via
/// `OvaCareApi.cycleEstimate()` (GET /cycles/estimate — never a hardcoded
/// 28-day assumption; see cycle_math.py's `estimate_next_period`) and the
/// user's saved `NotificationPreference`, and returns the device-local
/// wall-clock moment a local notification should fire, or `null` when no
/// reminder should be scheduled at all.
///
/// Kept free of any `flutter_local_notifications`/`timezone` plugin import
/// so the decision logic itself — which is the safety/privacy-relevant
/// part — stays plain, deterministic Dart. That also means it's exercised
/// by test/services/reminder_time_test.dart without needing a device or
/// plugin mock (see apps/mobile/README.md for why no Dart SDK is available
/// to actually run that test in this sandbox).
///
/// Deliberately uses the device's own local wall-clock time
/// (`DateTime`'s non-UTC constructor, which Dart always interprets in the
/// OS's current local timezone) rather than the `timezone` string stored on
/// `NotificationPreference`. The backend needs that stored string because
/// it schedules from a server with no notion of "the user's device right
/// now" — but a local notification is scheduled directly on the user's own
/// device, so its real clock is the more accurate source of "what time is
/// it for this person right now" than a possibly-stale saved preference
/// (e.g. set up before a trip to a different timezone).
library;

/// A device-local wall-clock moment, deliberately not a `DateTime` so
/// callers can't accidentally treat it as UTC or re-localize it — the
/// caller (`LocalReminderService`) is responsible for turning this into
/// whatever the notification plugin's scheduling API requires.
class ReminderFireTime {
  final int year;
  final int month;
  final int day;
  final int hour;
  final int minute;

  const ReminderFireTime({
    required this.year,
    required this.month,
    required this.day,
    required this.hour,
    required this.minute,
  });

  /// Device-local `DateTime` for this moment — safe because both sides
  /// (this class and the caller) agree it is always local, never UTC.
  DateTime toLocalDateTime() => DateTime(year, month, day, hour, minute);

  @override
  bool operator ==(Object other) =>
      other is ReminderFireTime &&
      other.year == year &&
      other.month == month &&
      other.day == day &&
      other.hour == hour &&
      other.minute == minute;

  @override
  int get hashCode => Object.hash(year, month, day, hour, minute);

  @override
  String toString() =>
      '${year.toString().padLeft(4, '0')}-${month.toString().padLeft(2, '0')}-'
      '${day.toString().padLeft(2, '0')} ${hour.toString().padLeft(2, '0')}:'
      '${minute.toString().padLeft(2, '0')}';
}

/// Returns `null` when reminders are off, there isn't enough cycle history
/// yet for a real estimate (never substituted with a guessed date), or the
/// computed fire time already falls in the past — mirroring the backend's
/// own "never schedule a reminder in the past" rule.
///
/// [notificationTimeHHMM] is the saved `"HH:MM"` 24-hour preference value
/// (`NotificationPreference.notificationTime`). [now] is injected (rather
/// than read via `DateTime.now()` internally) purely so this stays a pure,
/// directly testable function.
ReminderFireTime? computeUpcomingPeriodReminderTime({
  required bool periodRemindersEnabled,
  required bool sufficientData,
  required DateTime? estimatedStartDate,
  required int daysBeforePeriod,
  required String notificationTimeHHMM,
  required DateTime now,
}) {
  if (!periodRemindersEnabled) return null;
  if (!sufficientData || estimatedStartDate == null) return null;

  final reminderDate = estimatedStartDate.subtract(Duration(days: daysBeforePeriod));
  final parts = notificationTimeHHMM.split(':');
  if (parts.length < 2) return null;
  final hour = int.tryParse(parts[0]);
  final minute = int.tryParse(parts[1]);
  if (hour == null || minute == null) return null;

  final fireAt = DateTime(reminderDate.year, reminderDate.month, reminderDate.day, hour, minute);
  if (!fireAt.isAfter(now)) return null;

  return ReminderFireTime(year: fireAt.year, month: fireAt.month, day: fireAt.day, hour: fireAt.hour, minute: fireAt.minute);
}
