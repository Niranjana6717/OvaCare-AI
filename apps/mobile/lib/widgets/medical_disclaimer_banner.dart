import 'package:flutter/material.dart';

/// Shown wherever a screening/prediction result appears, and small-form
/// wherever the assessment flow starts. Text matches
/// backend/app/safety/wording.py's MEDICAL_DISCLAIMER exactly — this
/// widget renders backend-provided text when given one (via
/// [overrideText]), and this same fallback copy otherwise, but never
/// invents its own wording (requirement #58: "medical disclaimer always
/// shown, never buried").
class MedicalDisclaimerBanner extends StatelessWidget {
  final String? overrideText;
  final bool compact;

  const MedicalDisclaimerBanner({super.key, this.overrideText, this.compact = false});

  static const String fallbackText =
      'OvaCare AI provides an educational, AI-assisted screening result. It is not a medical '
      'diagnosis and does not replace an evaluation by a qualified healthcare professional. If '
      'you have concerns about your health, please consult a doctor.';

  @override
  Widget build(BuildContext context) {
    final text = overrideText ?? fallbackText;
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.symmetric(horizontal: 16, vertical: compact ? 10 : 14),
      margin: const EdgeInsets.only(top: 12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border(top: BorderSide(color: scheme.outlineVariant)),
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: compact ? 12 : 13, color: scheme.onSurfaceVariant, height: 1.4),
      ),
    );
  }
}
