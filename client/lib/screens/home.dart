import 'package:flutter/material.dart';

import '../queue_code.dart';

/// Главная: ввести код, создать очередь.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _code = TextEditingController();
  String? _error;

  void _open() {
    if (!QueueCode.isValid(_code.text)) {
      setState(() => _error = 'Код — 6 символов, без 0, O, 1 и I');
      return;
    }
    Navigator.pushNamed(context, '/join', arguments: QueueCode.normalize(_code.text));
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('SmartQueue')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  key: const Key('code'),
                  controller: _code,
                  textCapitalization: TextCapitalization.characters,
                  decoration: InputDecoration(labelText: 'Код очереди', errorText: _error),
                  onSubmitted: (_) => _open(),
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: _open,
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                  child: const Text('Встать в очередь'),
                ),
                const SizedBox(height: 12),
                OutlinedButton(
                  onPressed: () => Navigator.pushNamed(context, '/create'),
                  style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                  child: const Text('Создать очередь'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
