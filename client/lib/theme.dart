import 'package:flutter/material.dart';

/// Цвета из макета интерфейса. Цвет экрана — состояние:
/// лавандовый — ждёшь, изумрудный — ты следующий, индиго — ты управляешь.
class Palette {
  const Palette({
    required this.page,
    required this.surface,
    required this.ink,
    required this.soft,
    required this.wait,
    required this.next,
    required this.nextBg,
    required this.lead,
    required this.leadBg,
    required this.off,
  });

  final Color page, surface, ink, soft, wait, next, nextBg, lead, leadBg, off;

  static const light = Palette(
    page: Color(0xFFEEF1F6),
    surface: Colors.white,
    ink: Color(0xFF1C2238),
    soft: Color(0xFF6B7189),
    wait: Color(0xFFEBE8FB),
    next: Color(0xFF119A80),
    nextBg: Color(0xFFD9F1EA),
    lead: Color(0xFF3F4CC9),
    leadBg: Color(0xFFE1E5FA),
    off: Color(0x1A1C2238),
  );

  static const dark = Palette(
    page: Color(0xFF0E1220),
    surface: Color(0xFF171C2E),
    ink: Color(0xFFE6E9F4),
    soft: Color(0xFF8A91AA),
    wait: Color(0xFF1D1A35),
    next: Color(0xFF33D1AD),
    nextBg: Color(0xFF0E2A26),
    lead: Color(0xFF8B95FF),
    leadBg: Color(0xFF1A1F45),
    off: Color(0x17E6E9F4),
  );

  static Palette of(BuildContext context) => Theme.of(context).brightness == Brightness.dark ? dark : light;
}

ThemeData buildTheme(Brightness brightness) {
  final p = brightness == Brightness.dark ? Palette.dark : Palette.light;
  final scheme = ColorScheme.fromSeed(seedColor: p.lead, brightness: brightness).copyWith(
    primary: p.lead,
    surface: p.page,
    onSurface: p.ink,
  );
  final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(18));
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: p.page,
    appBarTheme: AppBarTheme(backgroundColor: p.page, foregroundColor: p.ink, elevation: 0),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(56),
        shape: shape,
        backgroundColor: p.ink,
        foregroundColor: p.page,
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(56),
        shape: shape,
        foregroundColor: p.ink,
        backgroundColor: p.surface,
        side: BorderSide(color: p.off),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: p.surface,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
    ),
  );
}
