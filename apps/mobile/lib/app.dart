import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'config.dart';
import 'screens/consent_screen.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'state/app_state.dart';

/// Professional, non-hackathon color scheme matching
/// apps/web/src/css/styles.css's design tokens (--color-primary: #7b3fa0
/// and friends), so the two surfaces read as the same product
/// (requirement #42).
const Color _seedColor = Color(0xFF7B3FA0);

class OvaCareApp extends StatelessWidget {
  const OvaCareApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppConfig.appName,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: _seedColor, brightness: Brightness.light), useMaterial3: true),
      darkTheme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: _seedColor, brightness: Brightness.dark), useMaterial3: true),
      home: const _RootRouter(),
    );
  }
}

/// Mirrors apps/web/src/js/app.js's router() auth-gating: unknown state
/// shows a loading indicator (bootstrap() is checking for a stored
/// session), signedOut goes to LoginScreen, signedIn goes to the main
/// app shell. Flutter's own Navigator handles everything past that
/// point — this widget only decides the ONE fork the whole app depends on.
class _RootRouter extends StatelessWidget {
  const _RootRouter();

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    switch (appState.status) {
      case AuthStatus.unknown:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.signedOut:
        return const LoginScreen();
      case AuthStatus.signedIn:
        // Requirement #57: informed consent BEFORE health-data
        // collection. Gate the very first screen after registration —
        // an existing user who is simply logging back in skips straight
        // to the app, matching apps/web/src/js/app.js's same behavior.
        if (appState.justRegistered) {
          return const ConsentScreen();
        }
        return const HomeShell();
    }
  }
}
