# OvaCare AI — Desktop

Desktop is served by the **same Flutter codebase** as mobile
(`apps/mobile/`), not a separate app. Flutter builds native desktop
targets (Windows, macOS, Linux) from one `lib/` tree, and the product
spec's requirement #43 ("desktop must not just be a stretched mobile
layout") is handled with responsive `LayoutBuilder`/breakpoint logic
inside the shared widgets rather than a forked codebase — a second
codebase would be the thing actually likely to drift out of sync with
the backend contract over time.

```
flutter config --enable-windows-desktop   # or macos-desktop / linux-desktop
flutter run -d windows                    # or macos / linux
```

## What's real here right now

This sandbox has no Flutter SDK and no network access to install one
(see `docs/deployment.md`'s "Environment constraints encountered"
section) — no widget in `apps/mobile/lib/` has been compiled or run in
this environment. The source is written to the same standard the rest
of this codebase holds itself to: it targets the real backend API
(`shared/api-contracts/`), never a mocked one, and it contains no
fabricated prediction or hardcoded screening result. Nothing about the
desktop target specifically has been exercised beyond that — the
distinction from mobile is almost entirely `MediaQuery`/breakpoint
layout logic, which is likewise unverified without a running SDK.

If you're picking this up on a machine with the Flutter SDK installed,
`flutter analyze` and `flutter test` against `apps/mobile/` are the
first things to run — they were the first things this project would
have run too, had the SDK been reachable.
