import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../config.dart';
import 'token_storage.dart';

/// Thrown for any non-2xx response. `message` is always the backend's
/// generic, non-leaky error text (backend/app/middleware/error_handling.py
/// never returns a raw exception string) — this app must not try to be
/// "smarter" than that message client-side.
class ApiException implements Exception {
  final int statusCode;
  final String message;
  final Map<String, dynamic>? body;

  ApiException(this.statusCode, this.message, [this.body]);

  @override
  String toString() => 'ApiException($statusCode): $message';
}

/// Thin wrapper around the backend REST API — the Dart equivalent of
/// apps/web/src/js/api.js and admin/dashboard/js/api.js. Same shape on
/// purpose: same 401-triggers-one-refresh-retry logic, same "auth"/"retry"
/// per-call flags, so all three clients are easy to reason about together
/// even though nothing generates one from another.
class ApiClient {
  ApiClient._();
  static final ApiClient instance = ApiClient._();

  final http.Client _http = http.Client();
  final Uri _base = Uri.parse(AppConfig.apiBaseUrl);

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final full = Uri.parse('${_base.toString()}$path');
    if (query == null || query.isEmpty) return full;
    return full.replace(queryParameters: {
      ...full.queryParameters,
      ...query.map((k, v) => MapEntry(k, v.toString())),
    });
  }

  Future<dynamic> request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, dynamic>? query,
    bool auth = true,
    bool retry = true,
  }) async {
    final headers = {'Content-Type': 'application/json'};
    if (auth) {
      final token = await TokenStorage.instance.getAccessToken();
      if (token != null) headers['Authorization'] = 'Bearer $token';
    }

    final uri = _uri(path, query);
    late http.Response response;
    switch (method) {
      case 'GET':
        response = await _http.get(uri, headers: headers);
        break;
      case 'POST':
        response = await _http.post(uri, headers: headers, body: body == null ? null : jsonEncode(body));
        break;
      case 'PUT':
        response = await _http.put(uri, headers: headers, body: body == null ? null : jsonEncode(body));
        break;
      case 'DELETE':
        response = await _http.delete(uri, headers: headers, body: body == null ? null : jsonEncode(body));
        break;
      default:
        throw ArgumentError('Unsupported method: $method');
    }

    if (response.statusCode == 401 && auth && retry) {
      final refreshed = await _tryRefresh();
      if (refreshed) {
        return request(method, path, body: body, query: query, auth: auth, retry: false);
      }
      await TokenStorage.instance.clear();
    }

    Map<String, dynamic>? data;
    if (response.body.isNotEmpty) {
      try {
        final decoded = jsonDecode(response.body);
        data = decoded is Map<String, dynamic> ? decoded : {'value': decoded};
      } catch (_) {
        data = {'detail': response.body};
      }
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      final message = (data?['detail'] as String?) ?? (data?['message'] as String?) ?? 'Something went wrong. Please try again.';
      throw ApiException(response.statusCode, message, data);
    }

    if (response.body.isEmpty) return null;
    return jsonDecode(response.body);
  }

  /// For binary responses (currently just the PDF report) — bypasses the
  /// JSON decoding `request()` does above. Same auth-header/401-retry
  /// behavior, since a binary export is just as auth-gated as any JSON one.
  Future<Uint8List> requestBytes(String path, {bool retry = true}) async {
    final token = await TokenStorage.instance.getAccessToken();
    final headers = <String, String>{if (token != null) 'Authorization': 'Bearer $token'};

    final response = await _http.get(_uri(path), headers: headers);

    if (response.statusCode == 401 && retry) {
      final refreshed = await _tryRefresh();
      if (refreshed) return requestBytes(path, retry: false);
      await TokenStorage.instance.clear();
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      String message = 'Something went wrong. Please try again.';
      try {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        message = (decoded['detail'] as String?) ?? message;
      } catch (_) {
        // Non-JSON error body — keep the generic message rather than
        // exposing raw bytes/text to the user.
      }
      throw ApiException(response.statusCode, message);
    }

    return response.bodyBytes;
  }

  Future<bool> _tryRefresh() async {
    final refreshToken = await TokenStorage.instance.getRefreshToken();
    if (refreshToken == null) return false;
    try {
      final data = await request(
        'POST',
        '/auth/refresh',
        body: {'refresh_token': refreshToken},
        auth: false,
        retry: false,
      );
      await TokenStorage.instance.setTokens(
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String,
      );
      return true;
    } catch (_) {
      return false;
    }
  }
}
