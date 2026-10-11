import 'package:flutter/foundation.dart';

import '../models/user.dart';
import '../services/local_reminder_service.dart';
import '../services/ovacare_api.dart';
import '../services/token_storage.dart';

enum AuthStatus { unknown, signedOut, signedIn }

/// App-wide session state — the Dart equivalent of the auth-gating logic
/// in apps/web/src/js/app.js's router() (redirect to login when signed
/// out, redirect away from login when already signed in), implemented
/// here as a ChangeNotifier that widgets/screens/app.dart watches instead
/// of a hash router, since Flutter has its own navigation stack.
class AppState extends ChangeNotifier {
  AuthStatus status = AuthStatus.unknown;
  Profile? currentProfile;

  /// True for exactly one app session, right after a successful
  /// register() call — mirrors apps/web/src/js/app.js's register flow,
  /// which routes straight to #/consent after account creation and never
  /// re-prompts an already-registered user who simply logs back in.
  bool justRegistered = false;

  Future<void> bootstrap() async {
    final hasSession = await TokenStorage.instance.hasSession();
    if (!hasSession) {
      status = AuthStatus.signedOut;
      notifyListeners();
      return;
    }
    try {
      currentProfile = await OvaCareApi.instance.getMe();
      status = AuthStatus.signedIn;
      await _syncReminder();
    } catch (_) {
      // Access token present but rejected even after the API client's
      // own refresh-retry — treat as signed out rather than looping.
      await TokenStorage.instance.clear();
      status = AuthStatus.signedOut;
    }
    notifyListeners();
  }

  Future<void> login(String email, String password) async {
    await OvaCareApi.instance.login(email, password);
    currentProfile = await OvaCareApi.instance.getMe();
    justRegistered = false;
    status = AuthStatus.signedIn;
    notifyListeners();
    await _syncReminder();
  }

  Future<void> register(String email, String password) async {
    await OvaCareApi.instance.register(email, password);
    currentProfile = await OvaCareApi.instance.getMe();
    justRegistered = true;
    status = AuthStatus.signedIn;
    notifyListeners();
    // No cycle history yet right after registration, so there is nothing
    // for LocalReminderService to schedule — skipped here deliberately
    // rather than calling it just to compute a no-op; the settings and
    // cycle-tracker screens each sync it once real data exists.
  }

  void consentCompleted() {
    justRegistered = false;
    notifyListeners();
  }

  Future<void> logout() async {
    await OvaCareApi.instance.logout();
    currentProfile = null;
    status = AuthStatus.signedOut;
    // A locally-scheduled reminder is tied to whichever account was signed
    // in when it was scheduled — never leave it armed for the next person
    // to sign into this device (notification-privacy requirement).
    await LocalReminderService.instance.cancelUpcomingPeriodReminder();
    notifyListeners();
  }

  /// Best-effort resync of the local upcoming-period reminder from the
  /// account's current cycle estimate + saved notification preference.
  /// Never throws (LocalReminderService itself never does) and never
  /// blocks sign-in on a plugin/platform failure.
  Future<void> _syncReminder() async {
    try {
      final estimate = await OvaCareApi.instance.cycleEstimate();
      final preference = await OvaCareApi.instance.getNotificationPreferences();
      await LocalReminderService.instance.syncUpcomingPeriodReminder(
        estimate: estimate,
        preference: preference,
      );
    } catch (_) {
      // Best-effort — see method doc.
    }
  }

  Future<void> refreshCurrentProfile() async {
    currentProfile = await OvaCareApi.instance.getMe();
    notifyListeners();
  }
}
