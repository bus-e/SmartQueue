import 'package:flutter/material.dart';

import 'api.dart';
import 'queue_code.dart';
import 'screens/home.dart';
import 'screens/join.dart';
import 'screens/position.dart';
import 'screens/stub.dart';
import 'sun.dart';
import 'theme.dart';

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
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      // тема по солнцу: после заката тёмная, после восхода светлая
      themeMode: isDarkNow() ? ThemeMode.dark : ThemeMode.light,
      // Маршруты повторяют карту экранов.
      routes: {
        '/': (_) => const HomeScreen(),
        '/create': (_) => const StubScreen(title: 'Создание очереди', sprint: 'спринт 3'),
        '/manage': (_) => const StubScreen(title: 'Управление', sprint: 'спринт 3'),
        '/operator': (_) => const StubScreen(title: 'Пульт оператора', sprint: 'спринт 4'),
        '/account': (_) => const StubScreen(title: 'Аккаунт', sprint: 'после обязательного'),
      },
      onGenerateRoute: (settings) {
        final name = settings.name ?? '';
        // ссылка из QR: /q/K7M2QX
        if (name.startsWith('/q/') && QueueCode.isValid(name.substring(3))) {
          final code = QueueCode.normalize(name.substring(3));
          return MaterialPageRoute(builder: (_) => JoinScreen(api: api, code: code), settings: settings);
        }
        if (name == '/join') {
          final code = settings.arguments as String;
          return MaterialPageRoute(builder: (_) => JoinScreen(api: api, code: code), settings: settings);
        }
        if (name == '/position') {
          final code = settings.arguments as String;
          return MaterialPageRoute(builder: (_) => PositionScreen(api: api, code: code), settings: settings);
        }
        return null;
      },
    );
  }
}
