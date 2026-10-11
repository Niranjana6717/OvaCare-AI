enum ConsentType {
  coreService,
  healthDataProcessing,
  aiScreeningAcknowledgement,
  notificationPermission,
  analytics,
  researchModelImprovement;

  String get wireValue {
    switch (this) {
      case ConsentType.coreService:
        return 'core_service';
      case ConsentType.healthDataProcessing:
        return 'health_data_processing';
      case ConsentType.aiScreeningAcknowledgement:
        return 'ai_screening_acknowledgement';
      case ConsentType.notificationPermission:
        return 'notification_permission';
      case ConsentType.analytics:
        return 'analytics';
      case ConsentType.researchModelImprovement:
        return 'research_model_improvement';
    }
  }

  static ConsentType fromWire(String value) {
    return ConsentType.values.firstWhere((c) => c.wireValue == value);
  }

  /// Mirrors backend REQUIRED_CONSENT_TYPES — cannot be withdrawn while
  /// keeping the account active (requirement #61). Using the app is never
  /// treated as automatic consent for anything NOT in this set.
  bool get isRequired => this == ConsentType.coreService || this == ConsentType.healthDataProcessing;

  /// Plain-language label + description for this consent category. Kept in
  /// sync with apps/web/src/js/app.js's CONSENT_CATALOG — same six
  /// categories, same wording, so the product reads the same across
  /// platforms (not independently drafted per client).
  String get label {
    switch (this) {
      case ConsentType.coreService:
        return 'Service usage';
      case ConsentType.healthDataProcessing:
        return 'Health-data processing';
      case ConsentType.aiScreeningAcknowledgement:
        return 'AI screening';
      case ConsentType.notificationPermission:
        return 'Notifications';
      case ConsentType.analytics:
        return 'Analytics';
      case ConsentType.researchModelImprovement:
        return 'Research & model improvement';
    }
  }

  String get description {
    switch (this) {
      case ConsentType.coreService:
        return 'Creating your account and keeping the app working and secure. Required to use OvaCare.';
      case ConsentType.healthDataProcessing:
        return 'Storing the cycle, symptom, and assessment information you enter so OvaCare can track your '
            "health over time. Required to use OvaCare's core features.";
      case ConsentType.aiScreeningAcknowledgement:
        return 'Using an AI model to screen your assessment answers for patterns associated with PCOS. This is '
            'a screening tool, not a diagnosis. You can withdraw this and still use cycle and symptom tracking '
            "— you just won't be able to request new AI screening results.";
      case ConsentType.notificationPermission:
        return 'Sending you period and cycle reminder notifications, at the schedule and privacy level you '
            'choose below.';
      case ConsentType.analytics:
        return 'Collecting anonymized usage analytics (which screens are used, not your health responses) to '
            'help us improve the app.';
      case ConsentType.researchModelImprovement:
        return 'Allowing your de-identified assessment data to be used to improve the accuracy of future '
            'versions of the screening model.';
    }
  }
}

/// Mirrors backend/app/schemas/consent.py's ConsentResponse exactly —
/// field names (`accepted`, `accepted_at`, not `granted`/`created_at`)
/// matter here because this is sent over the wire, unlike a purely
/// internal model.
class ConsentRecord {
  final String id;
  final ConsentType consentType;
  final String consentVersion;
  final String policyVersion;
  final String appVersion;
  final bool accepted;
  final DateTime? acceptedAt; // null when accepted == false
  final DateTime? withdrawnAt;

  const ConsentRecord({
    required this.id,
    required this.consentType,
    required this.consentVersion,
    required this.policyVersion,
    required this.appVersion,
    required this.accepted,
    this.acceptedAt,
    this.withdrawnAt,
  });

  bool get isActive => accepted && withdrawnAt == null;

  factory ConsentRecord.fromJson(Map<String, dynamic> json) {
    return ConsentRecord(
      id: json['id'] as String,
      consentType: ConsentType.fromWire(json['consent_type'] as String),
      consentVersion: json['consent_version'] as String,
      policyVersion: json['policy_version'] as String,
      appVersion: json['app_version'] as String,
      accepted: json['accepted'] as bool,
      acceptedAt: json['accepted_at'] == null ? null : DateTime.parse(json['accepted_at'] as String),
      withdrawnAt: json['withdrawn_at'] == null ? null : DateTime.parse(json['withdrawn_at'] as String),
    );
  }
}
