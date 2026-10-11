import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/consent.dart';
import '../services/api_client.dart';
import '../services/ovacare_api.dart';
import '../state/app_state.dart';
import '../widgets/error_banner.dart';

/// Requirement #57: informed consent BEFORE any health-data collection,
/// plain language, no pre-checked boxes. Copy matches
/// apps/web/src/js/app.js's viewConsent() exactly so the product reads
/// the same across platforms — this is NOT independently drafted text.
///
/// Only the two REQUIRED consent types (core_service,
/// health_data_processing) are collected here, same as the web app's
/// current implementation — the optional ones (notifications, analytics,
/// research/model-improvement) are opt-in later, from Settings, and using
/// the app is never treated as automatic consent for those (requirement
/// #57: "using the app is never automatic consent for the optional
/// ones").
class ConsentScreen extends StatefulWidget {
  const ConsentScreen({super.key});

  @override
  State<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends State<ConsentScreen> {
  bool _agreed = false;
  bool _submitting = false;
  String? _error;

  Future<void> _continue() async {
    if (!_agreed) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      for (final type in [ConsentType.coreService, ConsentType.healthDataProcessing]) {
        await OvaCareApi.instance.submitConsent(type, accepted: true);
      }
      if (!mounted) return;
      context.read<AppState>().consentCompleted();
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text('Before You Continue', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 16),
                    const Text(
                      'OvaCare collects health information to provide period tracking, symptom '
                      'tracking, and AI-assisted screening features.',
                    ),
                    const SizedBox(height: 10),
                    const Text('Some questions are optional.'),
                    const SizedBox(height: 10),
                    const Text(
                      'Your screening result is not a medical diagnosis and should not replace '
                      'professional medical advice.',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 10),
                    const Text('You can review our Privacy Policy and manage your data settings at any time.'),
                    const SizedBox(height: 18),
                    if (_error != null) ...[
                      ErrorBanner(message: _error!),
                      const SizedBox(height: 12),
                    ],
                    CheckboxListTile(
                      value: _agreed,
                      onChanged: _submitting ? null : (value) => setState(() => _agreed = value ?? false),
                      controlAffinity: ListTileControlAffinity.leading,
                      contentPadding: EdgeInsets.zero,
                      title: const Text('I understand how my information will be used.'),
                    ),
                    const SizedBox(height: 8),
                    FilledButton(
                      onPressed: (_agreed && !_submitting) ? _continue : null,
                      child: _submitting
                          ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Text('Continue'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
