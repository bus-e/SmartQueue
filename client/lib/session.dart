import 'package:shared_preferences/shared_preferences.dart';

/// Токен гостя сохраняется на устройстве (на сайте — в хранилище браузера),
/// чтобы после перезагрузки страницы человек снова видел своё место.
class Session {
  static const _key = 'guest_token';

  static Future<String?> load() async {
    try {
      return (await SharedPreferences.getInstance()).getString(_key);
    } catch (_) {
      return null; // хранилище недоступно — работаем без сохранения
    }
  }

  static Future<void> save(String token) async {
    try {
      await (await SharedPreferences.getInstance()).setString(_key, token);
    } catch (_) {}
  }
}
