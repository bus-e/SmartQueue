import 'package:flutter/material.dart';

import 'api.dart';
import 'queue_code.dart';
import 'screens/home.dart';
import 'screens/stub.dart';

/// Адрес сервера задаётся при сборке: --dart-define=API_URL=https://...
const apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://localhost:8080');

final api = ApiClient(baseUrl: apiUrl);

void main() => runApp(const SmartQueueApp());

class SmartQueueApp extends StatelessWidget {
  const SmartQueueApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SmartQueue',
      theme: ThemeData(colorSchemeSeed: Colors.blueGrey, useMaterial3: true),
      // Маршруты повторяют карту экранов.
      routes: {
        '/': (_) => const HomeScreen(),
        '/create': (_) => const StubScreen(title: 'Создание очереди', sprint: 'спринт 3'),
        '/position': (_) => const StubScreen(title: 'Моя позиция', sprint: 'спринт 2'),
        '/manage': (_) => const StubScreen(title: 'Управление', sprint: 'спринт 3'),
        '/operator': (_) => const StubScreen(title: 'Пульт оператора', sprint: 'спринт 4'),
        '/account': (_) => const StubScreen(title: 'Аккаунт', sprint: 'после обязательного'),
      },
      onGenerateRoute: (settings) {
        if (settings.name == '/join') {
          final code = settings.arguments as String;
          return MaterialPageRoute(
            builder: (_) => StubScreen(title: 'Вход в очередь ${QueueCode.pretty(code)}', sprint: 'спринт 2'),
          );
        }
        return null;
      },
    );
  }
}
