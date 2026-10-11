import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../models/assessment.dart';
import '../../models/consent.dart';
import '../../safety/wording.dart';
import '../../services/api_client.dart';
import '../../services/ovacare_api.dart';
import '../../widgets/error_banner.dart';
import '../../widgets/medical_disclaimer_banner.dart';
import 'assessment_fields.dart';

enum _Step { questionnaire, review, aiConsent, savedWithoutResult, result }

/// The full requirement #75 flow — questionnaire -> review -> result —
/// as one screen with internal steps (rather than separate Navigator
/// routes) so the in-progress form state survives a step-back without
/// extra plumbing. Mirrors apps/web/src/js/app.js's
/// viewAssessment -> viewAssessmentReview -> viewAssessmentResult chain.
class AssessmentFlowScreen extends StatefulWidget {
  const AssessmentFlowScreen({super.key});

  @override
  State<AssessmentFlowScreen> createState() => _AssessmentFlowScreenState();
}

class _AssessmentFlowScreenState extends State<AssessmentFlowScreen> {
  _Step _step = _Step.questionnaire;

  // Field name -> entered value (num or String), or absent if skipped.
  final Map<String, Object?> _values = {};
  // Field names the person explicitly marked "I don't have this result."
  final Set<String> _skipped = {};

  final _controllers = <String, TextEditingController>{};

  // Red-flag safety fields (requirement #67/#68) — collected regardless
  // of ML field completeness, evaluated independently server-side.
  bool _soakingThroughProtectionHourly = false;
  bool _bleedingWithDizzinessOrFainting = false;
  int? _pelvicPainSeverity;
  bool _faintingOrSevereDizziness = false;
  bool _chestPainOrBreathingDifficulty = false;

  bool _submitting = false;
  String? _formError;
  AssessmentSubmitResponse? _result;
  String? _pendingAssessmentId;

  @override
  void initState() {
    super.initState();
    for (final field in assessmentFields) {
      if (field.type == AssessmentFieldType.numeric) {
        _controllers[field.name] = TextEditingController();
      }
    }
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  bool _validateRequired() {
    for (final field in assessmentFields.where((f) => f.required)) {
      final hasValue = field.type == AssessmentFieldType.numeric
          ? (_controllers[field.name]?.text.trim().isNotEmpty ?? false)
          : _values.containsKey(field.name);
      if (!hasValue) return false;
    }
    return true;
  }

  void _goToReview() {
    // Collect current numeric field text into _values.
    for (final field in assessmentFields.where((f) => f.type == AssessmentFieldType.numeric)) {
      final text = _controllers[field.name]?.text.trim() ?? '';
      if (text.isEmpty) {
        _values.remove(field.name);
      } else {
        _values[field.name] = num.tryParse(text);
      }
    }
    if (!_validateRequired()) {
      setState(() => _formError = 'Please answer every required question before continuing.');
      return;
    }
    setState(() {
      _formError = null;
      _step = _Step.review;
    });
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _formError = null;
    });
    try {
      final responses = <String, Object?>{};
      for (final field in assessmentFields) {
        responses[field.name] = _skipped.contains(field.name) ? null : _values[field.name];
      }
      final request = AssessmentSubmitRequest(
        responses: responses,
        unansweredFields: _skipped.toList(),
        soakingThroughProtectionHourly: _soakingThroughProtectionHourly,
        bleedingWithDizzinessOrFainting: _bleedingWithDizzinessOrFainting,
        pelvicPainSeverity: _pelvicPainSeverity,
        faintingOrSevereDizziness: _faintingOrSevereDizziness,
        chestPainOrBreathingDifficulty: _chestPainOrBreathingDifficulty,
      );
      final assessmentId = await OvaCareApi.instance.submitAssessment(request);

      // Requirement: consent BEFORE AI screening. The assessment answers
      // are already saved above (POST /assessments) — this only gates the
      // separate POST /predictions call, matching the backend's own
      // AI_SCREENING_ACKNOWLEDGEMENT check in app/api/predictions.py.
      final consents = await OvaCareApi.instance.getConsents();
      final hasAiScreeningConsent = consents.any(
        (c) => c.consentType == ConsentType.aiScreeningAcknowledgement && c.isActive,
      );
      if (!hasAiScreeningConsent) {
        setState(() {
          _pendingAssessmentId = assessmentId;
          _step = _Step.aiConsent;
        });
        return;
      }

      final result = await OvaCareApi.instance.requestPrediction(assessmentId);
      setState(() {
        _result = result;
        _step = _Step.result;
      });
    } on ApiException catch (e) {
      setState(() => _formError = e.message);
    } catch (_) {
      setState(() => _formError = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _confirmAiScreeningConsentAndShowResult() async {
    final assessmentId = _pendingAssessmentId;
    if (assessmentId == null) return;
    setState(() {
      _submitting = true;
      _formError = null;
    });
    try {
      await OvaCareApi.instance.submitConsent(ConsentType.aiScreeningAcknowledgement);
      final result = await OvaCareApi.instance.requestPrediction(assessmentId);
      setState(() {
        _result = result;
        _step = _Step.result;
      });
    } on ApiException catch (e) {
      setState(() => _formError = e.message);
    } catch (_) {
      setState(() => _formError = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _startOver() {
    setState(() {
      _values.clear();
      _skipped.clear();
      for (final c in _controllers.values) {
        c.clear();
      }
      _soakingThroughProtectionHourly = false;
      _bleedingWithDizzinessOrFainting = false;
      _pelvicPainSeverity = null;
      _faintingOrSevereDizziness = false;
      _chestPainOrBreathingDifficulty = false;
      _result = null;
      _pendingAssessmentId = null;
      _formError = null;
      _step = _Step.questionnaire;
    });
  }

  @override
  Widget build(BuildContext context) {
    switch (_step) {
      case _Step.questionnaire:
        return _buildQuestionnaire();
      case _Step.review:
        return _buildReview();
      case _Step.aiConsent:
        return _buildAiConsent();
      case _Step.savedWithoutResult:
        return _buildSavedWithoutResult();
      case _Step.result:
        return _buildResult();
    }
  }

  // --- Step 1: Questionnaire ---

  Widget _buildQuestionnaire() {
    final bySection = <String, List<AssessmentField>>{};
    for (final field in assessmentFields) {
      bySection.putIfAbsent(field.section, () => []).add(field);
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('AI-Assisted PCOS Screening', style: Theme.of(context).textTheme.titleLarge),
        const InfoBanner(
          message: 'This is an educational, AI-assisted screening — not a diagnosis. Some questions are optional.',
        ),
        const SizedBox(height: 12),
        if (_formError != null) ...[ErrorBanner(message: _formError!), const SizedBox(height: 12)],
        for (final section in bySection.entries) _buildSection(section.key, section.value),
        _buildSafetySection(),
        const SizedBox(height: 8),
        FilledButton(onPressed: _goToReview, child: const Text('Review my answers')),
        const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildSection(String title, List<AssessmentField> fields) {
    final isOptional = fields.first.required == false;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            if (isOptional)
              const Padding(
                padding: EdgeInsets.only(top: 4, bottom: 8),
                child: Text('Optional — leave blank or mark "I don\'t have this result" if unknown.',
                    style: TextStyle(fontSize: 12)),
              )
            else
              const SizedBox(height: 8),
            for (final field in fields) _buildFieldInput(field),
          ],
        ),
      ),
    );
  }

  Widget _buildFieldInput(AssessmentField field) {
    final skipped = _skipped.contains(field.name);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: _buildFieldControl(field, enabled: !skipped)),
          if (!field.required) ...[
            const SizedBox(width: 8),
            Column(
              children: [
                const SizedBox(height: 4),
                Checkbox(
                  value: skipped,
                  onChanged: (value) {
                    setState(() {
                      if (value == true) {
                        _skipped.add(field.name);
                        _values.remove(field.name);
                        _controllers[field.name]?.clear();
                      } else {
                        _skipped.remove(field.name);
                      }
                    });
                  },
                ),
                const Text("Don't\nhave this", style: TextStyle(fontSize: 10), textAlign: TextAlign.center),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFieldControl(AssessmentField field, {required bool enabled}) {
    switch (field.type) {
      case AssessmentFieldType.numeric:
        return TextField(
          controller: _controllers[field.name],
          enabled: enabled,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: InputDecoration(labelText: field.label),
        );
      case AssessmentFieldType.yesNo:
        return DropdownButtonFormField<String>(
          value: _values[field.name] as String?,
          decoration: InputDecoration(labelText: field.label),
          items: const [
            DropdownMenuItem(value: 'no', child: Text('No')),
            DropdownMenuItem(value: 'yes', child: Text('Yes')),
          ],
          onChanged: enabled ? (value) => setState(() => _values[field.name] = value) : null,
        );
      case AssessmentFieldType.cycleRegularity:
        return DropdownButtonFormField<String>(
          value: _values[field.name] as String?,
          decoration: InputDecoration(labelText: field.label),
          items: const [
            DropdownMenuItem(value: 'regular', child: Text('Regular')),
            DropdownMenuItem(value: 'irregular', child: Text('Irregular')),
          ],
          onChanged: enabled ? (value) => setState(() => _values[field.name] = value) : null,
        );
    }
  }

  Widget _buildSafetySection() {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('If any of these apply right now', style: Theme.of(context).textTheme.titleMedium),
            const Padding(
              padding: EdgeInsets.only(top: 4, bottom: 4),
              child: Text(
                "We'll show you information about seeking urgent care. This check runs independently of the "
                'screening above and never delays or requires completing it.',
                style: TextStyle(fontSize: 12),
              ),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              title: const Text('Soaking through pad/tampon protection hourly'),
              value: _soakingThroughProtectionHourly,
              onChanged: (v) => setState(() => _soakingThroughProtectionHourly = v ?? false),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              title: const Text('Heavy bleeding with dizziness or fainting'),
              value: _bleedingWithDizzinessOrFainting,
              onChanged: (v) => setState(() => _bleedingWithDizzinessOrFainting = v ?? false),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              title: const Text('Fainting or severe dizziness'),
              value: _faintingOrSevereDizziness,
              onChanged: (v) => setState(() => _faintingOrSevereDizziness = v ?? false),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              title: const Text('Chest pain or difficulty breathing'),
              value: _chestPainOrBreathingDifficulty,
              onChanged: (v) => setState(() => _chestPainOrBreathingDifficulty = v ?? false),
            ),
            Text('Pelvic pain severity (optional, 1-5)', style: Theme.of(context).textTheme.bodyMedium),
            Slider(
              value: (_pelvicPainSeverity ?? 0).toDouble(),
              min: 0,
              max: 5,
              divisions: 5,
              label: _pelvicPainSeverity == null ? 'None' : '$_pelvicPainSeverity',
              onChanged: (value) => setState(() => _pelvicPainSeverity = value.round() == 0 ? null : value.round()),
            ),
          ],
        ),
      ),
    );
  }

  // --- Step 2: Review ---

  Widget _buildReview() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Review Your Information', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final field in assessmentFields)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        Expanded(child: Text(field.label)),
                        Text(
                          _skipped.contains(field.name) || _values[field.name] == null
                              ? 'Not provided'
                              : '${_values[field.name]}',
                          style: TextStyle(
                            color: (_skipped.contains(field.name) || _values[field.name] == null)
                                ? Theme.of(context).colorScheme.outline
                                : null,
                          ),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 8),
                const Text(
                  'This result will be based only on the information you provided above.',
                  style: TextStyle(fontSize: 12),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (_formError != null) ...[ErrorBanner(message: _formError!), const SizedBox(height: 12)],
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _submitting ? null : () => setState(() => _step = _Step.questionnaire),
                child: const Text('Edit information'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton(
                onPressed: _submitting ? null : _submit,
                child: _submitting
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Submit assessment'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // --- Step 2b: AI-screening consent gate ---

  Widget _buildAiConsent() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Before We Show Your Result', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(ConsentType.aiScreeningAcknowledgement.description),
                const SizedBox(height: 10),
                const Text('You can withdraw this at any time from Settings.', style: TextStyle(fontSize: 12)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (_formError != null) ...[ErrorBanner(message: _formError!), const SizedBox(height: 12)],
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _submitting ? null : () => setState(() => _step = _Step.savedWithoutResult),
                child: const Text('Not now'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton(
                onPressed: _submitting ? null : _confirmAiScreeningConsentAndShowResult,
                child: _submitting
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('I understand, show my result'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildSavedWithoutResult() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Assessment Saved', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        const Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'Your answers were saved. When you\'re ready for your AI screening result, accept AI-screening '
              'consent from Settings and start a new assessment, or return to this one.',
            ),
          ),
        ),
        const SizedBox(height: 16),
        OutlinedButton(onPressed: _startOver, child: const Text('Start a new assessment')),
      ],
    );
  }

  // --- Step 3: Result ---

  /// Defense-in-depth (requirement #63/#64/#90) — see
  /// lib/safety/wording.dart. The backend is the primary control; this
  /// only guards against unsafe text somehow still reaching the client.
  /// Falls back to the neutral insufficient-data wording rather than
  /// crashing the screen if the check ever fires for real.
  String _guarded(String text) {
    try {
      assertSafeWording(text);
      return text;
    } on UnsafeWordingError catch (e) {
      if (kDebugMode) {
        // Surface loudly in development/tests; never in a release build,
        // where crashing on unsafe wording would be worse than a
        // deliberately generic fallback.
        debugPrint('Blocked unsafe wording from rendering: $e');
      }
      return "We don't have enough validated information to provide a reliable screening result from these "
          'inputs. Please review your information or consider discussing your concerns with a healthcare '
          'professional.';
    }
  }

  Widget _buildResult() {
    final response = _result!;
    final safety = response.safety;
    final result = response.result;
    final factors = (result.explanation['factors'] as List?) ?? const [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Your Screening Result', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        if (safety.urgent && safety.message != null) ...[
          ErrorBanner(message: safety.message!),
          const SizedBox(height: 12),
        ],
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Screening indication', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                // Pre-approved wording rendered verbatim — this app never
                // constructs or alters this text (requirement #90 tests 1/2).
                // _guarded() is a defense-in-depth re-check, not a rewrite.
                Text(_guarded(result.message), style: Theme.of(context).textTheme.bodyLarge),
                if (result.probability != null) ...[
                  const SizedBox(height: 6),
                  Text('Model probability: ${(result.probability! * 100).toStringAsFixed(0)}%',
                      style: Theme.of(context).textTheme.bodySmall),
                ],
                if (factors.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Text('Factors that contributed', style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 6),
                  for (final f in factors)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: RichText(
                        text: TextSpan(
                          style: DefaultTextStyle.of(context).style,
                          children: [
                            TextSpan(text: '${(f as Map)['label']}: ', style: const TextStyle(fontWeight: FontWeight.bold)),
                            TextSpan(text: '${f['why_it_matters']}'),
                          ],
                        ),
                      ),
                    ),
                  if (result.explanationFraming != null)
                    Text(result.explanationFraming!, style: Theme.of(context).textTheme.bodySmall),
                ],
                const SizedBox(height: 10),
                Text(
                  'Assessed ${result.assessedAt.toLocal()} · model ${result.modelVersion}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                MedicalDisclaimerBanner(overrideText: result.medicalDisclaimer),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        OutlinedButton(onPressed: _startOver, child: const Text('Start a new assessment')),
      ],
    );
  }
}
