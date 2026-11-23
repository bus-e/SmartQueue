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

  Map<String, dynamic> _map(dynamic body) => Map<String, dynamic>.from(body as Map);

  Future<bool> health() async {
    final body = _read(await _http.get(_uri('/health'), headers: _headers));
    return body is Map && body['status'] == 'ok';
  }

  /// Вход без регистрации: сервер выдаёт токен гостя по имени.
  Future<String> guest(String name) async {
    final r = await _http.post(_uri('/auth/guest'), headers: _headers, body: jsonEncode({'name': name}));
    guestToken = _map(_read(r))['token'] as String;
    return guestToken!;
  }

  /// Очередь по коду: название, тип, статус, сколько ждут.
  Future<Map<String, dynamic>> queue(String code) async =>
      _map(_read(await _http.get(_uri('/queues/$code'), headers: _headers)));

  /// Создать очередь. Создатель обычной очереди сразу стоит первым.
  Future<Map<String, dynamic>> createQueue(String title, {String type = 'regular', int notifyBefore = 2}) async {
    final r = await _http.post(_uri('/queues'),
        headers: _headers,
        body: jsonEncode({'title': title, 'type': type, 'notify_before': notifyBefore, 'source': 'site'}));
    return _map(_read(r));
  }

  /// Встать в очередь. Без токена сначала входим гостем с этим именем.
  /// Повторный вызов возвращает уже существующую запись.
  Future<Map<String, dynamic>> join(String code, String name) async {
    if (guestToken == null) await guest(name);
    final r = await _http.post(_uri('/queues/$code/entries'), headers: _headers, body: jsonEncode({'source': 'site'}));
    return _map(_read(r));
  }

  /// Моя запись и позиция; null — я не стою в этой очереди.
  Future<Map<String, dynamic>?> me(String code) async {
    try {
      return _map(_read(await _http.get(_uri('/queues/$code/entries/me'), headers: _headers)));
    } on ApiError catch (e) {
      if (e.status == 404) return null;
      rethrow;
    }
  }

  /// Кто в очереди по порядку. Имена других видят только управляющие.
  Future<List<Map<String, dynamic>>> entries(String code) async {
    final body = _read(await _http.get(_uri('/queues/$code/entries'), headers: _headers)) as List;
    return body.map(_map).toList();
  }

  /// served — «Следующий»; left — выйти; removed — забрать управление у первого через 10 минут.
  Future<Map<String, dynamic>> setStatus(int entryId, String status) async {
    final r = await _http.patch(_uri('/entries/$entryId'), headers: _headers, body: jsonEncode({'status': status}));
    return _map(_read(r));
  }

  /// Адрес WebSocket очереди: сервер сообщает, что очередь изменилась.
  Uri events(String code) => Uri.parse('${baseUrl.replaceFirst('http', 'ws')}/api/v1/ws/queues/$code');
}
