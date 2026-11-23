import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartqueue/widgets/dot_number.dart';

void main() {
  testWidgets('номер из точек рисуется и читается экранным диктором', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: Center(child: DotNumber('03', cell: 10)))));
    expect(find.bySemanticsLabel('03'), findsOneWidget);
    final size = tester.getSize(find.descendant(of: find.byType(DotNumber), matching: find.byType(CustomPaint)));
    expect(size, const Size(130, 90)); // (2 цифры × 6 − 1 + 2 поля) × 10 на 9 × 10
  });
}
