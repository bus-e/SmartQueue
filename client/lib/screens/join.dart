import 'package:flutter/material.dart';

import '../api.dart';
import '../queue_code.dart';
import '../session.dart';
import '../theme.dart';

/// Вход в очередь по коду или ссылке из QR: название очереди, имя, «Встать».
class JoinScreen extends StatefulWidget {
  const JoinScreen({super.key, required this.api, required this.code});

  final ApiClient api;
  final String code;

  @override
  State<JoinScreen> createState() => _JoinScreenState();
}

class _JoinScreenState extends State<JoinScreen> {
  final _name = TextEditingController();
  late final Future<Map<String, dynamic>> _queue = widget.api.queue(widget.code);
  String? _error;
  bool _busy = false;

  Future<void> _join() async {
    if (_name.text.trim().isEmpty && widget.api.guestToken == null) {
      setState(() => _error = 'Как тебя показать в очереди?');
      return;
    }
    setState(() => _busy = true);
    try {
      widget.api.guestToken ??= await Session.load();
      await widget.api.join(widget.code, _name.text.trim());
      await Session.save(widget.api.guestToken!);
      if (mounted) Navigator.pushReplacementNamed(context, '/position', arguments: widget.code);
    } on ApiError catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Нет связи с сервером');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    return Scaffold(
      appBar: AppBar(title: Text('Очередь ${QueueCode.pretty(widget.code)}')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: ListView(
            padding: const EdgeInsets.all(16),
            shrinkWrap: true,
            children: [
              Container(
                padding: const EdgeInsets.all(22),
                decoration: BoxDecoration(color: p.wait, borderRadius: BorderRadius.circular(28)),
                child: FutureBuilder<Map<String, dynamic>>(
                  future: _queue,
                  builder: (context, snap) {
                    final q = snap.data;
                    final title = q?['title'] as String? ?? (snap.hasError ? 'Очередь не найдена' : '…');
                    final waiting = q?['waiting'] as int?;
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(title, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: p.ink)),
                        const SizedBox(height: 6),
                        Text(
                          waiting == null ? 'Код ${QueueCode.pretty(widget.code)}' : 'Сейчас в очереди: $waiting',
                          style: TextStyle(color: p.soft),
                        ),
                      ],
                    );
                  },
                ),
              ),
              const SizedBox(height: 14),
              TextField(
                key: const Key('name'),
                controller: _name,
                maxLength: 50,
                decoration: InputDecoration(labelText: 'Имя в очереди', errorText: _error),
                onSubmitted: (_) => _join(),
              ),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: _busy ? null : _join,
                child: Text(_busy ? 'Встаём…' : 'Встать'),
              ),
              const SizedBox(height: 10),
              Text(
                'Без регистрации. Место сохранится в этом браузере.',
                textAlign: TextAlign.center,
                style: TextStyle(color: p.soft, fontSize: 13),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
