import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartqueue/main.dart';

void main() {
  testWidgets('неверный код показывает подсказку и не открывает вход', (tester) async {
    await tester.pumpWidget(const SmartQueueApp());
    await tester.enterText(find.byKey(const Key('code')), 'K0M2QX');
    await tester.tap(find.text('Встать в очередь'));
    await tester.pump();
    expect(find.text('Код — 6 символов, без 0, O, 1 и I'), findsOneWidget);
  });

  testWidgets('верный код открывает экран входа', (tester) async {
    await tester.pumpWidget(const SmartQueueApp());
    await tester.enterText(find.byKey(const Key('code')), 'k7m 2qx');
    await tester.tap(find.text('Встать в очередь'));
    await tester.pumpAndSettle();
    expect(find.textContaining('K7M 2QX'), findsWidgets);
  });
}
