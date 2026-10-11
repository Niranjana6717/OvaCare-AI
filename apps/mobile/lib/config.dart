/// OvaCare AI — app-wide configuration.
///
/// `apiBaseUrl` intentionally has no override mechanism beyond this
/// constant + the two platform-specific defaults below, unlike
/// apps/web/src/config.js's localStorage override — a mobile build is
/// compiled per-environment (dev/staging/prod flavors) rather than
/// configured at runtime, so the right place for that is Flutter's
/// `--dart-define` build flag, read here via `String.fromEnvironment`.
class AppConfig {
  const AppConfig._();

  /// Default local-dev backend, matching apps/web/src/config.js and
  /// admin/dashboard/config.js's own defaults. Override at build time:
  ///   flutter run --dart-define=API_BASE_URL=https://api.ovacare.example/api/v1
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000/api/v1',
  );

  static const String appName = 'OvaCare AI';

  /// Breakpoint above which the UI switches from a bottom-nav mobile
  /// layout to a permanent side-rail/desktop layout (requirement #43 —
  /// desktop must not just be a stretched mobile screen). Matches the
  /// 780px breakpoint apps/web/src/css/styles.css uses for the reverse
  /// transition, so the product feels consistent across platforms at
  /// the same physical width.
  static const double desktopBreakpoint = 780;
}
