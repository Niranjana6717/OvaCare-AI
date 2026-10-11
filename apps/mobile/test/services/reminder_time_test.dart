import 'package:flutter_test/flutter_test.dart';
import 'package:ovacare_ai/services/reminder_time.dart';

// Mirrors backend/tests/test_notification_service.py's coverage of
// schedule_upcoming_period_reminder() — same scenarios (disabled, no
// history yet, in the past, normal case) — so this pure Dart mirror of
// that logic is checked against the same cases the Python original is.
void main() {
  group('computeUpcomingPeriodReminderTime', () {
    final now = DateTime(2026, 9, 1, 8, 0);

    test('returns null when reminders are disabled', () {
      final result = computeUpcomingPeriodReminderTime(
        periodRemindersEnabled: false,
        sufficientData: true,
        estimatedStartDate: DateTime(2026, 9, 20),
        daysBeforePeriod: 2,
        notificationTimeHHMM: '09:00',
        now: now,
      );
      expect(result, isNull);
    });

    test('returns null without enough cycle history — never assumes a date', () {
      final result = computeUpcomingPeriodReminderTime(
        periodRemindersEnabled: true,
        sufficientData: false,
        estimatedStartDate: null,
        daysBeforePeriod: 2,
        notificationTimeHHMM: '09:00',
        now: now,
      );
      expect(result, isNull);
    });

    test('returns null when the computed fire time has already passed', () {
      final result = computeUpcomingPeriodReminderTime(
        periodRemindersEnabled: true,
        sufficientData: true,
        estimatedStartDate: DateTime(2026, 9, 2), // 2 days before = Aug 31, already past "now"
        daysBeforePeriod: 2,
        notificationTimeHHMM: '09:00',
        now: now,
      );
      expect(result, isNull);
    });

    test('computes the correct reminder date and time for a normal case', () {
      final result = computeUpcomingPeriodReminderTime(
        periodRemindersEnabled: true,
        sufficientData: true,
        estimatedStartDate: DateTime(2026, 9, 20),
        daysBeforePeriod: 3,
        notificationTimeHHMM: '09:30',
        now: now,
      );
      expect(result, isNotNull);
      expect(result!.year, 2026);
      expect(result.month, 9);
      expect(result.day, 17); // 20th minus 3 days
      expect(result.hour, 9);
      expect(result.minute, 30);
    });

    test('never assumes a fixed 28-day cycle — respects whatever estimate is given', () {
      // A short (21-day) and a long (35-day) cycle estimate both produce
      // exactly the date implied by the given estimatedStartDate, not a
      // hardcoded 28-day-cycle guess.
      final short = computeUpcomingPeriodReminderTime(
        periodRemindersEnabled: true,
        sufficientData: true,
        estimatedStartDate: DateTime(2026, 9, 22),
        daysBeforePeriod: 1,
        notificationTimeHHMM: '08:00',
        now: now,
      );
      final long = computeUpcomingPeriodReminderTime(
        periodRemindersEnabled: true,
        sufficientData: true,
        estimatedStartDate: DateTime(2026, 10, 6),
        daysBeforePeriod: 1,
        notificationTimeHHMM: '08:00',
        now: now,
      );
      expect(short!.day, 21);
      expect(long!.day, 5);
      expect(long.month, 10);
    });

    test('returns null on a malformed notification time rather than throwing', () {
      final result = computeUpcomingPeriodReminderTime(
        periodRemindersEnabled: true,
        sufficientData: true,
        estimatedStartDate: DateTime(2026, 9, 20),
        daysBeforePeriod: 2,
        notificationTimeHHMM: 'not-a-time',
        now: now,
      );
      expect(result, isNull);
    });

    test('ReminderFireTime equality and toLocalDateTime', () {
      const a = ReminderFireTime(year: 2026, month: 9, day: 17, hour: 9, minute: 30);
      const b = ReminderFireTime(year: 2026, month: 9, day: 17, hour: 9, minute: 30);
      expect(a, equals(b));
      expect(a.toLocalDateTime(), DateTime(2026, 9, 17, 9, 30));
    });
  });
}
