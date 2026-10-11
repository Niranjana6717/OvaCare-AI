/// Real, on-device scheduling of the single "estimated period starting
/// soon" reminder (requirement: period reminder notifications, "real
/// cycle-history-based calculation, never assume a 28-day cycle", plus
/// graceful notification-permission handling).
///
/// No push provider (FCM/APNs) is configured anywhere in this project (see
/// docs/deployment.md's "Environment constraints encountered" /
/// EXTERNAL REQUIREMENTS) — that's what would be needed for the backend to
/// push a notification to a phone that isn't currently open. This class is
/// deliberately NOT that: it schedules a genuine local notification,
/// entirely from data already on the device (`GET /cycles/estimate` +
/// the saved `NotificationPreference`), using the OS's own notification
/// scheduler. That is real functionality, not a stub — it just can't wake
/// a fully-killed app the way a push notification could.
///
/// Disclosure (see apps/mobile/README.md "## Status: written, not compiled
/// here"): this file was hand-written against `flutter_local_notifications`
/// ^17.2.3's publicly documented API from memory — this sandbox has no
/// network access to pub.dev/pub.dev docs and no Flutter SDK to compile
/// against, so the exact method/class names below (in particular
/// `DarwinFlutterLocalNotificationsPlugin` and
/// `AndroidFlutterLocalNotificationsPlugin.requestNotificationsPermission`)
/// could not be verified against the pinned version. Run `flutter pub get`
/// then `flutter analyze` as the first step before relying on this file,
/// and see "Local notifications: platform setup still required" below for
/// the manifest/plist additions this also needs once `flutter create .` has
/// generated the (currently absent — see apps/mobile/android,
/// apps/mobile/ios) platform projects.
library;

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

import '../models/cycle_record.dart';
import '../models/notification_preference.dart';
import '../safety/wording.dart' as safety_wording;
import 'reminder_time.dart';

class LocalReminderService {
  LocalReminderService._();
  static final LocalReminderService instance = LocalReminderService._();

  /// Fixed id: there is only ever one meaningful "next period" reminder at
  /// a time. `syncUpcomingPeriodReminder` always cancels whatever was
  /// scheduled under this id before scheduling the new one (or scheduling
  /// nothing), so a preference change or a newly-logged cycle can never
  /// leave a stale reminder firing with an outdated date.
  static const int _upcomingPeriodNotificationId = 9001;

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;
    tz_data.initializeTimeZones();
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const darwinInit = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );
    try {
      await _plugin.initialize(
        const InitializationSettings(android: androidInit, iOS: darwinInit, macOS: darwinInit),
      );
    } catch (_) {
      // Best-effort: platform channels are unavailable outside a real
      // device/emulator/desktop build (e.g. a plain `dart run`). Reminder
      // scheduling degrades to a no-op rather than crashing app startup.
    }
    _initialized = true;
  }

  /// Requests OS notification permission. Safe to call more than once —
  /// both Android and iOS/macOS only ever show the system prompt on the
  /// first real call; an already-granted or already-permanently-denied
  /// state is simply reported back without re-prompting the person, so the
  /// caller can show the same graceful in-app note the web app shows for
  /// an already-decided `Notification.permission` (see
  /// apps/web/src/js/app.js's `notificationPermissionNote`).
  Future<bool> requestPermission() async {
    await initialize();
    try {
      final androidImpl = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
      if (androidImpl != null) {
        final granted = await androidImpl.requestNotificationsPermission();
        return granted ?? false;
      }
      final darwinImpl = _plugin.resolvePlatformSpecificImplementation<DarwinFlutterLocalNotificationsPlugin>();
      if (darwinImpl != null) {
        final granted = await darwinImpl.requestPermissions(alert: true, badge: true, sound: true);
        return granted ?? false;
      }
    } catch (_) {
      return false;
    }
    // Other desktop targets (see apps/desktop/README.md) have no OS-level
    // notification permission model in this plugin — nothing to request.
    return true;
  }

  Future<void> cancelUpcomingPeriodReminder() async {
    await initialize();
    try {
      await _plugin.cancel(_upcomingPeriodNotificationId);
    } catch (_) {
      // Best-effort — see class doc.
    }
  }

  /// Recomputes and (re)schedules the single upcoming-period reminder from
  /// the person's current cycle estimate and saved preference. Call this
  /// after login/app start, after saving notification preferences, and
  /// after logging or deleting a cycle — anywhere an input to the
  /// calculation could have changed. Never throws: scheduling a local
  /// reminder is best-effort and must never block the screen that called
  /// it (mirrors `run_prediction`'s own never-block-the-caller posture in
  /// prediction_service.py, applied here to a purely local operation).
  Future<void> syncUpcomingPeriodReminder({
    required CycleEstimateResponse estimate,
    required NotificationPreference preference,
  }) async {
    try {
      await initialize();
      final fireAt = computeUpcomingPeriodReminderTime(
        periodRemindersEnabled: preference.periodRemindersEnabled,
        sufficientData: estimate.sufficientData,
        estimatedStartDate: estimate.estimatedStartDate,
        daysBeforePeriod: preference.daysBeforePeriod,
        notificationTimeHHMM: preference.notificationTime,
        now: DateTime.now(),
      );

      await _plugin.cancel(_upcomingPeriodNotificationId);
      if (fireAt == null) return;

      // `TZDateTime.from` preserves the real-world instant of the
      // `DateTime` passed in — it does not reinterpret its wall-clock
      // fields — so this fires at the correct physical moment regardless
      // of what `tz.local`'s configured location is (see reminder_time.dart's
      // header comment for why device-local time, not the saved
      // `timezone` string, is used to compute that instant in the first
      // place).
      final scheduledDate = tz.TZDateTime.from(fireAt.toLocalDateTime(), tz.local);

      final body = preference.privacyMode
          ? safety_wording.privateNotificationText
          : safety_wording.upcomingPeriodNotificationText(preference.daysBeforePeriod);
      safety_wording.assertSafeWording(body);

      await _plugin.zonedSchedule(
        _upcomingPeriodNotificationId,
        'OvaCare',
        body,
        scheduledDate,
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'period_reminders',
            'Period reminders',
            channelDescription: 'Reminders about your estimated upcoming period.',
            importance: Importance.defaultImportance,
            priority: Priority.defaultPriority,
          ),
          iOS: DarwinNotificationDetails(),
          macOS: DarwinNotificationDetails(),
        ),
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      );
    } catch (_) {
      // Best-effort — see method doc. A plugin/platform failure here (no
      // platform channel available, permission not yet granted, exact-alarm
      // permission not yet granted on Android 12+ — see README) must never
      // surface as an error on whatever screen triggered the sync.
    }
  }
}
