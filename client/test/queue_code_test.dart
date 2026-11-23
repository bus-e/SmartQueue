import 'package:flutter_test/flutter_test.dart';
import 'package:smartqueue/queue_code.dart';

void main() {
  test('верные коды', () {
    expect(QueueCode.isValid('K7M2QX'), isTrue);
    expect(QueueCode.isValid('k7m 2qx'), isTrue);
    expect(QueueCode.normalize('k7m 2qx'), 'K7M2QX');
    expect(QueueCode.pretty('K7M2QX'), 'K7M 2QX');
  });

  test('неверные коды', () {
    for (final raw in ['K7M2Q', 'K7M2QXA', 'K0M2QX', 'KOM2QX', 'K1M2QX', 'KIM2QX', '']) {
      expect(QueueCode.isValid(raw), isFalse, reason: raw);
    }
  });
}
