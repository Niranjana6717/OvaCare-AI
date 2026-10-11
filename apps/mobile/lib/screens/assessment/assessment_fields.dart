/// Static description of the AI-screening questionnaire, hand-synced from
/// ml-platform/src/feature_schema.py's FEATURES list (verified against
/// that file directly, not guessed — see its docstring for full
/// citations and why some product-brief-mentioned fields like
/// testosterone/DHEA-S/SHBG are absent: the real dataset this schema is
/// built against doesn't have those columns).
///
/// Requirement #9 ("only use fields supported by the final validated
/// model") means the true authority for what's valid is the DEPLOYED
/// model's own model_metadata.json, re-checked server-side in
/// app/ml/preprocessing.py regardless of what this file asks for — this
/// list exists only so the app has something to render a form from
/// without a dedicated "describe your schema" endpoint, which doesn't
/// exist yet (a real gap, same one shared/README.md notes for the
/// contract files in general: if the model's feature set changes,
/// update this file in the same change, or add that endpoint).
library;

enum AssessmentFieldType { numeric, yesNo, cycleRegularity }

class AssessmentField {
  final String name; // matches the model's feature name exactly
  final String label;
  final AssessmentFieldType type;
  final bool required;
  final double? minValue;
  final double? maxValue;
  final String section;

  const AssessmentField({
    required this.name,
    required this.label,
    required this.type,
    required this.required,
    this.minValue,
    this.maxValue,
    required this.section,
  });
}

const String basicSection = 'Basic information';
const String menstrualSection = 'Menstrual cycle';
const String symptomSection = 'Visible symptoms';
const String clinicalSection = 'Optional clinical results';
const String lifestyleSection = 'Optional lifestyle';

const List<AssessmentField> assessmentFields = [
  // --- Required: basic + menstrual + visible-symptom fields, answerable
  // without a lab result (backend/app/ml/preprocessing.py returns
  // insufficient_data if any of these are missing) ---
  AssessmentField(name: 'age', label: 'Age', type: AssessmentFieldType.numeric, required: true, minValue: 10, maxValue: 60, section: basicSection),
  AssessmentField(name: 'bmi', label: 'BMI', type: AssessmentFieldType.numeric, required: true, minValue: 10, maxValue: 60, section: basicSection),
  AssessmentField(name: 'cycle_regularity', label: 'Cycle regularity', type: AssessmentFieldType.cycleRegularity, required: true, section: menstrualSection),
  AssessmentField(name: 'average_cycle_length_days', label: 'Average cycle length (days)', type: AssessmentFieldType.numeric, required: true, minValue: 10, maxValue: 90, section: menstrualSection),
  AssessmentField(name: 'acne', label: 'Acne', type: AssessmentFieldType.yesNo, required: true, section: symptomSection),
  AssessmentField(name: 'hair_growth_excess', label: 'Excess hair growth', type: AssessmentFieldType.yesNo, required: true, section: symptomSection),
  AssessmentField(name: 'hair_thinning', label: 'Hair thinning / hair loss', type: AssessmentFieldType.yesNo, required: true, section: symptomSection),
  AssessmentField(name: 'skin_darkening', label: 'Skin darkening', type: AssessmentFieldType.yesNo, required: true, section: symptomSection),
  AssessmentField(name: 'weight_gain', label: 'Recent weight gain', type: AssessmentFieldType.yesNo, required: true, section: symptomSection),

  // --- Optional: present in the source dataset, but a person may not
  // have these results. Missing values don't block a result — each gets
  // an "I don't have this result" opt-out (requirement #74). ---
  AssessmentField(name: 'fsh', label: 'FSH (mIU/mL)', type: AssessmentFieldType.numeric, required: false, minValue: 0, maxValue: 50, section: clinicalSection),
  AssessmentField(name: 'lh', label: 'LH (mIU/mL)', type: AssessmentFieldType.numeric, required: false, minValue: 0, maxValue: 50, section: clinicalSection),
  AssessmentField(name: 'fsh_lh_ratio', label: 'FSH/LH ratio', type: AssessmentFieldType.numeric, required: false, minValue: 0, maxValue: 20, section: clinicalSection),
  AssessmentField(name: 'amh', label: 'AMH (ng/mL)', type: AssessmentFieldType.numeric, required: false, minValue: 0, maxValue: 30, section: clinicalSection),
  AssessmentField(name: 'prolactin', label: 'Prolactin (ng/mL)', type: AssessmentFieldType.numeric, required: false, minValue: 0, maxValue: 100, section: clinicalSection),
  AssessmentField(name: 'tsh', label: 'TSH (mIU/L)', type: AssessmentFieldType.numeric, required: false, minValue: 0, maxValue: 20, section: clinicalSection),
  AssessmentField(name: 'follicle_count_left', label: 'Follicle count (left ovary)', type: AssessmentFieldType.numeric, required: false, minValue: 0, maxValue: 40, section: clinicalSection),
  AssessmentField(name: 'follicle_count_right', label: 'Follicle count (right ovary)', type: AssessmentFieldType.numeric, required: false, minValue: 0, maxValue: 40, section: clinicalSection),
  AssessmentField(name: 'fast_food_frequent', label: 'Frequent fast food consumption', type: AssessmentFieldType.yesNo, required: false, section: lifestyleSection),
  AssessmentField(name: 'regular_exercise', label: 'Regular exercise', type: AssessmentFieldType.yesNo, required: false, section: lifestyleSection),
];
