import 'package:flutter/material.dart';

import '../models/cycle_record.dart';
import '../services/api_client.dart';
import '../services/local_reminder_service.dart';
import '../services/ovacare_api.dart';
import '../widgets/error_banner.dart';

class CycleTrackerScreen extends StatefulWidget {
  const CycleTrackerScreen({super.key});

  @override
  State<CycleTrackerScreen> createState() => _CycleTrackerScreenState();
}

class _CycleTrackerScreenState extends State<CycleTrackerScreen> {
  List<CycleRecord>? _cycles;
  CycleSummary? _summary;
  CycleEstimateResponse? _estimate;
  String? _loadError;

  DateTime _startDate = DateTime.now();
  DateTime? _endDate;
  FlowLevel _flowLevel = FlowLevel.medium;
  final _notesController = TextEditingController();
  bool _submitting = false;
  String? _formError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loadError = null);
    try {
      final results = await Future.wait([
        OvaCareApi.instance.listCycles(),
        OvaCareApi.instance.cycleSummary(),
        OvaCareApi.instance.cycleEstimate(),
      ]);
      if (!mounted) return;
      setState(() {
        _cycles = results[0] as List<CycleRecord>;
        _summary = results[1] as CycleSummary;
        _estimate = results[2] as CycleEstimateResponse;
      });
      // Logging/removing a period changes the cycle-history-based estimate
      // this reminder is computed from — resync it here so the reminder
      // never fires against a stale estimated date. Best-effort: never
      // surfaces an error on this screen.
      try {
        final preference = await OvaCareApi.instance.getNotificationPreferences();
        await LocalReminderService.instance.syncUpcomingPeriodReminder(estimate: _estimate!, preference: preference);
      } catch (_) {
        // Ignored — see comment above.
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _loadError = e.message);
    } catch (_) {
      if (mounted) setState(() => _loadError = 'Something went wrong. Please try again.');
    }
  }

  Future<void> _pickStartDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _startDate,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _startDate = picked);
  }

  Future<void> _pickEndDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _endDate ?? _startDate,
      firstDate: _startDate,
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _endDate = picked);
  }

  Future<void> _submitLog() async {
    setState(() {
      _submitting = true;
      _formError = null;
    });
    try {
      final record = CycleRecord(
        startDate: _startDate,
        endDate: _endDate,
        flowLevel: _flowLevel,
        notes: _notesController.text.isEmpty ? null : _notesController.text,
      );
      await OvaCareApi.instance.createCycle(record);
      _notesController.clear();
      setState(() {
        _endDate = null;
        _flowLevel = FlowLevel.medium;
      });
      await _load();
    } on ApiException catch (e) {
      setState(() => _formError = e.message);
    } catch (_) {
      setState(() => _formError = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _delete(CycleRecord record) async {
    try {
      await OvaCareApi.instance.deleteCycle(record.id!);
      await _load();
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loadError != null) {
      return Padding(padding: const EdgeInsets.all(16), child: ErrorBanner(message: _loadError!));
    }
    if (_cycles == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          _buildSummaryCards(),
          const SizedBox(height: 16),
          _buildLogForm(),
          const SizedBox(height: 16),
          Text('History', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_cycles!.isEmpty)
            const Padding(padding: EdgeInsets.all(12), child: Text('No periods logged yet.'))
          else
            ..._cycles!.map((c) => Card(
                  child: ListTile(
                    title: Text(_formatDate(c.startDate)),
                    subtitle: Text([
                      if (c.endDate != null) 'to ${_formatDate(c.endDate!)}',
                      if (c.flowLevel != null) c.flowLevel!.label,
                      if (c.cycleLengthDays != null) 'cycle: ${c.cycleLengthDays}d',
                      if (c.periodDurationDays != null) 'duration: ${c.periodDurationDays}d',
                    ].join(' · ')),
                    trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => _delete(c)),
                  ),
                )),
        ],
      ),
    );
  }

  Widget _buildSummaryCards() {
    final summary = _summary!;
    final estimate = _estimate!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Average cycle length', style: Theme.of(context).textTheme.bodySmall),
                      Text(
                        summary.sufficientData ? '${summary.averageCycleLengthDays?.toStringAsFixed(0)} days' : '—',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(estimate.label, style: Theme.of(context).textTheme.bodySmall),
                      Text(
                        estimate.sufficientData && estimate.estimatedStartDate != null
                            ? _formatDate(estimate.estimatedStartDate!)
                            : '—',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
        if (!estimate.sufficientData && estimate.message != null) ...[
          const SizedBox(height: 10),
          InfoBanner(message: estimate.message!),
        ],
        if (summary.isHighVariability) ...[
          const SizedBox(height: 10),
          const WarningBanner(
            message: 'Your recent cycle lengths have varied. Continue tracking your cycles, and consider '
                'discussing persistent changes with a qualified healthcare professional.',
          ),
        ],
      ],
    );
  }

  Widget _buildLogForm() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Log a period', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            if (_formError != null) ...[ErrorBanner(message: _formError!), const SizedBox(height: 10)],
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _pickStartDate,
                    child: Text('Start: ${_formatDate(_startDate)}'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    onPressed: _pickEndDate,
                    child: Text(_endDate == null ? 'End: (ongoing)' : 'End: ${_formatDate(_endDate!)}'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<FlowLevel>(
              value: _flowLevel,
              decoration: const InputDecoration(labelText: 'Flow'),
              items: FlowLevel.values.map((f) => DropdownMenuItem(value: f, child: Text(f.label))).toList(),
              onChanged: (value) => setState(() => _flowLevel = value ?? FlowLevel.medium),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _notesController,
              decoration: const InputDecoration(labelText: 'Notes (optional)'),
              maxLines: 2,
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: _submitting ? null : _submitLog,
              child: _submitting
                  ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }
}
