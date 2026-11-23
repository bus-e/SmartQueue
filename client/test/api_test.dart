import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smartqueue/api.dart';

void main() {
  test('health: сервер отвечает', () async {
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        expect(request.url.path, '/api/v1/health');
        return http.Response(jsonEncode({'status': 'ok'}), 200);
      }),
    );
    expect(await api.health(), isTrue);
  });

  test('ошибка сервера превращается в ApiError с текстом для пользователя', () async {
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async => http.Response.bytes(
          utf8.encode(jsonEncode({
            'error': {'code': 'queue_closed', 'message': 'Очередь завершена'}
          })),
          410)),
    );
    expect(
      () => api.join('K7M2QX', 'Мария'),
      throwsA(isA<ApiError>().having((e) => e.status, 'status', 410).having((e) => e.message, 'message', 'Очередь завершена')),
    );
  });

  test('токен гостя уходит в заголовке', () async {
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        expect(request.headers['X-Guest-Token'], 'abc');
        return http.Response(jsonEncode({'entry_id': 1, 'position': 5}), 201);
      }),
    )..guestToken = 'abc';
    expect((await api.join('K7M2QX', 'Мария'))['position'], 5);
  });
}
