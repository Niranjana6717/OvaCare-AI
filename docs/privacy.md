# OvaCare AI — Privacy

## What's collected, and why
Collected data maps directly to a feature the user opted into: account
credentials (auth), profile (personalization, BMI display), cycle logs
(period tracking), symptoms (symptom tracking), questionnaire responses
(AI screening — only after `health_data_processing` consent is active),
notification preferences. Nothing is collected "just in case."

## Consent gate
No health data flows into an assessment or a prediction without the
corresponding active consent — enforced in code, not just policy:
`app/api/assessments.py` and `app/api/predictions.py` both check
`consent_service.is_consent_active()` before proceeding and return 403 with
an explanatory message if it's missing. See `docs/consent.md`.

## Minimizing sensitive logging
- `app/services/audit_service.py`'s `SENSITIVE_FIELD_DENYLIST` blocks health
  fields from ever reaching the audit log (see `docs/security.md`).
- `app/middleware/error_handling.py` never returns exception internals to
  the client, and application code does not `log.info()` request bodies.
- Notifications default to **private mode**
  (`NotificationPreference.privacy_mode = True` by default) — lock-screen
  text is the generic `"You have an OvaCare reminder."`, never symptom or
  screening content, unless the user explicitly opts into full detail.
- OS-level notification permission (the browser's `Notification.permission`
  on web; the platform notification permission via
  `flutter_local_notifications` on mobile) is requested only when the user
  turns period reminders on, and a denial is handled gracefully — the
  reminder preference itself still saves and is still visible inside the
  app either way; only the OS-level pop-up notification is affected. See
  `apps/web/src/js/app.js`'s `notificationPermissionNote()` and
  `apps/mobile/lib/services/local_reminder_service.dart`.

## Administrator access restriction
Admin endpoints (`app/api/admin.py`) return account/system metadata only —
id, email, role, active flag, timestamps, model registry, aggregate counts,
audit log entries. There is no admin endpoint that returns a user's
`raw_responses`, symptoms, or prediction explanation, and
`test_admin_access_api.py` checks this structurally, not just by omission
in the code someone might later add to.

## Data in transit / at rest
- Transit: the app is HTTPS-ready (`docker-compose.yml` + nginx notes in
  `infrastructure/nginx/`); TLS termination is expected at the
  reverse-proxy/load-balancer layer in production — see
  `docs/deployment.md` §3.
- At rest: standard PostgreSQL storage. Full disk/column-level encryption
  is an infrastructure-layer decision (e.g. managed Postgres with
  encryption-at-rest) not implemented at the application layer here — flag
  this explicitly rather than claim it's handled.

## Account & data management
- **Deletion**: `DELETE /users/me` soft-deletes (`User.deleted_at` +
  `is_active = False`); `get_current_user` treats such a user as
  unauthenticatable immediately, for any outstanding token, without having
  to enumerate and revoke them individually. The client is expected to
  show its own "are you sure" confirmation before calling this endpoint,
  per requirement #86; the endpoint itself performs the deletion.
- **Export**: `GET /reports` lets a user assemble their own data
  (profile/cycle/symptom/screening history) with an explicit
  `data_source_labels` split between user-provided and AI-generated
  content (requirement #87). `GET /reports/pdf` (`app/services/report_pdf_service.py`)
  packages the same information as a downloadable PDF, in addition to (not
  replacing) the JSON endpoint — same content, plus the mandatory
  disclaimer text ("This report is generated from an AI-based screening
  system. It is not a medical diagnosis.") printed on the document itself.
  Both formats are generated on request and streamed straight back to the
  caller; neither is stored server-side or sent anywhere else.
- **Consent withdrawal**: optional consents can be withdrawn at any time
  via `PUT /consent/{type}`; required consents explain that account
  deletion is the alternative rather than silently refusing. See
  `docs/consent.md`.

## Known gaps (stated rather than hidden)
- Encryption-at-rest is an infrastructure decision, not verified here.
- The Kaggle dataset's license terms (docs/ml_documentation.md §1.3) must
  be confirmed before any model trained on it is used in production — this
  bears on data provenance disclosure obligations, not just ML validity.
