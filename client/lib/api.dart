import 'dart:convert';

import 'package:http/http.dart' as http;

/// Ошибка сервера в едином формате {error: {code, message}}.
class ApiError implements Exception {
  ApiError(this.status, this.code, this.message);

  final int status;
  final String code;
  final String message;

  @override
  String toString() => message;
}

/// Клиент API SmartQueue. Адреса и поля — по документу «API SmartQueue».
class ApiClient {
  ApiClient({required this.baseUrl, http.Client? client}) : _http = client ?? http.Client();

  final String baseUrl;
  final http.Client _http;

  /// Токен гостя; после входа прикладывается к каждому запросу.
  String? guestToken;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (guestToken != null) 'X-Guest-Token': guestToken!,
      };

  Uri _uri(String path) => Uri.parse('$baseUrl/api/v1$path');

  dynamic _read(http.Response r) {
    final body = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode >= 400) {
      final err = body is Map ? body['error'] as Map? : null;
      throw ApiError(r.statusCode, '${err?['code'] ?? 'unknown'}', '${err?['message'] ?? 'Ошибка сервера'}');
    }
    return body;
  }

  Future<bool> health() async {
    final body = _read(await _http.get(_uri('/health'), headers: _headers));
    return body is Map && body['status'] == 'ok';
  }

  /// Очередь по коду: название, тип, статус, длина.
  Future<Map<String, dynamic>> queue(String code) async =>
      Map<String, dynamic>.from(_read(await _http.get(_uri('/queues/$code'), headers: _headers)) as Map);

  /// Встать в очередь. Повторный вызов возвращает уже существующую запись.
  Future<Map<String, dynamic>> join(String code, String name) async {
    final r = await _http.post(_uri('/queues/$code/entries'),
        headers: _headers, body: jsonEncode({'name': name, 'source': 'site'}));
    return Map<String, dynamic>.from(_read(r) as Map);
  }
}
