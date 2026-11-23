import 'package:flutter/material.dart';

/// Экран из карты экранов, который будет сделан в следующих спринтах.
class StubScreen extends StatelessWidget {
  const StubScreen({super.key, required this.title, required this.sprint});

  final String title;
  final String sprint;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(child: Text('Экран «$title» — $sprint')),
    );
  }
}
