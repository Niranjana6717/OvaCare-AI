class NotificationPreference {
  final bool periodRemindersEnabled;
  final int daysBeforePeriod; // one of 1, 2, 3, 5
  final String notificationTime; // "HH:MM", 24h
  final bool cycleRemindersEnabled;
  final bool symptomRemindersEnabled;

  /// Defaults true server-side. When true, delivered notification text is
  /// only the generic "You have an OvaCare reminder." — never health
  /// content on a lock screen (requirement #21, requirement #90 test 6).
  final bool privacyMode;
  final String timezone;

  const NotificationPreference({
    required this.periodRemindersEnabled,
    required this.daysBeforePeriod,
    required this.notificationTime,
    required this.cycleRemindersEnabled,
    required this.symptomRemindersEnabled,
    required this.privacyMode,
    required this.timezone,
  });

  static const List<int> daysBeforeOptions = [1, 2, 3, 5];

  factory NotificationPreference.fromJson(Map<String, dynamic> json) {
    return NotificationPreference(
      periodRemindersEnabled: json['period_reminders_enabled'] as bool,
      daysBeforePeriod: json['days_before_period'] as int,
      notificationTime: (json['notification_time'] as String).substring(0, 5),
      cycleRemindersEnabled: json['cycle_reminders_enabled'] as bool,
      symptomRemindersEnabled: json['symptom_reminders_enabled'] as bool,
      privacyMode: json['privacy_mode'] as bool,
      timezone: json['timezone'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'period_reminders_enabled': periodRemindersEnabled,
      'days_before_period': daysBeforePeriod,
      'notification_time': '$notificationTime:00',
      'cycle_reminders_enabled': cycleRemindersEnabled,
      'symptom_reminders_enabled': symptomRemindersEnabled,
      'privacy_mode': privacyMode,
      'timezone': timezone,
    };
  }

  NotificationPreference copyWith({
    bool? periodRemindersEnabled,
    int? daysBeforePeriod,
    String? notificationTime,
    bool? cycleRemindersEnabled,
    bool? symptomRemindersEnabled,
    bool? privacyMode,
    String? timezone,
  }) {
    return NotificationPreference(
      periodRemindersEnabled: periodRemindersEnabled ?? this.periodRemindersEnabled,
      daysBeforePeriod: daysBeforePeriod ?? this.daysBeforePeriod,
      notificationTime: notificationTime ?? this.notificationTime,
      cycleRemindersEnabled: cycleRemindersEnabled ?? this.cycleRemindersEnabled,
      symptomRemindersEnabled: symptomRemindersEnabled ?? this.symptomRemindersEnabled,
      privacyMode: privacyMode ?? this.privacyMode,
      timezone: timezone ?? this.timezone,
    );
  }
}
