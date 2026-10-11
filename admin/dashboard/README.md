# OvaCare AI — Admin Portal

A static HTML/CSS/vanilla-JS single-page app, same no-build-step pattern
as `apps/web/` (see `docs/deployment.md` for why: npm's registry was not
reachable in this project's original development sandbox). Open
`index.html` directly, or serve the directory with any static file
server, and it talks to the backend's `/admin/*` routes.

## What it shows — and what it deliberately never shows

Every screen here is backed by `backend/app/api/admin.py`, and every one
of those routes is scoped, server-side, to return account/system
metadata only:

- **Users** — email, role, active/inactive, created date.
- **Model Versions** — full lifecycle (development → validation →
  staging → production → archived), evaluation metrics, review status,
  and each version's `calibration_method`/`dataset_version`.
- **Monitoring** (`GET /admin/monitoring`) — prediction outcome
  distribution, assessment missing-field rate, inference error count and
  latency, and a drift signal, over a configurable window. Aggregate
  numbers only — no per-user data; see `docs/ml_documentation.md` §5.
- **System Health** — DB reachability, whether a production model is
  currently loaded, and aggregate counts.
- **Audit Logs** — actor, role, action, target type/id, timestamp.

None of this includes a user's cycle records, symptoms, assessment
answers, screening predictions, or free-text explanations. That's not a
UI-level redaction — the API responses never contain those fields in the
first place (requirement #30 / #40), so there's nothing for this portal
to accidentally leak even if a screen here had a bug.

## Getting an admin account

There is no self-service way to become an admin, and no HTTP endpoint
that grants the role — registration always creates a `user`-role
account (`app/services/auth_service.register_user`). To create the
first admin account (or promote an existing one), set
`ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` in the backend's
`.env` and run, once, against the target database:

```bash
cd backend
python scripts/bootstrap_admin.py
```

This creates the account if it doesn't exist yet (admin role from
creation, password hashed the normal way) or promotes it in place if it
already exists (role updated, existing password left untouched — the
script can never be used to take over an unrelated existing account by
guessing its email). Sign in here with that account's normal email and
password, same as any other login.

If you sign in with a non-admin account, the portal will let you submit
the login form (the shared `/auth/login` endpoint has no reason to know
this is the admin portal) and then show "this account does not have
admin access" as soon as it probes `/admin/system-health` and gets a
403 back — it does not assume success from a valid login alone.
