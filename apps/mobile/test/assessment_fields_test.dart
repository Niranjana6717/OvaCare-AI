import 'package:flutter_test/flutter_test.dart';
import 'package:ovacare_ai/screens/assessment/assessment_fields.dart';

// Written against the real ml-platform/src/feature_schema.py — see that
// file's FEATURES list — so this test is really checking "does the
// hand-synced Dart copy still match the 9 required + 9 optional fields
// the backend actually expects," not an arbitrary invariant. If this
// test starts failing after a schema.py change, assessment_fields.dart
// is what needs updating, not this test.
void main() {
  group('assessmentFields', () {
    test('has exactly 18 fields: 9 required + 9 optional', () {
      final required = assessmentFields.where((f) => f.required).toList();
      final optional = assessmentFields.where((f) => !f.required).toList();
      expect(required.length, 9);
      expect(optional.length, 9);
      expect(assessmentFields.length, 18);
    });

    test('every field name is unique', () {
      final names = assessmentFields.map((f) => f.name).toSet();
      expect(names.length, assessmentFields.length);
    });

    test('required fields match the model_loader.py "always askable" set', () {
      final requiredNames = assessmentFields.where((f) => f.required).map((f) => f.name).toSet();
      expect(requiredNames, {
        'age',
        'bmi',
        'cycle_regularity',
        'average_cycle_length_days',
        'acne',
        'hair_growth_excess',
        'hair_thinning',
        'skin_darkening',
        'weight_gain',
      });
    });

    test('cycle_regularity field type is cycleRegularity, not a generic yes/no', () {
      final field = assessmentFields.firstWhere((f) => f.name == 'cycle_regularity');
      expect(field.type, AssessmentFieldType.cycleRegularity);
    });
  });
}
