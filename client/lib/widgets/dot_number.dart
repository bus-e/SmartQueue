import 'package:flutter/material.dart';

/// Номер из точек, как на табло: шрифт 5×7, горящие точки крупные, погасшие — бледные.
class DotNumber extends StatelessWidget {
  const DotNumber(this.text, {super.key, this.cell = 12, this.color, this.off});

  final String text;
  final double cell;
  final Color? color;
  final Color? off;

  static const _glyphs = {
    '0': '01110100011001110101110011000101110',
    '1': '00100011000010000100001000010001110',
    '2': '01110100010000100010001000100011111',
    '3': '11110000010000101110000010000111110',
    '4': '00010001100101010010111110001000010',
    '5': '11111100001111000001000011000101110',
    '6': '00110010001000011110100011000101110',
    '7': '11111000010001000100010000100001000',
    '8': '01110100011000101110100011000101110',
    '9': '01110100011000101111000010001001100',
  };

  @override
  Widget build(BuildContext context) {
    final cols = text.length * 6 - 1 + 2;
    final ink = color ?? Theme.of(context).colorScheme.onSurface;
    return Semantics(
      label: text,
      child: CustomPaint(
        size: Size(cols * cell, 9 * cell),
        painter: _DotsPainter(text, cell, ink, off ?? ink.withValues(alpha: 0.1)),
      ),
    );
  }
}

class _DotsPainter extends CustomPainter {
  _DotsPainter(this.text, this.cell, this.ink, this.off);

  final String text;
  final double cell;
  final Color ink, off;

  @override
  void paint(Canvas canvas, Size size) {
    final lit = <int>{};
    final cols = text.length * 6 - 1 + 2;
    for (var k = 0; k < text.length; k++) {
      final g = DotNumber._glyphs[text[k]] ?? '';
      for (var i = 0; i < g.length; i++) {
        if (g[i] == '1') lit.add((1 + i ~/ 5) * cols + 1 + k * 6 + i % 5);
      }
    }
    final on = Paint()..color = ink;
    final dim = Paint()..color = off;
    for (var y = 0; y < 9; y++) {
      for (var x = 0; x < cols; x++) {
        final isOn = lit.contains(y * cols + x);
        canvas.drawCircle(Offset(x * cell + cell / 2, y * cell + cell / 2), cell * (isOn ? 0.42 : 0.17), isOn ? on : dim);
      }
    }
  }

  @override
  bool shouldRepaint(_DotsPainter old) => old.text != text || old.ink != ink || old.off != off;
}
