/// Everything the review-before-submit screen (requirement #75) and the
/// safety-critical result screen (requirement #90) need. Field/shape
/// choices mirror shared/types/models.ts exactly.

enum ScreeningOutcome {
  lowerIndication,
  higherIndication,
  insufficientData;

  static ScreeningOutcome fromWire(String value) {
    switch (value) {
      case 'higher_indication':
        return ScreeningOutcome.higherIndication;
      case 'insufficient_data':
        return ScreeningOutcome.insufficientData;
      case 'lower_indication':
      default:
        return ScreeningOutcome.lowerIndication;
    }
  }
}

class AssessmentSubmitRequest {
  /// Keyed by the deployed model's OWN feature_schema field names — this
  /// app never hardcodes a fixed field set for the ML questionnaire,
  /// because the valid feature set is versioned by the model artifact,
  /// not this client (requirement #9).
  final Map<String, Object?> responses;
  final List<String> unansweredFields;

  // Red-flag safety fields — always collected, always sent, evaluated
  // independently of the ML model (requirement #67/#68).
  final bool soakingThroughProtectionHourly;
  final bool bleedingWithDizzinessOrFainting;
  final int? pelvicPainSeverity; // 1-5
  final bool faintingOrSevereDizziness;
  final bool chestPainOrBreathingDifficulty;

  const AssessmentSubmitRequest({
    required this.responses,
    this.unansweredFields = const [],
    this.soakingThroughProtectionHourly = false,
    this.bleedingWithDizzinessOrFainting = false,
    this.pelvicPainSeverity,
    this.faintingOrSevereDizziness = false,
    this.chestPainOrBreathingDifficulty = false,
  });

  Map<String, dynamic> toJson() {
    return {
      'responses': responses,
      'unanswered_fields': unansweredFields,
      'soaking_through_protection_hourly': soakingThroughProtectionHourly,
      'bleeding_with_dizziness_or_fainting': bleedingWithDizzinessOrFainting,
      'pelvic_pain_severity': pelvicPainSeverity,
      'fainting_or_severe_dizziness': faintingOrSevereDizziness,
      'chest_pain_or_breathing_difficulty': chestPainOrBreathingDifficulty,
    };
  }
}

class SafetyCheckResult {
  final bool urgent;
  final String? message;
  final List<String> triggeredRuleIds;

  const SafetyCheckResult({required this.urgent, this.message, this.triggeredRuleIds = const []});

  factory SafetyCheckResult.fromJson(Map<String, dynamic> json) {
    return SafetyCheckResult(
      urgent: json['urgent'] as bool,
      message: json['message'] as String?,
      triggeredRuleIds: (json['triggered_rule_ids'] as List?)?.cast<String>() ?? const [],
    );
  }
}

class PredictionResult {
  final String assessmentId;
  final ScreeningOutcome outcome;

  /// Pre-approved wording ONLY, exactly as the backend returns it. This
  /// app must never construct or alter this text client-side — see
  /// backend/app/safety/wording.py and requirement #90 tests 1/2: a
  /// result must never render "You have PCOS" or "You do not have
  /// PCOS" regardless of outcome.
  final String message;

  final double? probability; // null when outcome == insufficientData
  final String? explanationFraming;
  final Map<String, dynamic> explanation;
  final String? insufficientDataReason;

  // Full traceability (requirement #90 test 7) — this app displays these
  // as recorded, never re-derives or hides them.
  final String modelVersion;
  final String featureSchemaVersion;
  final String preprocessingVersion;
  final String thresholdVersion;
  final DateTime assessedAt;
  final String medicalDisclaimer;

  const PredictionResult({
    required this.assessmentId,
    required this.outcome,
    required this.message,
    required this.probability,
    required this.explanationFraming,
    required this.explanation,
    required this.insufficientDataReason,
    required this.modelVersion,
    required this.featureSchemaVersion,
    required this.preprocessingVersion,
    required this.thresholdVersion,
    required this.assessedAt,
    required this.medicalDisclaimer,
  });

  factory PredictionResult.fromJson(Map<String, dynamic> json) {
    return PredictionResult(
      assessmentId: json['assessment_id'] as String,
      outcome: ScreeningOutcome.fromWire(json['outcome'] as String),
      message: json['message'] as String,
      probability: (json['probability'] as num?)?.toDouble(),
      explanationFraming: json['explanation_framing'] as String?,
      explanation: (json['explanation'] as Map?)?.cast<String, dynamic>() ?? const {},
      insufficientDataReason: json['insufficient_data_reason'] as String?,
      modelVersion: json['model_version'] as String,
      featureSchemaVersion: json['feature_schema_version'] as String,
      preprocessingVersion: json['preprocessing_version'] as String,
      thresholdVersion: json['threshold_version'] as String,
      assessedAt: DateTime.parse(json['assessed_at'] as String),
      medicalDisclaimer: json['medical_disclaimer'] as String,
    );
  }
}

class AssessmentSubmitResponse {
  final String assessmentId;
  final SafetyCheckResult safety;
  final PredictionResult result;

  const AssessmentSubmitResponse({required this.assessmentId, required this.safety, required this.result});

  factory AssessmentSubmitResponse.fromJson(Map<String, dynamic> json) {
    return AssessmentSubmitResponse(
      assessmentId: json['assessment_id'] as String,
      safety: SafetyCheckResult.fromJson(json['safety'] as Map<String, dynamic>),
      result: PredictionResult.fromJson(json['result'] as Map<String, dynamic>),
    );
  }
}
