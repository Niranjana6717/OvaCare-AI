import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app.dart';
import 'services/local_reminder_service.dart';
import 'state/app_state.dart';

void main() async {
  // Needed before any plugin call (LocalReminderService.initialize) runs
  // ahead of runApp.
  WidgetsFlutterBinding.ensureInitialized();
  // Best-effort — see LocalReminderService's own class doc for why this
  // never throws even where the plugin has no platform channel available.
  await LocalReminderService.instance.initialize();

  runApp(
    ChangeNotifierProvider(
      create: (_) => AppState()..bootstrap(),
      child: const OvaCareApp(),
    ),
  );
}
