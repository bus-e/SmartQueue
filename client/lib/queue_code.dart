/// Код очереди: 6 символов без похожих 0, O, 1, I. Правило то же, что на сервере.
class QueueCode {
  static const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

  /// Убирает пробелы и приводит к верхнему регистру: «k7m 2qx» -> «K7M2QX».
  static String normalize(String raw) => raw.replaceAll(' ', '').toUpperCase();

  static bool isValid(String raw) {
    final code = normalize(raw);
    return code.length == 6 && code.split('').every(alphabet.contains);
  }

  /// Для показа на экране: «K7M 2QX».
  static String pretty(String code) => '${code.substring(0, 3)} ${code.substring(3)}';
}
