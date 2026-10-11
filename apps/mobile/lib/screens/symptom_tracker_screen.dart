import 'package:flutter/material.dart';

import '../models/symptom.dart';
import '../services/api_client.dart';
import '../services/ovacare_api.dart';
import '../widgets/error_banner.dart';

class SymptomTrackerScreen extends StatefulWidget {
  const SymptomTrackerScreen({super.key});

  @override
  State<SymptomTrackerScreen> createState() => _SymptomTrackerScreenState();
}

class _SymptomTrackerScreenState extends State<SymptomTrackerScreen> {
  List<Symptom>? _symptoms;
  String? _loadError;

  SymptomType _type = SymptomType.acne;
  int _severity = 2;
  DateTime _loggedDate = DateTime.now();
  final _customLabelController = TextEditingController();
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
    _customLabelController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loadError = null);
    try {
      final symptoms = await OvaCareApi.instance.listSymptoms();
      if (mounted) setState(() => _symptoms = symptoms);
    } on ApiException catch (e) {
      if (mounted) setState(() => _loadError = e.message);
    } catch (_) {
      if (mounted) setState(() => _loadError = 'Something went wrong. Please try again.');
    }
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _loggedDate,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _loggedDate = picked);
  }

  Future<void> _submit() async {
    if (_type == SymptomType.other && _customLabelController.text.trim().isEmpty) {
      setState(() => _formError = 'Please describe the symptom when "Other" is selected.');
      return;
    }
    setState(() {
      _submitting = true;
      _formError = null;
    });
    try {
      final symptom = Symptom(
        symptomType: _type,
        customLabel: _type == SymptomType.other ? _customLabelController.text.trim() : null,
        severity: _severity,
        loggedDate: _loggedDate,
        notes: _notesController.text.isEmpty ? null : _notesController.text,
      );
      await OvaCareApi.instance.createSymptom(symptom);
      _customLabelController.clear();
      _notesController.clear();
      setState(() => _severity = 2);
      await _load();
    } on ApiException catch (e) {
      setState(() => _formError = e.message);
    } catch (_) {
      setState(() => _formError = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _delete(Symptom symptom) async {
    try {
      await OvaCareApi.instance.deleteSymptom(symptom.id!);
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
    if (_symptoms == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          _buildForm(),
          const SizedBox(height: 16),
          Text('History', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_symptoms!.isEmpty)
            const Padding(padding: EdgeInsets.all(12), child: Text('No symptoms logged yet.'))
          else
            ..._symptoms!.map((s) => Card(
                  child: ListTile(
                    title: Text(s.symptomType == SymptomType.other && s.customLabel != null
                        ? s.customLabel!
                        : s.symptomType.label),
                    subtitle: Text('${_formatDate(s.loggedDate)} · severity ${s.severity}/5'),
                    trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => _delete(s)),
                  ),
                )),
        ],
      ),
    );
  }

  Widget _buildForm() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Log a symptom', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            if (_formError != null) ...[ErrorBanner(message: _formError!), const SizedBox(height: 10)],
            DropdownButtonFormField<SymptomType>(
              value: _type,
              decoration: const InputDecoration(labelText: 'Symptom'),
              items: SymptomType.values.map((t) => DropdownMenuItem(value: t, child: Text(t.label))).toList(),
              onChanged: (value) => setState(() => _type = value ?? SymptomType.acne),
            ),
            if (_type == SymptomType.other) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _customLabelController,
                decoration: const InputDecoration(labelText: 'Describe the symptom'),
              ),
            ],
            const SizedBox(height: 12),
            Text('Severity: $_severity / 5', style: Theme.of(context).textTheme.bodyMedium),
            Slider(
              value: _severity.toDouble(),
              min: 1,
              max: 5,
              divisions: 4,
              label: '$_severity',
              onChanged: (value) => setState(() => _severity = value.round()),
            ),
            OutlinedButton(onPressed: _pickDate, child: Text('Date: ${_formatDate(_loggedDate)}')),
            const SizedBox(height: 12),
            TextField(
              controller: _notesController,
              decoration: const InputDecoration(labelText: 'Notes (optional)'),
              maxLines: 2,
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: _submitting ? null : _submit,
              child: _submitting
                  ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Save symptom'),
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
