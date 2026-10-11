# apps/mobile/ (and apps/desktop/)

Flutter/Dart source targeting Android, iOS, and desktop (Windows/macOS/
Linux — see `apps/desktop/README.md`; it's the same codebase, not a fork).

## Status: written, not compiled here

This sandbox has no Flutter SDK and no network access to install one
(see `docs/deployment.md`'s "Environment constraints encountered"). No
file under `lib/` or `test/` has been run through `flutter analyze`,
`flutter test`, or `flutter build` in this environment. What was done
instead, to keep this honest rather than just asserting it's fine:

- Every request/response model (`lib/models/`) was written by reading
  the actual backend Pydantic schemas (`backend/app/schemas/*.py`)
  field-by-field, not guessed from memory — including catching and
  fixing a real mismatch along the way (the consent endpoints use
  `accepted`/`accepted_at`, not `granted`/`created_at`; `cycles`
  responses include `period_duration_days` distinct from
  `cycle_length_days`; `/users/me` is a flat `ProfileResponse` with no
  nested object and no `role`/`id`). `shared/types/models.ts` and
  `shared/api-contracts/openapi.yaml` were corrected to match at the
  same time, so all three stayed in sync.
- Every `.dart` file was checked for balanced braces/parens/brackets as
  a basic sanity pass (not a substitute for a real compiler — see
  `.github/workflows/frontend-checks.yml`'s `flutter` job, which runs
  `flutter analyze` and `flutter test` for real on GitHub's runners).
- The questionnaire in `lib/screens/assessment/assessment_fields.dart`
  was built directly from `ml-platform/src/feature_schema.py`'s real
  `FEATURES` list (9 required + 9 optional), not invented — and
  `test/assessment_fields_test.dart` asserts that set stays in sync.
  Doing this surfaced a real gap in the already-shipped web app
  (`apps/web/`), which was only asking 5 of the 9 required fields and
  would therefore always receive `insufficient_data` back from a real
  model — that's fixed now too (see `apps/web/src/js/app.js`).
- `lib/safety/wording.dart` is a client-side, defense-in-depth port of
  `backend/app/safety/wording.py`'s banned-phrase guard, with its own
  test (`test/safety/wording_test.dart`) run against the same cases the
  backend's own test file checks.
- `lib/services/reminder_time.dart` is a plugin-free, pure port of
  `backend/app/services/notification_service.py`'s reminder-time
  calculation (real cycle-history-based estimate in, device-local
  fire time out, `null` if reminders are off / there isn't enough
  history yet / the time has already passed) — its own test is
  `test/services/reminder_time_test.dart`.

## Local notifications: platform setup still required

`lib/services/local_reminder_service.dart` schedules a real, local
"estimated period starting soon" notification via
`flutter_local_notifications` (no FCM/APNs push provider is configured
anywhere in this project — see `docs/deployment.md` — so this is
deliberately on-device scheduling, not a push notification). Because
`apps/mobile/android/` and `apps/mobile/ios/` are empty placeholders in
this repo (no `flutter create .` has been run here — there is no Flutter
SDK in this sandbox to run it), the platform-native files those
directories will contain don't exist yet for this change to edit. Once
`flutter create .` has generated them:

- **Android**: `flutter_local_notifications`' own setup docs require
  registering `com.dexterous.flutterlocalnotifications.ScheduledNotificationReceiver`
  and `ScheduledNotificationBootReceiver` in `AndroidManifest.xml`
  (the latter needs `<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>`
  so a scheduled reminder survives a device reboot), and — because
  `AndroidScheduleMode.exactAllowWhileIdle` is used here for a
  time-accurate reminder — `<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM"/>`
  on Android 12+ (API 31+).
- **iOS/macOS**: no manifest changes are required for local
  notifications specifically, but the standard notification-permission
  usage description strings apply if App Store review asks for one.

`local_reminder_service.dart`'s own header comment has the full
disclosure: its exact API calls against `flutter_local_notifications`
^17.2.3 could not be checked against real package docs in this
sandbox (no network access to pub.dev) — run `flutter analyze` first
and treat any signature mismatch there as the next fix, not a sign the
overall approach is wrong.

## Run it (once you have the Flutter SDK)

```bash
cd apps/mobile
flutter pub get
flutter run                                    # mobile
flutter run -d windows                         # or macos / linux
flutter run --dart-define=API_BASE_URL=https://api.example.com/api/v1
flutter analyze
flutter test
```

Default `API_BASE_URL` is `http://localhost:8000/api/v1`, matching
`apps/web/src/config.js` and `admin/dashboard/config.js`'s own
local-dev defaults (see `lib/config.dart`).

## Architecture

- `lib/models/` — wire-shape classes, `fromJson`/`toJson`, mirroring
  `shared/types/models.ts`.
- `lib/services/api_client.dart` — thin `http` wrapper with the same
  401-triggers-one-refresh-retry logic as `apps/web/src/js/api.js` and
  `admin/dashboard/js/api.js`.
- `lib/services/ovacare_api.dart` — typed methods over `api_client.dart`.
- `lib/services/token_storage.dart` — JWTs in `flutter_secure_storage`
  (OS keychain/keystore), never `SharedPreferences`.
- `lib/state/app_state.dart` — a single `ChangeNotifier` for
  auth/session state; `lib/app.dart`'s `_RootRouter` is the one place
  that decides login vs. consent vs. the main app shell.
- `lib/widgets/app_scaffold.dart` — the requirement #43 responsive
  layout: a bottom `NavigationBar` below `AppConfig.desktopBreakpoint`
  (780px, matching `apps/web`'s own breakpoint), a permanent
  `NavigationRail` with a constrained content width above it — not the
  same mobile screen stretched wide.
- `lib/screens/assessment/` — the questionnaire → review → result flow
  (requirement #75), including the red-flag safety fields and the
  "I don't have this result" per-field skip (requirement #74).
