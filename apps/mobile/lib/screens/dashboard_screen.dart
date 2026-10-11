import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/cycle_record.dart';
import '../services/api_client.dart';
import '../services/ovacare_api.dart';
import '../state/app_state.dart';
import '../widgets/error_banner.dart';
import '../widgets/medical_disclaimer_banner.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late Future<_DashboardData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_DashboardData> _load() async {
    final results = await Future.wait([
      OvaCareApi.instance.cycleSummary(),
      OvaCareApi.instance.cycleEstimate(),
    ]);
    return _DashboardData(results[0] as CycleSummary, results[1] as CycleEstimateResponse);
  }

  @override
  Widget build(BuildContext context) {
    final profile = context.watch<AppState>().currentProfile;
    return RefreshIndicator(
      onRefresh: () async {
        final next = _load();
        setState(() => _future = next);
        await next;
      },
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: FutureBuilder<_DashboardData>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 48),
                child: Center(child: CircularProgressIndicator()),
              );
            }
            if (snapshot.hasError) {
              final message = snapshot.error is ApiException
                  ? (snapshot.error as ApiException).message
                  : 'Something went wrong. Please try again.';
              return ErrorBanner(message: message);
            }
            final data = snapshot.data!;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Welcome back${profile?.fullName != null ? ', ${profile!.fullName}' : ''}',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(child: _StatCard(
                      label: 'Average cycle length',
                      value: data.summary.sufficientData
                          ? '${data.summary.averageCycleLengthDays?.toStringAsFixed(0)} days'
                          : '—',
                      caption: data.summary.sufficientData ? null : data.summary.message,
                    )),
                    const SizedBox(width: 12),
                    Expanded(child: _StatCard(
                      label: 'Estimated next period',
                      value: data.estimate.sufficientData && data.estimate.estimatedStartDate != null
                          ? _formatDate(data.estimate.estimatedStartDate!)
                          : '—',
                      caption: data.estimate.sufficientData ? data.estimate.label : data.estimate.message,
                    )),
                  ],
                ),
                if (data.summary.isHighVariability) ...[
                  const SizedBox(height: 12),
                  const WarningBanner(
                    message: 'Your recent cycle lengths have varied. Continue tracking your cycles, and consider '
                        'discussing persistent changes with a qualified healthcare professional.',
                  ),
                ],
                const SizedBox(height: 20),
                const _QuickActionHint(),
                const MedicalDisclaimerBanner(compact: true),
              ],
            );
          },
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${months[date.month - 1]} ${date.day}';
  }
}

class _DashboardData {
  final CycleSummary summary;
  final CycleEstimateResponse estimate;
  _DashboardData(this.summary, this.estimate);
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final String? caption;

  const _StatCard({required this.label, required this.value, this.caption});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 6),
            Text(value, style: Theme.of(context).textTheme.headlineSmall),
            if (caption != null) ...[
              const SizedBox(height: 4),
              Text(caption!, style: Theme.of(context).textTheme.bodySmall, maxLines: 2, overflow: TextOverflow.ellipsis),
            ],
          ],
        ),
      ),
    );
  }
}

/// A small note rather than deep-linking into another tab's Navigator —
/// this app's tabs are independent IndexedStack entries (see
/// screens/home_shell.dart), so "quick actions" here point the person at
/// the right tab by name instead of performing cross-tab navigation,
/// which would need a shared navigation key this MVP doesn't set up yet.
class _QuickActionHint extends StatelessWidget {
  const _QuickActionHint();

  @override
  Widget build(BuildContext context) {
    return Text(
      'Use the Period Tracker, Symptoms, or Assessment tabs below to log new entries.',
      style: Theme.of(context).textTheme.bodySmall,
    );
  }
}
