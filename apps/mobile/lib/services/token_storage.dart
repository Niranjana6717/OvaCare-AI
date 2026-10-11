import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// JWT access/refresh token storage. Uses the OS-level secure storage
/// (Keychain on iOS, Keystore-backed EncryptedSharedPreferences on
/// Android) rather than SharedPreferences, which stores plaintext on
/// disk — see docs/security.md's "no secrets in source, no secrets
/// unencrypted at rest" policy, applied here to the client side too.
class TokenStorage {
  TokenStorage._();
  static final TokenStorage instance = TokenStorage._();

  static const _accessKey = 'ovacare_access_token';
  static const _refreshKey = 'ovacare_refresh_token';

  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  Future<String?> getAccessToken() => _storage.read(key: _accessKey);
  Future<String?> getRefreshToken() => _storage.read(key: _refreshKey);

  Future<void> setTokens({required String accessToken, required String refreshToken}) async {
    await _storage.write(key: _accessKey, value: accessToken);
    await _storage.write(key: _refreshKey, value: refreshToken);
  }

  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }

  Future<bool> hasSession() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }
}
