import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ovacare_ai/safety/wording.dart';
import 'package:ovacare_ai/widgets/medical_disclaimer_banner.dart';

// Deliberately doesn't pump the full OvaCareApp — that would touch
// flutter_secure_storage/http through AppState.bootstrap(), which need
// platform channel mocks this test doesn't set up. Testing the banner
// widget in isolation is both simpler and more targeted: it's the one
// widget every safety requirement in this file actually cares about.
void main() {
  testWidgets('renders the fallback disclaimer text when no override is given', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: MedicalDisclaimerBanner())),
    );
    expect(find.text(MedicalDisclaimerBanner.fallbackText), findsOneWidget);
  });

  testWidgets('renders backend-provided text verbatim when given an override', (tester) async {
    const backendText = 'This result is intended for health awareness and does not diagnose PCOS.';
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: MedicalDisclaimerBanner(overrideText: backendText))),
    );
    expect(find.text(backendText), findsOneWidget);
    expect(find.text(MedicalDisclaimerBanner.fallbackText), findsNothing);
  });

  testWidgets('never renders forbidden diagnostic phrasing in either mode', (tester) async {
    const backendText = 'Your responses produced a screening result that may warrant further discussion.';
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: MedicalDisclaimerBanner(overrideText: backendText))),
    );
    for (final phrase in forbiddenDiagnosticPhrases) {
      expect(find.textContaining(phrase, findRichText: true), findsNothing);
    }
  });
}
