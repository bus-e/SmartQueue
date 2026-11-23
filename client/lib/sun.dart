import 'dart:math';

/// Восход и закат по уравнению восхода (с поправкой на рефракцию −0,833°).
/// По ним тема переключается сама: после заката тёмная, после восхода светлая.
class SunTimes {
  const SunTimes(this.rise, this.set, {this.polar});

  final DateTime? rise;
  final DateTime? set;

  /// 'day' — полярный день, 'night' — полярная ночь.
  final String? polar;

  bool isDark(DateTime now) {
    if (polar != null) return polar == 'night';
    return now.isBefore(rise!) || !now.isBefore(set!);
  }
}

SunTimes sunTimes(DateTime date, double lat, double lon) {
  const r = pi / 180;
  final j = date.toUtc().millisecondsSinceEpoch / 864e5 + 2440587.5;
  // ближайший к этому моменту солнечный полдень — значит, восход и закат текущих суток
  final n = (j - 2451545 + lon / 360).roundToDouble();
  final js = n - lon / 360;
  final m = (357.5291 + 0.98560028 * js) % 360;
  final c = 1.9148 * sin(m * r) + 0.02 * sin(2 * m * r) + 0.0003 * sin(3 * m * r);
  final l = (m + c + 180 + 102.9372) % 360;
  final jt = 2451545 + js + 0.0053 * sin(m * r) - 0.0069 * sin(2 * l * r);
  final sd = sin(l * r) * sin(23.4397 * r);
  final cd = cos(asin(sd));
  final cw = (sin(-0.833 * r) - sin(lat * r) * sd) / (cos(lat * r) * cd);
  if (cw > 1) return const SunTimes(null, null, polar: 'night');
  if (cw < -1) return const SunTimes(null, null, polar: 'day');
  final w = acos(cw) / r / 360;
  DateTime at(double jd) => DateTime.fromMillisecondsSinceEpoch(((jd - 2440587.5) * 864e5).round(), isUtc: true);
  return SunTimes(at(jt - w), at(jt + w));
}

/// Без доступа к геолокации место оцениваем по часовому поясу:
/// долгота — по смещению от UTC, широта — средняя для городов России.
({double lat, double lon}) placeFromOffset(Duration offset) => (lat: 56.0, lon: offset.inMinutes / 4.0);

bool isDarkNow([DateTime? now]) {
  final t = now ?? DateTime.now();
  final p = placeFromOffset(t.timeZoneOffset);
  return sunTimes(t, p.lat, p.lon).isDark(t.toUtc());
}
