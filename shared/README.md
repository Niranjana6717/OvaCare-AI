# shared/

Cross-app reference material — not compiled code, not imported by any
app in this repo (see the note at the top of each file for why: `apps/web`
and `admin/dashboard` are plain JS with no build step, `apps/mobile` is
Dart, and there is no codegen pipeline turning one into the others).

| Path | What it is |
|---|---|
| `api-contracts/openapi.yaml` | Hand-written OpenAPI 3.0 document mirroring `backend/app/api/*.py`. Validated with `python3 -c "import yaml; yaml.safe_load(open('api-contracts/openapi.yaml'))"` — parses cleanly, 28 paths / 30 schemas as of this writing (`/reports/pdf` and `/admin/monitoring` added in a later session). FastAPI generates a live, always-accurate version of this at `/api/v1/openapi.json` when the backend is running; that one wins if the two ever disagree. |
| `types/models.ts` | The same wire shapes as TypeScript interfaces, for quick reference while working on any frontend — snake_case field names, matching the JSON exactly as it crosses the wire. |
| `constants/enums.json` | Canonical enum value lists (`UserRole`, `ScreeningOutcome`, `ConsentType`, ...), hand-synced from `backend/app/database/models/*.py`. |

**If you change an enum, a request shape, or a response shape in the
backend, update these three files in the same change.** Nothing enforces
that automatically today — that's a real gap, not a hidden one, and the
honest fix is either a generated OpenAPI export step in CI (see
`.github/workflows/`) or accepting manual sync as a project convention
and reviewing for it in PRs.
