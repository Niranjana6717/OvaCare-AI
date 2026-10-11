# OvaCare AI — API Documentation

Base URL: `{API_BASE_URL}/api/v1`. All request/response bodies are JSON.
Authenticated endpoints require `Authorization: Bearer <access_token>`.

Interactive docs (FastAPI's built-in Swagger UI) are available at `/docs`
once the backend is running — this file is a stable reference that doesn't
depend on the server being up.

## Auth (`/auth`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/register` | none | `{email, password}` → tokens. Password policy: 10+ chars, letters+digits. |
| POST | `/auth/login` | none | `{email, password}` → tokens |
| POST | `/auth/logout` | required | Revokes the current access token (and refresh token, if provided) |
| POST | `/auth/refresh` | none (body carries refresh token) | Rotates the refresh token — the old one is revoked and cannot be reused |
| POST | `/auth/forgot-password` | none | Always returns the same generic message, whether or not the email is registered |
| POST | `/auth/reset-password` | none | `{token, new_password}` |

## Users (`/users`)

| Method | Path | Notes |
|---|---|---|
| GET | `/users/me` | Profile + computed BMI |
| PUT | `/users/me` | Partial update |
| DELETE | `/users/me` | Soft-deletes the account (requirement #86). Client shows its own confirmation before calling this. |

## Assessments & predictions (`/assessments`, `/predictions`)

| Method | Path | Notes |
|---|---|---|
| POST | `/assessments` | Stores the raw questionnaire answers. Requires `health_data_processing` consent. Does **not** run the model. |
| GET | `/assessments` | List (metadata only) |
| GET | `/assessments/{id}` | Full stored responses, for the review-before-submit screen |
| POST | `/predictions` | `{assessment_id}` — requires `ai_screening_acknowledgement` consent. Runs the safety check (independent of ML) and the model. Returns `{safety: {...}, result: {...}}`. `result.outcome` is one of `higher_indication` / `lower_indication` / `insufficient_data` — never a bare yes/no. |
| GET | `/predictions/history` | All past results for the user, each carrying its own `model_version` etc. — never recalculated with a newer model |

## Cycle tracking (`/cycles`)

| Method | Path | Notes |
|---|---|---|
| POST | `/cycles` | Log a period |
| GET | `/cycles` | List, newest first |
| GET | `/cycles/{id}` | 404 (not 403) if not owned by the caller |
| PUT | `/cycles/{id}` | Partial update |
| DELETE | `/cycles/{id}` | |
| GET | `/cycles/summary` | Average length/duration, variability, `sufficient_data` flag |
| GET | `/cycles/estimate` | `{estimated_start_date, based_on_cycle_count, label: "Estimated next period"}` or `sufficient_data: false` with the standard insufficient-history message |

## Symptoms (`/symptoms`)

Standard CRUD: `POST /symptoms`, `GET /symptoms`, `PUT /symptoms/{id}`,
`DELETE /symptoms/{id}`.

## Insights (`/insights`)

`GET /insights` — cycle trends + symptom trends + static, review-tracked
educational content. Explicitly tagged `"source": "non_diagnostic_insights"`
and never reads from the `predictions` table.

## Notifications (`/notifications`)

`GET /notifications/preferences`, `PUT /notifications/preferences` —
`{period_reminders_enabled, days_before_period (1/2/3/5), notification_time,
cycle_reminders_enabled, symptom_reminders_enabled, privacy_mode, timezone}`.

## Reports (`/reports`)

`GET /reports?sections=profile&sections=cycle_history&...` — the caller
must explicitly list which sections to include; nothing is included by
default. Response separates `data_source_labels.user_provided_health_data`
from `data_source_labels.ai_generated_screening_information`.

`GET /reports/pdf` — same underlying report content, streamed back as
`application/pdf` (`Content-Disposition: attachment;
filename="ovacare-health-report.pdf"`) instead of JSON. Additive: the JSON
endpoint above is unchanged and still available.

## Consent (`/consent`)

| Method | Path | Notes |
|---|---|---|
| GET | `/consent` | Currently-active consents |
| POST | `/consent` | `{consent_type, accepted, consent_version, policy_version, app_version}` — always inserts a new record, never overwrites |
| PUT | `/consent/{consent_type}` | Withdraws an optional consent. Returns 400 for a required one (`core_service`, `health_data_processing`) with an explanation that account deletion is the alternative |

## Admin (`/admin`) — requires the `admin` role

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/users` | Id/email/role/active/created_at only — never health data |
| GET | `/admin/models` | The model version registry — includes each version's `calibration_method` and `dataset_version` |
| GET | `/admin/system-health` | DB reachability, whether a production model is loaded, row counts |
| GET | `/admin/audit-logs` | Paginated |
| GET | `/admin/monitoring` | `window_days` query (1–365, default 30). Prediction outcome distribution, assessment missing-field rate, inference error count, latency stats, and a drift signal computed against the loaded model's own recorded training-time class balance — never a second, separately fabricated "expected" distribution. Never triggers or recommends retraining; see `docs/ml_documentation.md`. |

## Error format

All errors: `{"detail": "..."}`. Unhandled server errors additionally
include a `request_id` for support correlation and log the real exception
server-side only — see `app/middleware/error_handling.py`. Validation
errors (422) include a structured `errors` array from Pydantic.
