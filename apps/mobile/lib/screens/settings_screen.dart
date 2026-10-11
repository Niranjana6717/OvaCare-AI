import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/consent.dart';
import '../models/notification_preference.dart';
import '../models/user.dart';
import '../services/api_client.dart';
import '../services/local_reminder_service.dart';
import '../services/ovacare_api.dart';
import '../state/app_state.dart';
import '../widgets/error_banner.dart';

/// Profile + notification preferences + consent management + account
/// deletion in one screen — a deliberate merge of what
/// apps/web/src/js/app.js keeps as two views (viewProfile, viewSettings)
/// into one scrollable mobile screen, a common and reasonable mobile
/// pattern given how small each section is individually.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  Profile? _profile;
  NotificationPreference? _prefs;
  List<ConsentRecord>? _consents;
  String? _loadError;

  final _fullNameController = TextEditingController();
  final _heightController = TextEditingController();
  final _weightController = TextEditingController();
  bool _savingProfile = false;
  String? _profileError;

  bool _savingPrefs = false;
  String? _prefsError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loadError = null);
    try {
      final results = await Future.wait([
        OvaCareApi.instance.getMe(),
        OvaCareApi.instance.getNotificationPreferences(),
        OvaCareApi.instance.getConsents(),
      ]);
      if (!mounted) return;
      final profile = results[0] as Profile;
      setState(() {
        _profile = profile;
        _prefs = results[1] as NotificationPreference;
        _consents = results[2] as List<ConsentRecord>;
        _fullNameController.text = profile.fullName ?? '';
        _heightController.text = profile.heightCm?.toString() ?? '';
        _weightController.text = profile.weightKg?.toString() ?? '';
      });
      // Best-effort resync in case the cycle estimate changed elsewhere in
      // this session (e.g. a period logged on the Cycle Tracker screen)
      // since the reminder was last scheduled.
      try {
        final estimate = await OvaCareApi.instance.cycleEstimate();
        await LocalReminderService.instance.syncUpcomingPeriodReminder(
          estimate: estimate,
          preference: results[1] as NotificationPreference,
        );
      } catch (_) {
        // Ignored — see comment above.
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _loadError = e.message);
    } catch (_) {
      if (mounted) setState(() => _loadError = 'Something went wrong. Please try again.');
    }
  }

  Future<void> _saveProfile() async {
    setState(() {
      _savingProfile = true;
      _profileError = null;
    });
    try {
      final updated = _profile!.copyWith(
        fullName: _fullNameController.text.isEmpty ? null : _fullNameController.text,
        heightCm: double.tryParse(_heightController.text),
        weightKg: double.tryParse(_weightController.text),
      );
      final saved = await OvaCareApi.instance.updateMe(updated);
      if (!mounted) return;
      setState(() => _profile = saved);
      await context.read<AppState>().refreshCurrentProfile();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profile saved.')));
    } on ApiException catch (e) {
      setState(() => _profileError = e.message);
    } catch (_) {
      setState(() => _profileError = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _savingProfile = false);
    }
  }

  Future<void> _savePrefs(NotificationPreference next) async {
    setState(() {
      _savingPrefs = true;
      _prefsError = null;
    });
    // Ask for OS notification permission only when reminders are being
    // turned on. Safe to call even if already granted/denied — the OS only
    // ever prompts once (see LocalReminderService.requestPermission's own
    // doc) — and the preference is saved either way below regardless of
    // the answer, mirroring the web app's graceful-denial handling.
    if (next.periodRemindersEnabled) {
      await LocalReminderService.instance.requestPermission();
    }
    try {
      final saved = await OvaCareApi.instance.updateNotificationPreferences(next);
      if (mounted) setState(() => _prefs = saved);
      // Best-effort, separate from the save itself: a failure fetching the
      // estimate here must never be reported as a failure to save the
      // preference, which already succeeded above.
      try {
        final estimate = await OvaCareApi.instance.cycleEstimate();
        await LocalReminderService.instance.syncUpcomingPeriodReminder(estimate: estimate, preference: saved);
      } catch (_) {
        // Ignored — see comment above.
      }
    } on ApiException catch (e) {
      setState(() => _prefsError = e.message);
    } catch (_) {
      setState(() => _prefsError = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _savingPrefs = false);
    }
  }

  Future<void> _withdrawConsent(ConsentType type) async {
    try {
      await OvaCareApi.instance.withdrawConsent(type);
      await _load();
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _grantConsent(ConsentType type) async {
    try {
      await OvaCareApi.instance.submitConsent(type);
      await _load();
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _deleteAccount() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete account'),
        content: const Text('This deactivates your account and marks your data for deletion. Continue?'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await OvaCareApi.instance.deleteMe();
      if (mounted) await context.read<AppState>().logout();
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _logout() async {
    await context.read<AppState>().logout();
  }

  @override
  Widget build(BuildContext context) {
    if (_loadError != null) {
      return Padding(padding: const EdgeInsets.all(16), child: ErrorBanner(message: _loadError!));
    }
    if (_profile == null || _prefs == null || _consents == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildProfileCard(),
        const SizedBox(height: 16),
        _buildNotificationsCard(),
        const SizedBox(height: 16),
        _buildConsentCard(),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                OutlinedButton.icon(onPressed: _logout, icon: const Icon(Icons.logout), label: const Text('Log out')),
                const SizedBox(height: 10),
                Text(
                  'This deactivates your account and marks your data for deletion.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 8),
                FilledButton.tonalIcon(
                  onPressed: _deleteAccount,
                  icon: const Icon(Icons.delete_forever_outlined),
                  label: const Text('Delete my account'),
                  style: FilledButton.styleFrom(
                    backgroundColor: Theme.of(context).colorScheme.errorContainer,
                    foregroundColor: Theme.of(context).colorScheme.onErrorContainer,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildProfileCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Profile', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 10),
            if (_profileError != null) ...[ErrorBanner(message: _profileError!), const SizedBox(height: 10)],
            TextField(
              enabled: false,
              controller: TextEditingController(text: _profile!.email),
              decoration: const InputDecoration(labelText: 'Email'),
            ),
            const SizedBox(height: 10),
            TextField(controller: _fullNameController, decoration: const InputDecoration(labelText: 'Full name')),
            const SizedBox(height: 10),
            TextField(
              controller: _heightController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Height (cm)'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _weightController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Weight (kg)'),
            ),
            const SizedBox(height: 8),
            Text(
              'BMI: ${_profile!.bmi ?? '—'} (informational only — not the primary factor in your screening result)',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _savingProfile ? null : _saveProfile,
              child: _savingProfile
                  ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNotificationsCard() {
    final prefs = _prefs!;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Period reminder', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            if (_prefsError != null) ...[ErrorBanner(message: _prefsError!), const SizedBox(height: 10)],
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Enable reminders'),
              value: prefs.periodRemindersEnabled,
              onChanged: _savingPrefs ? null : (v) => _savePrefs(prefs.copyWith(periodRemindersEnabled: v)),
            ),
            DropdownButtonFormField<int>(
              value: prefs.daysBeforePeriod,
              decoration: const InputDecoration(labelText: 'Remind me'),
              items: NotificationPreference.daysBeforeOptions
                  .map((d) => DropdownMenuItem(value: d, child: Text('$d day(s) before')))
                  .toList(),
              onChanged: _savingPrefs ? null : (v) => _savePrefs(prefs.copyWith(daysBeforePeriod: v)),
            ),
            const SizedBox(height: 10),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Use private notification text'),
              subtitle: const Text('Shows only "You have an OvaCare reminder." on your lock screen.'),
              value: prefs.privacyMode,
              onChanged: _savingPrefs ? null : (v) => _savePrefs(prefs.copyWith(privacyMode: v)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConsentCard() {
    final activeTypes = _consents!.where((c) => c.isActive).map((c) => c.consentType).toSet();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Consent', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            const Text(
              'Service usage and health-data processing are required to use OvaCare and were accepted when you '
              'registered. The rest are optional — turn them on or off any time; nothing below affects your '
              'ability to track cycles or symptoms.',
              style: TextStyle(fontSize: 12),
            ),
            for (final type in ConsentType.values)
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                title: Text(type.label),
                subtitle: Text(
                  type.isRequired ? '${type.description} (required — active)' : type.description,
                  style: const TextStyle(fontSize: 12),
                ),
                value: type.isRequired ? true : activeTypes.contains(type),
                onChanged: type.isRequired
                    ? null
                    : (checked) => checked == true ? _grantConsent(type) : _withdrawConsent(type),
              ),
          ],
        ),
      ),
    );
  }
}
