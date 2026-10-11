import 'package:flutter/material.dart';

/// Renders whatever message the caller passes verbatim — for an
/// ApiException that's always the backend's generic, non-leaky error
/// text (see services/api_client.dart's ApiException doc comment). This
/// widget makes no attempt to be "smarter" than that message.
class ErrorBanner extends StatelessWidget {
  final String message;
  const ErrorBanner({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: scheme.errorContainer, borderRadius: BorderRadius.circular(10)),
      child: Text(message, style: TextStyle(color: scheme.onErrorContainer)),
    );
  }
}

class InfoBanner extends StatelessWidget {
  final String message;
  final IconData icon;
  const InfoBanner({super.key, required this.message, this.icon = Icons.info_outline});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: scheme.secondaryContainer, borderRadius: BorderRadius.circular(10)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: scheme.onSecondaryContainer),
          const SizedBox(width: 8),
          Expanded(child: Text(message, style: TextStyle(color: scheme.onSecondaryContainer))),
        ],
      ),
    );
  }
}

class WarningBanner extends StatelessWidget {
  final String message;
  const WarningBanner({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: Colors.amber.shade100, borderRadius: BorderRadius.circular(10)),
      child: Text(message, style: TextStyle(color: Colors.amber.shade900)),
    );
  }
}
