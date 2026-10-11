/// Mirrors backend/app/schemas/user.py's ProfileResponse exactly — a
/// single flat resource returned by GET /users/me. There is no separate
/// nested "profile" object and no id/role/is_active/created_at here;
/// those matter only to the admin portal, which reaches them through a
/// completely different endpoint (GET /admin/users), never this one.
class Profile {
  final String email;
  final String? fullName;
  final DateTime? dateOfBirth;
  final double? heightCm;
  final double? weightKg;

  /// Server-computed from height/weight. Informational only — never the
  /// primary determinant of a screening result anywhere in this app
  /// (requirement #54 CRITICAL PRODUCT RULES).
  final double? bmi;
  final String? country;
  final String? phone;
  final String timezone;

  const Profile({
    required this.email,
    this.fullName,
    this.dateOfBirth,
    this.heightCm,
    this.weightKg,
    this.bmi,
    this.country,
    this.phone,
    this.timezone = 'UTC',
  });

  factory Profile.fromJson(Map<String, dynamic> json) {
    return Profile(
      email: json['email'] as String,
      fullName: json['full_name'] as String?,
      dateOfBirth: json['date_of_birth'] == null ? null : DateTime.parse(json['date_of_birth'] as String),
      heightCm: (json['height_cm'] as num?)?.toDouble(),
      weightKg: (json['weight_kg'] as num?)?.toDouble(),
      bmi: (json['bmi'] as num?)?.toDouble(),
      country: json['country'] as String?,
      phone: json['phone'] as String?,
      timezone: json['timezone'] as String? ?? 'UTC',
    );
  }

  Map<String, dynamic> toUpdateJson() {
    return {
      'full_name': fullName,
      'date_of_birth': dateOfBirth?.toIso8601String().split('T').first,
      'height_cm': heightCm,
      'weight_kg': weightKg,
      'country': country,
      'phone': phone,
      'timezone': timezone,
    };
  }

  Profile copyWith({
    String? fullName,
    DateTime? dateOfBirth,
    double? heightCm,
    double? weightKg,
    String? country,
    String? phone,
    String? timezone,
  }) {
    return Profile(
      email: email,
      fullName: fullName ?? this.fullName,
      dateOfBirth: dateOfBirth ?? this.dateOfBirth,
      heightCm: heightCm ?? this.heightCm,
      weightKg: weightKg ?? this.weightKg,
      bmi: bmi,
      country: country ?? this.country,
      phone: phone ?? this.phone,
      timezone: timezone ?? this.timezone,
    );
  }
}
