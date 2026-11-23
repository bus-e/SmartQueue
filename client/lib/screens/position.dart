import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../queue_code.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/dot_number.dart';

/// «Моё место»: номер из точек, кто в очереди, кнопки. Обновляется каждые 2 секунды —
/// так позиция меняется не позже чем через 2 с после действия на любой платформе (тест Т4).
class PositionScreen extends StatefulWidget {
  const PositionScreen({super.key, required this.api, required this.code, this.refresh = const Duration(seconds: 2)});

  final ApiClient api;
  final String code;
  final Duration refresh;

  @override
  State<PositionScreen> createState() => _PositionScreenState();
}

class _PositionScreenState extends State<PositionScreen> {
  Map<String, dynamic>? _queue;
  Map<String, dynamic>? _me;
  List<Map<String, dynamic>> _entries = const [];
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(widget.refresh, (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      widget.api.guestToken ??= await Session.load();
      final q = await widget.api.queue(widget.code);
      final me = await widget.api.me(widget.code);
      final list = me == null ? <Map<String, dynamic>>[] : await widget.api.entries(widget.code);
      if (!mounted) return;
      setState(() {
        _queue = q;
        _me = me;
        _entries = list;
        _error = null;
      });
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Нет связи с сервером — пробуем ещё раз');
    }
  }

  Future<void> _act(int id, String status) async {
    try {
      await widget.api.setStatus(id, status);
      if (status == 'left' && mounted) {
        Navigator.pushNamedAndRemoveUntil(context, '/', (_) => false);
        return;
      }
      await _load();
    } on ApiError catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = Palette.of(context);
    final me = _me;
    final pos = me?['position'] as int?;
    final canNext = me?['can_next'] == true;
    final takeAt = me?['take_over_at'] as String?;
    final canTake = takeAt != null && DateTime.parse(takeAt).isBefore(DateTime.now().toUtc());

    // цвет экрана = состояние
    final (bg, accent, title) = switch ((pos, canNext, _queue?['status'])) {
      (_, _, 'closed') => (p.page, p.soft, 'Очередь завершена'),
      (1, true, _) => (p.leadBg, p.lead, 'Твоя очередь'),
      (1, false, _) => (p.nextBg, p.next, 'Ты первый'),
      (2, _, _) => (p.nextBg, p.next, 'Ты следующий'),
      (int n, _, _) => (p.wait, p.ink, 'Ты $n-й'),
      _ => (p.page, p.soft, me == null && _queue != null ? 'Ты не в очереди' : '…'),
    };

    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        backgroundColor: bg,
        title: Text(_queue?['title'] as String? ?? 'Очередь ${QueueCode.pretty(widget.code)}'),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (pos != null) Center(child: DotNumber(pos.toString().padLeft(2, '0'), cell: 13, color: accent)),
              const SizedBox(height: 12),
              Text(title,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, color: accent)),
              if (me != null && pos != null && pos > 1)
                Text('Перед тобой — ${me['ahead']}. Сейчас у двери: ${_queue?['now_serving'] ?? '—'}',
                    textAlign: TextAlign.center, style: TextStyle(color: p.soft)),
              if (canNext)
                Text('Зайди. Когда выйдешь — нажми «Следующий», и очередь сдвинется у всех.',
                    textAlign: TextAlign.center, style: TextStyle(color: p.soft)),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.redAccent)),
                ),
              const SizedBox(height: 18),
              for (final e in _entries) _Person(e, p),
              const SizedBox(height: 18),
              if (canNext)
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: p.lead, foregroundColor: Colors.white),
                  onPressed: () => _act(me!['id'] as int, 'served'),
                  child: const Text('Следующий'),
                ),
              if (canTake) ...[
                Text('Первый не нажимает «Следующий» больше 10 минут.',
                    textAlign: TextAlign.center, style: TextStyle(color: p.soft)),
                const SizedBox(height: 8),
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: p.next, foregroundColor: Colors.white),
                  onPressed: () => _act(me!['first_id'] as int, 'removed'),
                  child: const Text('Забрать управление'),
                ),
              ],
              const SizedBox(height: 8),
              if (me != null)
                TextButton(onPressed: () => _act(me['id'] as int, 'left'), child: const Text('Выйти из очереди')),
            ],
          ),
        ),
      ),
    );
  }
}

class _Person extends StatelessWidget {
  const _Person(this.e, this.p);

  final Map<String, dynamic> e;
  final Palette p;

  @override
  Widget build(BuildContext context) {
    final mine = e['is_me'] == true;
    final name = mine ? 'Ты' : (e['name'] as String? ?? 'Участник');
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.fromLTRB(8, 8, 12, 8),
      decoration: BoxDecoration(color: mine ? p.ink : p.surface, borderRadius: BorderRadius.circular(16)),
      child: Row(children: [
        CircleAvatar(
          radius: 17,
          backgroundColor: mine ? p.wait : p.leadBg,
          child: Text('${e['position'] ?? '·'}', style: TextStyle(color: p.ink, fontWeight: FontWeight.w800)),
        ),
        const SizedBox(width: 11),
        Text(name, style: TextStyle(fontWeight: FontWeight.w700, color: mine ? p.page : p.ink)),
        const Spacer(),
        if (e['status'] == 'called') Text('вызван', style: TextStyle(color: p.next, fontWeight: FontWeight.w700)),
      ]),
    );
  }
}
