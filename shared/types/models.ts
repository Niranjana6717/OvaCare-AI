/**
 * OvaCare AI — shared data-shape documentation.
 *
 * This file is NOT compiled or imported by any app in this repo. apps/web
 * and admin/dashboard are plain JS (no build step — see docs/deployment.md
 * for why), and apps/mobile is Dart/Flutter, not TypeScript. There is no
 * cross-language codegen pipeline here, so nothing enforces that this file
 * and the real backend Pydantic schemas (backend/app/schemas/) never drift.
 *
 * What this file IS for: one place a human (or an LLM working on any of
 * the four frontends) can read to see the wire shape of every endpoint
 * response, instead of re-deriving it from backend source each time. Field
 * names match the JSON exactly as FastAPI/Pydantic serializes it —
 * snake_case, not camelCase — because that's what actually crosses the
 * wire and what apps/web/src/js/api.js and admin/dashboard/js/api.js
 * consume directly, unmodified.
 *
 * If a shape here stops matching backend/app/schemas/*.py, the schema
 * file is correct and this one is stale — fix this one.
 */

// --- Enums (see shared/constants/enums.json for the canonical list) ---

export type UserRole = "user" | "admin" | "clinical_reviewer";
export type FlowLevel = "spotting" | "light" | "medium" | "heavy";
export type SymptomType =
  | "acne" | "hair_growth_changes" | "hair_loss" | "pelvic_discomfort"
  | "fatigue" | "mood_changes" | "other";
export type ScreeningOutcome = "lower_indication" | "higher_indication" | "insufficient_data";
export type NotificationType = "upcoming_period" | "period_logging" | "cycle_tracking" | "symptom_logging";
export type ConsentType =
  | "core_service" | "health_data_processing" | "ai_screening_acknowledgement"
  | "notification_permission" | "analytics" | "research_model_improvement";
export type ModelStage = "development" | "validation" | "staging" | "production" | "archived";

// --- Auth ---

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type?: "bearer";
}

// --- User / Profile ---
// NOTE: GET/PUT /users/me is a single flat resource (backend/app/schemas/user.py) —
// there is no separate "account" shape nesting a "profile" object. `role` and
// `is_active` are NOT part of this response; they matter only to the admin
// portal, which reaches them through GET /admin/users instead (see AdminUserRow).

export interface ProfileResponse {
  email: string;
  full_name: string | null;
  date_of_birth: string | null; // date
  height_cm: number | null;
  weight_kg: number | null;
  /** Server-computed from height/weight. Informational only — never the
   *  primary determinant of a screening result (requirement #54
   *  CRITICAL: "NEVER make BMI the primary determinant of screening
   *  result"). */
  bmi: number | null;
  country: string | null;
  phone: string | null;
  timezone: string;
}

export interface ProfileUpdateRequest {
  full_name?: string | null;
  date_of_birth?: string | null;
  height_cm?: number | null;
  weight_kg?: number | null;
  country?: string | null;
  phone?: string | null;
  timezone?: string | null;
}

// --- Cycles ---

export interface CycleCreateRequest {
  start_date: string; // date
  end_date?: string | null;
  flow_level?: FlowLevel | null;
  notes?: string | null;
}

export interface CycleRecord {
  id: string;
  start_date: string; // date
  end_date: string | null;
  flow_level: FlowLevel | null;
  /** Days since the PREVIOUS logged period's start date. Server-computed
   *  (cycle_service), never client-set, and null for the first-ever entry —
   *  never defaulted to 28. */
  cycle_length_days: number | null;
  period_duration_days: number | null; // start_date -> end_date, when end_date is set
  notes: string | null;
}

export interface CycleSummary {
  sufficient_data: boolean; // false below MIN_CYCLES_FOR_AVERAGE (2)
  message: string | null; // present when sufficient_data is false
  average_cycle_length_days: number | null;
  average_period_duration_days: number | null;
  cycle_variability_stdev_days: number | null;
  is_high_variability: boolean; // stdev > 7 days — carries no diagnostic claim by itself
  history: CycleRecord[];
}

export interface CycleEstimate {
  sufficient_data: boolean; // false below MIN_CYCLES_FOR_ESTIMATE (2)
  message: string | null; // e.g. "We need more cycle history to provide a useful personalized estimate."
  estimated_start_date: string | null; // always "Estimated," never asserted
  based_on_cycle_count: number;
  label: string; // "Estimated next period" — render this label, never "Your next period will start on..."
}

// --- Symptoms ---

export interface SymptomCreateRequest {
  symptom_type: SymptomType;
  custom_label?: string | null; // required (server-validated) when symptom_type === "other"
  severity: number; // 1-5, required
  logged_date: string;
  notes?: string | null;
}

export interface Symptom {
  id: string;
  symptom_type: SymptomType;
  custom_label: string | null;
  severity: number; // 1-5
  logged_date: string;
  notes: string | null;
}

// --- Consent ---

export interface ConsentRecord {
  id: string;
  consent_type: ConsentType;
  consent_version: string;
  policy_version: string;
  app_version: string;
  accepted: boolean;
  accepted_at: string | null; // null when accepted === false
  /** null while active; set when withdrawn. Withdrawal SETS this field on
   *  the currently-active row rather than deleting it or mutating
   *  `accepted` — a new decision always inserts a new row instead
   *  (consent_service.record_consent), so history stays reconstructable. */
  withdrawn_at: string | null;
}

export interface ConsentSubmitRequest {
  consent_type: ConsentType;
  accepted: boolean;
  consent_version: string;
  policy_version: string;
  app_version: string;
}

// --- Assessments / Predictions ---

export interface AssessmentSubmitRequest {
  /** Keyed by the model's OWN feature_schema field names — not a fixed
   *  client-side shape, because the valid feature set is versioned by the
   *  model artifact, not the API contract. */
  responses: Record<string, unknown>;
  unanswered_fields: string[];
  // Red-flag safety fields — always collected, checked independently of ML.
  soaking_through_protection_hourly: boolean;
  bleeding_with_dizziness_or_fainting: boolean;
  pelvic_pain_severity: number | null; // 1-5
  fainting_or_severe_dizziness: boolean;
  chest_pain_or_breathing_difficulty: boolean;
}

export interface SafetyCheckResult {
  urgent: boolean;
  message: string | null;
  triggered_rule_ids: string[];
}

export interface PredictionResult {
  assessment_id: string;
  outcome: ScreeningOutcome;
  /** Pre-approved wording only — see backend/app/safety/wording.py. Never
   *  "You have PCOS" / "You do not have PCOS" under any outcome. */
  message: string;
  probability: number | null; // null when outcome === "insufficient_data"
  explanation_framing: string | null;
  explanation: Record<string, unknown>;
  insufficient_data_reason: string | null;
  // Full traceability — an outcome's original versions are never
  // recalculated against a newer model after the fact.
  model_version: string;
  feature_schema_version: string;
  preprocessing_version: string;
  threshold_version: string;
  assessed_at: string;
  medical_disclaimer: string;
}

export interface AssessmentSubmitResponse {
  assessment_id: string;
  safety: SafetyCheckResult;
  result: PredictionResult;
}

// --- Notifications ---

export interface NotificationPreference {
  period_reminders_enabled: boolean;
  days_before_period: 1 | 2 | 3 | 5;
  notification_time: string; // "HH:MM"
  cycle_reminders_enabled: boolean;
  symptom_reminders_enabled: boolean;
  /** Defaults true. When true, delivered text is only "You have an
   *  OvaCare reminder." — never health content on a lock screen. */
  privacy_mode: boolean;
  timezone: string; // IANA tz name
}

// --- Admin (account/system metadata ONLY — see admin/dashboard/README.md) ---

export interface AdminUserRow {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface AdminModelVersionRow {
  id: string;
  model_name: string;
  model_version: string;
  stage: ModelStage;
  evaluation_metrics: Record<string, unknown>;
  review_status: string;
  training_date: string;
  promoted_at: string | null;
  calibration_method: string | null;
  dataset_version: string | null;
}

export interface AdminMonitoringSnapshot {
  window_days: number;
  generated_at: string;
  production_model_version: string | null;
  prediction_distribution: Record<string, unknown>;
  assessment_missing_field_rate_pct: Record<string, unknown>;
  drift: Record<string, unknown> | null;
  inference_errors: Record<string, unknown>;
  inference_latency: Record<string, unknown>;
}

export interface AdminSystemHealth {
  checked_at: string;
  database_reachable: boolean;
  production_model_loaded: boolean;
  production_model_version: string | null;
  total_users: number;
  total_assessments: number;
  total_predictions: number;
}

export interface AdminAuditLogRow {
  id: string;
  actor_user_id: string | null;
  actor_role: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  created_at: string;
}

// --- Generic error shape (backend/app/middleware/error_handling.py) ---

export interface ApiError {
  /** Always a generic, non-leaky message + a request_id for support
   *  correlation — never a raw exception string or stack trace. */
  detail: string;
  request_id?: string;
}
