enum SymptomType {
  acne,
  hairGrowthChanges,
  hairLoss,
  pelvicDiscomfort,
  fatigue,
  moodChanges,
  other;

  String get wireValue {
    switch (this) {
      case SymptomType.acne:
        return 'acne';
      case SymptomType.hairGrowthChanges:
        return 'hair_growth_changes';
      case SymptomType.hairLoss:
        return 'hair_loss';
      case SymptomType.pelvicDiscomfort:
        return 'pelvic_discomfort';
      case SymptomType.fatigue:
        return 'fatigue';
      case SymptomType.moodChanges:
        return 'mood_changes';
      case SymptomType.other:
        return 'other';
    }
  }

  static SymptomType fromWire(String value) {
    return SymptomType.values.firstWhere((s) => s.wireValue == value, orElse: () => SymptomType.other);
  }

  String get label {
    switch (this) {
      case SymptomType.acne:
        return 'Acne';
      case SymptomType.hairGrowthChanges:
        return 'Hair growth changes';
      case SymptomType.hairLoss:
        return 'Hair loss';
      case SymptomType.pelvicDiscomfort:
        return 'Pelvic discomfort';
      case SymptomType.fatigue:
        return 'Fatigue';
      case SymptomType.moodChanges:
        return 'Mood changes';
      case SymptomType.other:
        return 'Other';
    }
  }
}

/// Mirrors backend/app/schemas/symptom.py exactly. `severity` is REQUIRED
/// (not optional) and `customLabel` is required by a server-side
/// validator whenever `symptomType == SymptomType.other` — this app
/// enforces the same rule client-side (see screens/symptom_tracker_screen.dart)
/// so the form fails fast with a clear message instead of a 422 from the API.
class Symptom {
  final String? id;
  final SymptomType symptomType;
  final String? customLabel;
  final int severity; // 1-5
  final DateTime loggedDate;
  final String? notes;

  const Symptom({
    this.id,
    required this.symptomType,
    this.customLabel,
    required this.severity,
    required this.loggedDate,
    this.notes,
  });

  factory Symptom.fromJson(Map<String, dynamic> json) {
    return Symptom(
      id: json['id'] as String,
      symptomType: SymptomType.fromWire(json['symptom_type'] as String),
      customLabel: json['custom_label'] as String?,
      severity: json['severity'] as int,
      loggedDate: DateTime.parse(json['logged_date'] as String),
      notes: json['notes'] as String?,
    );
  }

  Map<String, dynamic> toCreateJson() {
    return {
      'symptom_type': symptomType.wireValue,
      'custom_label': customLabel,
      'severity': severity,
      'logged_date': loggedDate.toIso8601String().split('T').first,
      'notes': notes,
    };
  }
}
