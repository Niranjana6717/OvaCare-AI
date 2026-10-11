enum FlowLevel {
  spotting,
  light,
  medium,
  heavy;

  String get wireValue => name;

  static FlowLevel? fromWire(String? value) {
    if (value == null) return null;
    return FlowLevel.values.firstWhere((f) => f.wireValue == value, orElse: () => FlowLevel.medium);
  }

  String get label {
    switch (this) {
      case FlowLevel.spotting:
        return 'Spotting';
      case FlowLevel.light:
        return 'Light';
      case FlowLevel.medium:
        return 'Medium';
      case FlowLevel.heavy:
        return 'Heavy';
    }
  }
}

/// Mirrors backend/app/schemas/cycle.py exactly (CycleCreateRequest /
/// CycleResponse) — field names and shapes verified directly against
/// that file, not guessed, including `period_duration_days`, which is
/// easy to miss/confuse with `cycle_length_days` (they measure different
/// things: cycle_length_days is start-to-start vs. the PREVIOUS period;
/// period_duration_days is this period's own start-to-end span).
class CycleRecord {
  final String? id; // null for a not-yet-created record built client-side
  final DateTime startDate;
  final DateTime? endDate;
  final FlowLevel? flowLevel;
  final String? notes;

  /// Server-computed vs. the previous logged period. Null for the first
  /// entry ever logged. NEVER defaulted to 28 anywhere in this app —
  /// requirement #16/#54.
  final int? cycleLengthDays;

  /// Server-computed from this record's own start_date -> end_date, when
  /// end_date is set. Null otherwise.
  final int? periodDurationDays;

  const CycleRecord({
    this.id,
    required this.startDate,
    this.endDate,
    this.flowLevel,
    this.notes,
    this.cycleLengthDays,
    this.periodDurationDays,
  });

  factory CycleRecord.fromJson(Map<String, dynamic> json) {
    return CycleRecord(
      id: json['id'] as String,
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: json['end_date'] == null ? null : DateTime.parse(json['end_date'] as String),
      flowLevel: FlowLevel.fromWire(json['flow_level'] as String?),
      notes: json['notes'] as String?,
      cycleLengthDays: json['cycle_length_days'] as int?,
      periodDurationDays: json['period_duration_days'] as int?,
    );
  }

  Map<String, dynamic> toCreateJson() {
    return {
      'start_date': startDate.toIso8601String().split('T').first,
      'end_date': endDate?.toIso8601String().split('T').first,
      'flow_level': flowLevel?.wireValue,
      'notes': notes,
    };
  }
}

class CycleSummary {
  final bool sufficientData; // false below MIN_CYCLES_FOR_AVERAGE (2)
  final String? message; // present when sufficientData is false
  final double? averageCycleLengthDays;
  final double? averagePeriodDurationDays;
  final double? cycleVariabilityStdevDays;

  /// True when cycleVariabilityStdevDays exceeds the backend's
  /// HIGH_VARIABILITY_STDEV_DAYS threshold. Carries NO diagnostic claim
  /// by itself — pair with the neutral wording matching
  /// backend/app/safety/wording.py's IRREGULAR_CYCLE_NEUTRAL_TEXT
  /// (requirement #83: "Irregular cycles = PCOS" is explicitly forbidden
  /// logic).
  final bool isHighVariability;
  final List<CycleRecord> history;

  const CycleSummary({
    required this.sufficientData,
    required this.message,
    required this.averageCycleLengthDays,
    required this.averagePeriodDurationDays,
    required this.cycleVariabilityStdevDays,
    required this.isHighVariability,
    required this.history,
  });

  factory CycleSummary.fromJson(Map<String, dynamic> json) {
    return CycleSummary(
      sufficientData: json['sufficient_data'] as bool,
      message: json['message'] as String?,
      averageCycleLengthDays: (json['average_cycle_length_days'] as num?)?.toDouble(),
      averagePeriodDurationDays: (json['average_period_duration_days'] as num?)?.toDouble(),
      cycleVariabilityStdevDays: (json['cycle_variability_stdev_days'] as num?)?.toDouble(),
      isHighVariability: json['is_high_variability'] as bool,
      history: (json['history'] as List? ?? const [])
          .map((e) => CycleRecord.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class CycleEstimateResponse {
  final bool sufficientData; // false below MIN_CYCLES_FOR_ESTIMATE (2)
  final String? message; // e.g. "We need more cycle history to provide a useful personalized estimate."
  final DateTime? estimatedStartDate;
  final int basedOnCycleCount;

  /// Always render this label ("Estimated next period") — never "Your
  /// next period will start on..." (requirement #54/#84).
  final String label;

  const CycleEstimateResponse({
    required this.sufficientData,
    required this.message,
    required this.estimatedStartDate,
    required this.basedOnCycleCount,
    required this.label,
  });

  factory CycleEstimateResponse.fromJson(Map<String, dynamic> json) {
    return CycleEstimateResponse(
      sufficientData: json['sufficient_data'] as bool,
      message: json['message'] as String?,
      estimatedStartDate:
          json['estimated_start_date'] == null ? null : DateTime.parse(json['estimated_start_date'] as String),
      basedOnCycleCount: json['based_on_cycle_count'] as int,
      label: json['label'] as String? ?? 'Estimated next period',
    );
  }
}
