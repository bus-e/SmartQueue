import 'package:flutter_test/flutter_test.dart';
import 'package:smartqueue/sun.dart';

void main() {
  test('Ижевск 26.11: восход около 08:20, закат около 15:50 по местному (UTC+4)', () {
    final t = sunTimes(DateTime.utc(2026, 11, 26, 12), 56.85, 53.2);
    final rise = t.rise!.add(const Duration(hours: 4));
    final set = t.set!.add(const Duration(hours: 4));
    expect(rise.hour * 60 + rise.minute, inInclusiveRange(7 * 60 + 50, 8 * 60 + 50));
    expect(set.hour * 60 + set.minute, inInclusiveRange(15 * 60 + 20, 16 * 60 + 20));
  });

  test('днём светлая, после заката тёмная', () {
    final t = sunTimes(DateTime.utc(2026, 11, 26, 12), 56.85, 53.2);
    expect(t.isDark(DateTime.utc(2026, 11, 26, 9)), isFalse); // 13:00 по местному
    expect(t.isDark(DateTime.utc(2026, 11, 26, 16)), isTrue); // 20:00 по местному
  });

  test('полярная ночь — всегда тёмная', () {
    final t = sunTimes(DateTime.utc(2026, 12, 21, 12), 78.2, 15.6);
    expect(t.polar, 'night');
    expect(t.isDark(DateTime.utc(2026, 12, 21, 12)), isTrue);
  });

  test('место по часовому поясу: UTC+4 — долгота 60°', () {
    expect(placeFromOffset(const Duration(hours: 4)).lon, 60);
  });
}
