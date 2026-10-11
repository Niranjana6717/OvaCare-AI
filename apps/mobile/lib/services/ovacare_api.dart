import 'dart:typed_data';

import '../models/assessment.dart';
import '../models/consent.dart';
import '../models/cycle_record.dart';
import '../models/notification_preference.dart';
import '../models/symptom.dart';
import '../models/user.dart';
import 'api_client.dart';
import 'token_storage.dart';

/// Typed methods over ApiClient — the same endpoint surface as
/// apps/web/src/js/api.js and admin/dashboard/js/api.js's api clients,
/// mirroring shared/api-contracts/openapi.yaml.
class OvaCareApi {
  OvaCareApi._();
  static final OvaCareApi instance = OvaCareApi._();

  final ApiClient _client = ApiClient.instance;

  Future<void> register(String email, String password) async {
    final data = await _client.request('POST', '/auth/register', body: {'email': email, 'password': password}, auth: false);
    await TokenStorage.instance.setTokens(accessToken: data['access_token'], refreshToken: data['refresh_token']);
  }

  Future<void> login(String email, String password) async {
    final data = await _client.request('POST', '/auth/login', body: {'email': email, 'password': password}, auth: false);
    await TokenStorage.instance.setTokens(accessToken: data['access_token'], refreshToken: data['refresh_token']);
  }

  Future<void> logout() async {
    final refreshToken = await TokenStorage.instance.getRefreshToken();
    try {
      await _client.request('POST', '/auth/logout', body: {'refresh_token': refreshToken});
    } finally {
      await TokenStorage.instance.clear();
    }
  }

  Future<void> forgotPassword(String email) {
    return _client.request('POST', '/auth/forgot-password', body: {'email': email}, auth: false);
  }

  // --- Profile ---

  Future<Profile> getMe() async {
    final data = await _client.request('GET', '/users/me');
    return Profile.fromJson(data as Map<String, dynamic>);
  }

  Future<Profile> updateMe(Profile profile) async {
    final data = await _client.request('PUT', '/users/me', body: profile.toUpdateJson());
    return Profile.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteMe() async {
    await _client.request('DELETE', '/users/me');
    await TokenStorage.instance.clear();
  }

  // --- Consent ---

  Future<List<ConsentRecord>> getConsents() async {
    final data = await _client.request('GET', '/consent') as List;
    return data.map((e) => ConsentRecord.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<ConsentRecord> submitConsent(
    ConsentType type, {
    bool accepted = true,
    String consentVersion = '1.0.0',
    String policyVersion = '1.0.0',
    String appVersion = '0.1.0',
  }) async {
    final data = await _client.request('POST', '/consent', body: {
      'consent_type': type.wireValue,
      'accepted': accepted,
      'consent_version': consentVersion,
      'policy_version': policyVersion,
      'app_version': appVersion,
    });
    return ConsentRecord.fromJson(data as Map<String, dynamic>);
  }

  Future<ConsentRecord> withdrawConsent(ConsentType type) async {
    final data = await _client.request('PUT', '/consent/${type.wireValue}');
    return ConsentRecord.fromJson(data as Map<String, dynamic>);
  }

  // --- Cycles ---

  Future<List<CycleRecord>> listCycles() async {
    final data = await _client.request('GET', '/cycles') as List;
    return data.map((e) => CycleRecord.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<CycleRecord> createCycle(CycleRecord cycle) async {
    final data = await _client.request('POST', '/cycles', body: cycle.toCreateJson());
    return CycleRecord.fromJson(data as Map<String, dynamic>);
  }

  Future<CycleRecord> updateCycle(String id, CycleRecord cycle) async {
    final data = await _client.request('PUT', '/cycles/$id', body: cycle.toCreateJson());
    return CycleRecord.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteCycle(String id) => _client.request('DELETE', '/cycles/$id');

  Future<CycleSummary> cycleSummary() async {
    final data = await _client.request('GET', '/cycles/summary');
    return CycleSummary.fromJson(data as Map<String, dynamic>);
  }

  Future<CycleEstimateResponse> cycleEstimate() async {
    final data = await _client.request('GET', '/cycles/estimate');
    return CycleEstimateResponse.fromJson(data as Map<String, dynamic>);
  }

  // --- Symptoms ---

  Future<List<Symptom>> listSymptoms() async {
    final data = await _client.request('GET', '/symptoms') as List;
    return data.map((e) => Symptom.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Symptom> createSymptom(Symptom symptom) async {
    final data = await _client.request('POST', '/symptoms', body: symptom.toCreateJson());
    return Symptom.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteSymptom(String id) => _client.request('DELETE', '/symptoms/$id');

  // --- Assessments / predictions ---

  Future<String> submitAssessment(AssessmentSubmitRequest request) async {
    final data = await _client.request('POST', '/assessments', body: request.toJson());
    return (data as Map<String, dynamic>)['assessment_id'] as String;
  }

  Future<AssessmentSubmitResponse> requestPrediction(String assessmentId) async {
    final data = await _client.request('POST', '/predictions', body: {'assessment_id': assessmentId});
    return AssessmentSubmitResponse.fromJson(data as Map<String, dynamic>);
  }

  Future<List<PredictionResult>> predictionHistory() async {
    final data = await _client.request('GET', '/predictions/history') as List;
    return data.map((e) => PredictionResult.fromJson(e as Map<String, dynamic>)).toList();
  }

  // --- Insights ---

  Future<Map<String, dynamic>> getInsights() async {
    final data = await _client.request('GET', '/insights');
    return data as Map<String, dynamic>;
  }

  // --- Reports (requirement: PDF export in addition to, not replacing, JSON) ---

  Future<Map<String, dynamic>> getReport() async {
    final data = await _client.request('GET', '/reports');
    return data as Map<String, dynamic>;
  }

  /// Raw PDF bytes for GET /reports/pdf — the caller (settings_screen.dart)
  /// writes these to a file via path_provider; nothing here touches the
  /// filesystem, keeping this client symmetric with the rest of this file.
  Future<Uint8List> downloadReportPdfBytes() => _client.requestBytes('/reports/pdf');

  // --- Notifications ---

  Future<NotificationPreference> getNotificationPreferences() async {
    final data = await _client.request('GET', '/notifications/preferences');
    return NotificationPreference.fromJson(data as Map<String, dynamic>);
  }

  Future<NotificationPreference> updateNotificationPreferences(NotificationPreference prefs) async {
    final data = await _client.request('PUT', '/notifications/preferences', body: prefs.toJson());
    return NotificationPreference.fromJson(data as Map<String, dynamic>);
  }
}
