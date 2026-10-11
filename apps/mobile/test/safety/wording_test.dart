import 'package:flutter_test/flutter_test.dart';
import 'package:ovacare_ai/safety/wording.dart';

// Mirrors backend/tests/test_safety_wording.py's TestAssertSafeWording
// cases directly — same inputs, same expected pass/fail — so a
// discrepancy between the Dart port and the Python source shows up as a
// failing test here rather than as a silent behavioral difference.
void main() {
  group('assertSafeWording', () {
    test('allows approved screening text', () {
      expect(
        () => assertSafeWording(
          'Your responses produced a screening result that may warrant further discussion with a healthcare professional.',
        ),
        returnsNormally,
      );
      expect(
        () => assertSafeWording(
          'The information you provided produced a lower screening indication in this model. '
          'This does not rule out PCOS or other health conditions.',
        ),
        returnsNormally,
      );
    });

    test('rejects a direct diagnostic claim', () {
      expect(() => assertSafeWording('You have PCOS.'), throwsA(isA<UnsafeWordingError>()));
      expect(() => assertSafeWording('you do not have pcos'), throwsA(isA<UnsafeWordingError>()));
    });

    test('rejects false reassurance', () {
      expect(() => assertSafeWording('You are healthy and have nothing to worry about.'),
          throwsA(isA<UnsafeWordingError>()));
      expect(() => assertSafeWording('There is no need to see a doctor.'), throwsA(isA<UnsafeWordingError>()));
    });

    test('rejects a "proof" claim', () {
      expect(() => assertSafeWording('This proves you have a hormonal imbalance.'),
          throwsA(isA<UnsafeWordingError>()));
    });

    test('is case-insensitive', () {
      expect(() => assertSafeWording('YOU HAVE PCOS'), throwsA(isA<UnsafeWordingError>()));
    });
  });
}
