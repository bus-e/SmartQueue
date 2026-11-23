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

  test('вход гостем сохраняет токен для следующих запросов', () async {
    final calls = <String>[];
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        calls.add('${request.method} ${request.url.path} ${request.headers['X-Guest-Token'] ?? '-'}');
        if (request.url.path.endsWith('/auth/guest')) {
          return http.Response.bytes(utf8.encode(jsonEncode({'token': 't1', 'user': {'id': 'u1', 'name': 'Мария'}})), 201);
        }
        return http.Response(jsonEncode({'id': 3, 'position': 2}), 201);
      }),
    );
    expect((await api.join('K7M2QX', 'Мария'))['position'], 2);
    expect(calls, ['POST /api/v1/auth/guest -', 'POST /api/v1/queues/K7M2QX/entries t1']);
  });

  test('me: 404 значит «не в очереди»', () async {
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async => http.Response.bytes(
          utf8.encode(jsonEncode({'error': {'code': 'NotFound', 'message': 'Вы не стоите в этой очереди'}})), 404)),
    )..guestToken = 't';
    expect(await api.me('K7M2QX'), isNull);
  });

  test('«Следующий» — PATCH записи со статусом served', () async {
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        expect(request.method, 'PATCH');
        expect(request.url.path, '/api/v1/entries/7');
        expect(jsonDecode(request.body), {'status': 'served'});
        return http.Response(jsonEncode({'id': 7, 'status': 'served'}), 200);
      }),
    )..guestToken = 't';
    expect((await api.setStatus(7, 'served'))['status'], 'served');
  });
}
