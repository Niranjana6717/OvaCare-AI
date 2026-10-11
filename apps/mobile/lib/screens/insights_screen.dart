import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import '../services/api_client.dart';
import '../services/ovacare_api.dart';
import '../widgets/error_banner.dart';

/// Mirrors backend/app/services/recommendation_service.get_insights()'s
/// response shape directly (verified against that file, not guessed):
/// { cycle_trends: {...}, symptom_trends: {...}, educational_content: [...],
///   source: "non_diagnostic_insights" }. Rendered from the raw JSON map
/// rather than a typed model, same pragmatic choice
/// apps/web/src/js/app.js's viewInsights() makes for this one endpoint.
class InsightsScreen extends StatefulWidget {
  const InsightsScreen({super.key});

  @override
  State<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends State<InsightsScreen> {
  late Future<Map<String, dynamic>> _future;

  bool _savingReport = false;

  @override
  void initState() {
    super.initState();
    _future = OvaCareApi.instance.getInsights();
  }

  /// Requirement: PDF health report export, in addition to (not replacing)
  /// the JSON export GET /reports still provides for any client that wants
  /// the raw data. Saves to the app's own documents directory — visible to
  /// the person via their device's Files app (iOS) or file manager
  /// (Android); this app doesn't bundle a PDF viewer or share sheet.
  Future<void> _downloadReport() async {
    setState(() => _savingReport = true);
    try {
      final bytes = await OvaCareApi.instance.downloadReportPdfBytes();
      final dir = await getApplicationDocumentsDirectory();
      final file = File('${dir.path}/ovacare-health-report.pdf');
      await file.writeAsBytes(bytes, flush: true);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Report saved to ${file.path}')),
      );
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Something went wrong. Please try again.')));
      }
    } finally {
      if (mounted) setState(() => _savingReport = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          final message =
              snapshot.error is ApiException ? (snapshot.error as ApiException).message : 'Something went wrong.';
          return Padding(padding: const EdgeInsets.all(16), child: ErrorBanner(message: message));
        }
        final data = snapshot.data!;
        final cycleTrends = data['cycle_trends'] as Map<String, dynamic>;
        final symptomTrends = data['symptom_trends'] as Map<String, dynamic>;
        final educational = (data['educational_content'] as List?) ?? const [];

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('Cycle trends', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: cycleTrends['sufficient_data'] == true
                    ? Text(
                        'Average cycle length: ${cycleTrends['average_cycle_length_days']} days · '
                        'variability: ±${cycleTrends['cycle_variability_stdev_days']} days',
                      )
                    : Text(cycleTrends['message'] as String? ?? 'Not enough data yet.'),
              ),
            ),
            const SizedBox(height: 20),
            Text('Symptom trends (last ${symptomTrends['window_days']} days)',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: (symptomTrends['total_logged'] as int? ?? 0) == 0
                    ? const Text('No symptoms logged in this window yet.')
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${symptomTrends['total_logged']} entries logged'),
                          const SizedBox(height: 6),
                          for (final entry in (symptomTrends['frequency'] as Map).entries)
                            Text('${entry.key}: ${entry.value}×  '
                                '(avg severity ${(symptomTrends['average_severity'] as Map)[entry.key] ?? '—'})'),
                        ],
                      ),
              ),
            ),
            const SizedBox(height: 20),
            Text('Learn more', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            for (final item in educational)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(item['title'] as String, style: Theme.of(context).textTheme.titleSmall),
                      const SizedBox(height: 6),
                      Text(item['body'] as String),
                      const SizedBox(height: 8),
                      // Honest content-review status, never claimed
                      // "clinically reviewed" unless it actually was
                      // (requirement #71).
                      Text(
                        'Content review status: ${item['review_status']}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 20),
            Text('Health Report', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Your profile, cycle summary, symptom summary, and most recent AI screening result, with '
                      'the required disclaimer, as a PDF saved to your device.',
                      style: TextStyle(fontSize: 12),
                    ),
                    const SizedBox(height: 12),
                    FilledButton(
                      onPressed: _savingReport ? null : _downloadReport,
                      child: _savingReport
                          ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Text('Save PDF report'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
