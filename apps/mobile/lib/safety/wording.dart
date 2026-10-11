/// Client-side port of backend/app/safety/wording.py's banned-phrase
/// guard — a defense-in-depth check, not the primary control. The
/// primary control is still the backend: it is the only place that
/// constructs screening/result text, and this app renders that text
/// verbatim (see widgets/medical_disclaimer_banner.dart and
/// screens/assessment/assessment_flow_screen.dart's result step). This
/// file exists so a bug that somehow let unsafe wording reach the client
/// — a stale cached response, a future feature that assembles text
/// client-side, a regression — fails loudly in a widget test
/// (test/widgets/medical_disclaimer_banner_test.dart) rather than
/// silently rendering.
///
/// Patterns are kept in sync by hand with the Python source; if that
/// file's `_BANNED_PATTERNS` changes, update `forbiddenDiagnosticPhrases`
/// here in the same change (same convention as shared/README.md
/// describes for the cross-app contract files).
library;

/// Plain-text substrings for quick widget-test matching
/// (`find.textContaining`) — a subset of the regex patterns below,
/// covering the two requirement-#90-critical phrases directly: a result
/// must never claim the person does or does not have PCOS.
const List<String> forbiddenDiagnosticPhrases = [
  'you have pcos',
  'you do not have pcos',
  "you don't have pcos",
  'this proves',
  'you are healthy',
  'no need to see a doctor',
  'you can rule out',
];

final RegExp _bannedPattern = RegExp(
  [
    r'\byou have pcos\b',
    r'\byou do not have pcos\b',
    r"\byou don't have pcos\b",
    r'\bthis proves\b',
    r'\bconfirms (you|that you) (have|don’t have|do not have)\b',
    r'\bdiagnos(e|es|ed|is)\b.*\bpcos\b',
    r'\bpcos\b.*\bdiagnos',
    r'\byou are (healthy|fine|normal)\b',
    r'\bno need to see a doctor\b',
    r'\byou can rule out\b',
  ].join('|'),
  caseSensitive: false,
  dotAll: true,
);

class UnsafeWordingError implements Exception {
  final String message;
  UnsafeWordingError(this.message);

  @override
  String toString() => 'UnsafeWordingError: $message';
}

/// Throws [UnsafeWordingError] if [text] contains language this product
/// must never surface. Call this on any backend-provided result/estimate
/// text before rendering it, mirroring the backend's own
/// `assert_safe_wording` call sites (prediction_service, safety_service).
void assertSafeWording(String text) {
  final match = _bannedPattern.firstMatch(text);
  if (match != null) {
    throw UnsafeWordingError('Blocked unsafe wording pattern "${match.group(0)}" in outbound text.');
  }
}

/// Verbatim port of backend/app/safety/wording.py's
/// `NOTIFICATION_TEXT["upcoming_period"]` / `PRIVATE_NOTIFICATION_TEXT` —
/// used by services/local_reminder_service.dart so a locally-scheduled
/// device notification shows exactly the same wording the backend would
/// have used for the same reminder, honoring the person's privacy_mode
/// setting either way (requirement: notification privacy — detailed vs.
/// private text). Keep in sync by hand with the Python source, same
/// convention as `forbiddenDiagnosticPhrases` above.
String upcomingPeriodNotificationText(int daysBeforePeriod) =>
    'Your estimated period may start in about $daysBeforePeriod day(s).';

const String privateNotificationText = 'You have an OvaCare reminder.';
