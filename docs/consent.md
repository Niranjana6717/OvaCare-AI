# OvaCare AI — Informed Consent

## Consent types (requirement #58)

| Type | Required? | Gates |
|---|---|---|
| `core_service` | Required | Using the app at all |
| `health_data_processing` | Required | `POST /assessments` |
| `ai_screening_acknowledgement` | Required for screening | `POST /predictions` |
| `notification_permission` | Optional | Reminder scheduling |
| `analytics` | Optional | (not yet wired to any analytics collection — reserved) |
| `research_model_improvement` | Optional | Using a user's data to improve future models — **not implemented as an actual data pipeline in this codebase**; the consent type and gating exist so that pipeline, if built later, has a consent gate from day one rather than retrofitting one |

`app/database/models/consent.py` defines `REQUIRED_CONSENT_TYPES` and
`OPTIONAL_CONSENT_TYPES` as the two source-of-truth sets — nothing else in
the codebase hardcodes which consents are required.

Using the app is never treated as automatic consent to the optional/
research category — each has its own explicit `ConsentRecord` row.

## Record shape and versioning (requirement #59/#60)

Every consent decision is an **insert**, never an update:

```
ConsentRecord: id, user_id, consent_type, consent_version, policy_version,
               app_version, accepted, accepted_at, withdrawn_at
```

`consent_service.get_active_consents()` finds the *latest* row per
`(user_id, consent_type)` and filters to `accepted AND withdrawn_at IS NULL`
— so a full audit trail of every version a user ever saw and whether they
accepted it is always reconstructable by querying all rows, and a material
policy change is handled by asking for a **new** `consent_version` /
`policy_version` acceptance rather than silently carrying forward an old
one.

## Withdrawal (requirement #61)

`PUT /consent/{consent_type}`:
- Optional consent → sets `withdrawn_at` on the active record, returns 200.
  Withdrawal is exactly as many steps as granting it was (one API call) —
  not deliberately harder.
- Required consent → returns 400 with an explanation that account deletion
  (`DELETE /users/me`) is the way to stop that processing entirely, since
  the app cannot function without it.

## What the UI shows before collection (requirement #57)

Built on both clients, reusing the exact wording this section originally
drafted for whoever built the screen:

- **Web** (`apps/web/src/js/app.js`): `viewSettings()` renders every entry
  in `CONSENT_CATALOG` (one card per consent type, required ones shown as
  checked-and-disabled with a "required — active" note, optional ones as
  toggleable checkboxes wired to `submitConsent`/`withdrawConsent`). A
  second, separate screen — `viewAiScreeningConsent()` — is shown the
  first time a user reaches the point of requesting a screening result
  (i.e. right before `POST /predictions`) if `ai_screening_acknowledgement`
  isn't active yet: "Not now" saves the assessment without running a
  prediction, "I understand, show my result" submits that consent and then
  requests the prediction. This was the one genuine gap the audit found —
  `POST /predictions`' consent gate (`app/api/predictions.py`) already
  existed and worked correctly on the backend, but no screen ever reached
  it, so the assessment → screening-result journey was silently broken
  end-to-end before this fix.
- **Mobile** (`apps/mobile/lib/screens/settings_screen.dart`,
  `apps/mobile/lib/screens/assessment/assessment_flow_screen.dart`): the
  same two surfaces, built to match — `ConsentType`'s `label`/`description`
  getters (`apps/mobile/lib/models/consent.dart`) carry the identical copy
  used on web, and `_Step.aiConsent` in the assessment flow is the mobile
  equivalent of `viewAiScreeningConsent()`.

No pre-checked boxes on either client for an optional consent a user
hasn't already granted — the toggle reflects `activeConsentMap(consents)`
(web) / `activeTypes.contains(type)` (mobile), never a default of `true`.

A third screen, shown once at registration (`viewConsent()` in
`apps/web/src/js/app.js`; `apps/mobile/lib/screens/consent_screen.dart`)
covers the two *required* consents together before the app is usable at
all. The wording below is what that screen actually renders on both
clients, kept here as the single source of copy so a future change to one
doesn't drift from the other:

```
Before You Continue

OvaCare collects health information to provide period tracking, symptom
tracking, and AI-assisted screening features.

Some questions are optional.

Your screening result is not a medical diagnosis and should not replace
professional medical advice.

You can review our Privacy Policy and manage your data settings at any time.

[View Privacy Policy]

☐ I understand how my information will be used.

[Continue]
```

No pre-checked boxes — the checkbox above starts unchecked, and
`ConsentSubmitRequest.accepted` has no default that could let a client
silently send `true` without the user having interacted with it (it's a
required field).
