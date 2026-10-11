import 'package:flutter/material.dart';

import '../widgets/app_scaffold.dart';
import 'assessment/assessment_flow_screen.dart';
import 'cycle_tracker_screen.dart';
import 'dashboard_screen.dart';
import 'insights_screen.dart';
import 'settings_screen.dart';
import 'symptom_tracker_screen.dart';

/// The main authenticated app shell — six tabs matching
/// widgets/app_scaffold.dart's ovaCareNavDestinations, one screen per
/// tab, kept alive via IndexedStack so switching tabs doesn't lose a
/// half-filled form (e.g. a cycle log in progress) the way rebuilding
/// from scratch would.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _selectedIndex = 0;

  static const _titles = ['Dashboard', 'Period Tracker', 'Symptoms', 'Assessment', 'Insights', 'Settings'];

  final _screens = const [
    DashboardScreen(),
    CycleTrackerScreen(),
    SymptomTrackerScreen(),
    AssessmentFlowScreen(),
    InsightsScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: _titles[_selectedIndex],
      selectedIndex: _selectedIndex,
      onDestinationSelected: (index) => setState(() => _selectedIndex = index),
      body: IndexedStack(index: _selectedIndex, children: _screens),
    );
  }
}
