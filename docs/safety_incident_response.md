# OvaCare AI — Security & Safety Incident Response

This is a process document — the procedures below are the intended
response process for a deployed instance of OvaCare. No incident has
occurred in this codebase's development; nothing here reports a real
event.

## Severity guide

| Severity | Examples |
|---|---|
| SEV-1 (immediate) | Confirmed data exposure of health information; a live prediction path returning fabricated results; a red-flag/urgent-care message failing to display |
| SEV-2 (same-day) | Compromised admin credentials; a deployed model producing systematically miscalibrated results; notification privacy_mode not being honored |
| SEV-3 (scheduled) | A non-exploited vulnerability found in dependency scanning; a documentation/wording inconsistency with no user-facing effect yet |

## Unauthorized access
1. Revoke the affected credentials immediately: for a user, invalidate all
   outstanding tokens by inserting their currently-active `jti`s (or, more
   simply, forcing a password reset, which does not itself revoke existing
   tokens — also insert `RevokedToken` rows for any known-active sessions).
2. Force-rotate `JWT_SECRET` if the secret itself may have been exposed —
   this invalidates every outstanding token, sessions all users out, and
   requires an announced maintenance window.
3. Pull `audit_logs` for the affected account/timeframe (`action`,
   `actor_user_id`, `target_id`, `created_at` — never raw health payloads,
   by design; see `docs/security.md`).
4. Determine scope: which endpoints, which records. Cross-reference with
   `cycle_records`/`symptoms`/`assessments` row-level `user_id` ownership.

## Suspicious activity
- Elevated 401/403 rates from a single IP → check `RATE_LIMIT_PER_MINUTE`
  is engaged; consider a temporary IP-level block at the reverse proxy.
- Repeated `/admin/*` 403s → likely a non-admin probing; no account
  action needed unless paired with other signals, but log and watch.

## Data exposure
1. Contain: take the affected endpoint offline or patch immediately,
   whichever is faster.
2. Scope: exact tables/rows/timeframe.
3. Notify: per the regulatory obligations of the deployment market (see
   `docs/clinical_safety.md` §9 — not established for this codebase yet).
4. Root-cause and add a regression test in `backend/tests/` before
   reopening the endpoint.

## Compromised credentials (user or admin)
1. Force password reset (`auth_service.complete_password_reset`).
2. Revoke all outstanding tokens for the account.
3. For an admin account specifically: audit every `/admin/*` action taken
   under that account since the estimated compromise window
   (`audit_logs` filtered by `actor_user_id` + `action LIKE 'admin.%'` —
   note: admin actions are not yet individually audit-logged in this
   codebase beyond the generic auth events; see `docs/security.md`'s
   "Known gaps" — extend `log_event()` calls into `app/api/admin.py`
   before this procedure can be followed precisely).

## Model integrity problems
- A production model producing outputs inconsistent with its recorded
  `evaluation_metrics` (e.g. an unexplained shift in the positive-rate of
  live predictions): pull `predictions` grouped by `model_version` and
  compare positive-rate over time; a step change coincident with a
  deployment points at that deployment.
- **Immediate mitigation**: this codebase's `ux_model_versions_single_production`
  database constraint means there is always exactly one unambiguous
  current production model — rolling back means updating that one row's
  `stage` and pointing `MODEL_PATH` back at the prior artifact
  (`ml-platform/models/archived/`), not a complex multi-record migration.
- Never patch a live model file in place; always promote a new, distinctly
  versioned artifact (requirement #77).

## Notification failures
- Reminders not firing: check `notifications.delivery_status` for a
  backlog of `pending` rows past their `scheduled_for` time — indicates the
  (not-yet-built-in-this-codebase, see `docs/deployment.md`) delivery
  worker/provider integration is down, not that the scheduling logic
  itself is wrong (that logic has real test coverage independent of
  delivery — see `docs/clinical_safety.md`, test 6/7 gaps notwithstanding
  for privacy specifically).
- Reminders firing at the wrong local time: check the affected user's
  `NotificationPreference.timezone` and compare against
  `notification_service._local_datetime_to_utc()`'s output for that
  timezone/date — DST transitions are the most likely cause.

## Incorrect model deployment
If a model is promoted whose `feature_schema_version` doesn't match what
the currently-deployed backend expects: `app/ml/model_loader.py` loads
whatever metadata is present without cross-checking it against a backend
version — this is a **known gap**. Mitigation until fixed: any deployment
process must deploy backend and model artifact together, and manually
confirm `feature_schema_version` compatibility as a release-checklist
item, not an automated one.
