import 'package:flutter/material.dart';

import '../config.dart';

class NavDestinationSpec {
  final String label;
  final IconData icon;
  final IconData selectedIcon;

  const NavDestinationSpec({required this.label, required this.icon, required this.selectedIcon});
}

const List<NavDestinationSpec> ovaCareNavDestinations = [
  NavDestinationSpec(label: 'Dashboard', icon: Icons.dashboard_outlined, selectedIcon: Icons.dashboard),
  NavDestinationSpec(label: 'Cycles', icon: Icons.calendar_month_outlined, selectedIcon: Icons.calendar_month),
  NavDestinationSpec(label: 'Symptoms', icon: Icons.healing_outlined, selectedIcon: Icons.healing),
  NavDestinationSpec(label: 'Assessment', icon: Icons.fact_check_outlined, selectedIcon: Icons.fact_check),
  NavDestinationSpec(label: 'Insights', icon: Icons.insights_outlined, selectedIcon: Icons.insights),
  NavDestinationSpec(label: 'Settings', icon: Icons.settings_outlined, selectedIcon: Icons.settings),
];

/// Requirement #43: desktop must not just be a stretched mobile layout.
/// Below [AppConfig.desktopBreakpoint], this renders a standard mobile
/// scaffold with a bottom NavigationBar. At or above it, navigation moves
/// to a permanent side NavigationRail and content gets a constrained,
/// centered max width instead of stretching edge-to-edge — the same
/// layout shift apps/web/src/css/styles.css makes at its own 780px
/// breakpoint (in the opposite direction, since that app's default is
/// desktop-sidebar and it collapses down for mobile).
class AppScaffold extends StatelessWidget {
  final String title;
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;

  const AppScaffold({
    super.key,
    required this.title,
    required this.selectedIndex,
    required this.onDestinationSelected,
    required this.body,
    this.actions,
    this.floatingActionButton,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isDesktop = constraints.maxWidth >= AppConfig.desktopBreakpoint;
        if (isDesktop) {
          return _buildDesktopLayout(context);
        }
        return _buildMobileLayout(context);
      },
    );
  }

  Widget _buildMobileLayout(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title), actions: actions),
      body: SafeArea(child: body),
      floatingActionButton: floatingActionButton,
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: onDestinationSelected,
        destinations: ovaCareNavDestinations
            .map((d) => NavigationDestination(icon: Icon(d.icon), selectedIcon: Icon(d.selectedIcon), label: d.label))
            .toList(),
      ),
    );
  }

  Widget _buildDesktopLayout(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Row(
          children: [
            NavigationRail(
              extended: true,
              minExtendedWidth: 220,
              selectedIndex: selectedIndex,
              onDestinationSelected: onDestinationSelected,
              leading: Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  AppConfig.appName,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
              ),
              destinations: ovaCareNavDestinations
                  .map((d) => NavigationRailDestination(icon: Icon(d.icon), selectedIcon: Icon(d.selectedIcon), label: Text(d.label)))
                  .toList(),
            ),
            const VerticalDivider(width: 1),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(32, 24, 32, 0),
                    child: Row(
                      children: [
                        Expanded(child: Text(title, style: Theme.of(context).textTheme.headlineSmall)),
                        ...(actions ?? const []),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 1100),
                        child: Padding(padding: const EdgeInsets.all(32), child: body),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}
