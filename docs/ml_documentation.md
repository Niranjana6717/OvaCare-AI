# OvaCare AI — ML Documentation

## 1. Dataset

### 1.1 Source and provenance

**Dataset**: "Polycystic ovary syndrome (PCOS)" by Prasoon Kottarathil, published on Kaggle.
**URL**: https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos

This is a real, publicly documented dataset that multiple independent
peer-reviewed and preprint sources cite and describe consistently. It was
identified and verified through web research (see citations below) because
this project's development sandbox does not have general internet access
for file downloads (see `docs/deployment.md`) — the dataset file itself
could **not** be downloaded into this repository. `ml-platform/data/raw/`
is empty; `ml-platform/src/data_loader.py` raises a clear, actionable error
naming exactly this if training is attempted without the file present. No
placeholder or fabricated data is substituted anywhere in its place.

Reported structure, consistent across sources:
- **541 patients**, collected across **10 hospitals across Kerala, India**.
- Two files: `PCOS_data_without_infertility.csv` (the primary file, ~44 raw
  columns) and `PCOS_infertility.csv` (a smaller supplementary file with a
  few additional hormonal columns for a subset of patients). This project's
  schema uses only the primary file (see "Excluded candidate fields" below).
- **Target column**: `PCOS (Y/N)` — binary.
- **Class balance**: 177 positive / 364 negative (~32.7% / ~67.3%) — a real,
  documented, moderate class imbalance, not assumed.

### 1.2 Sourcing citations

These are the sources consulted (via web search/fetch) to document this
dataset without being able to open the file directly:

- Kaggle dataset page: https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos
- GitHub, hariniisathappan/PCOS_Classification_Using_Machine_Learning — reports 541 patients, 177/364 class split, 44→41 feature reduction after removing identifiers.
- ScienceDirect, "Empowering early detection: A web-based machine learning approach for PCOS prediction" (S235291482400056X) — the most detailed source found; supplied the full column table used to build `ml-platform/src/feature_schema.py`, including per-column descriptions, and documented that `Marriage Status (yrs.)`, `Fast food (Y/N)`, and `AMH (ng/mL)` have missing values requiring imputation, and that the raw `AMH (ng/mL)` column contains values that need `pandas.to_numeric()` coercion (reflected in `preprocessing.py`'s defensive handling of that column).
- DOAJ, "Informatics in Medicine Unlocked" (Jan 2024) — independently confirms the 541-patient count.
- Multiple Kaggle notebooks referencing the same file (e.g. "PCOS-A guide to practical machine learning") — consistent with the above.

**What could not be independently verified**: the exact numeric encoding of
the `Cycle(R/I)` column. Multiple secondary sources describe it as coded
`2` = regular, `4` = irregular, but this project could not open the actual
CSV to confirm the codebook against the source. `preprocessing.py` marks
this `VERIFY-BEFORE-TRAINING` and **raises an error rather than silently
mis-mapping** if the real file contains anything other than `2`, `4`,
`"regular"`, or `"irregular"` — see `_convert_cycle_regularity()`. The same
caution applies to the Yes/No symptom columns' encoding (commonly reported
as integer `1`/`0`).

### 1.3 License status

**Not established.** Kaggle dataset pages display licensing information
that requires viewing the live page (JavaScript-rendered), which this
project's fetch tooling could not extract with confidence — see the
"What could not be independently verified" pattern above. **Before this
dataset is used to train a model that is ever promoted to production,
someone with direct access to the Kaggle page must confirm the listed
license and that it permits the intended use** (a commercial or
quasi-commercial health product). This is called out explicitly rather
than assumed, per the product rule against fabricating "clinical
validation" or usage-rights claims.

### 1.4 Population and limitations

Documented (not assumed) limitations, also written into
`ml-platform/src/train.py`'s `LIMITATIONS_TEXT` and copied into every
trained model's `model_metadata.json`, per requirement #71:

- **Single-country, single-region sample**: 541 patients from 10 hospitals
  in Kerala, India. Performance on other populations, ethnicities, age
  distributions, or healthcare settings is not established.
- **Label-quality / measurement bias**: the `PCOS (Y/N)` label reflects
  each source clinic's contemporaneous diagnostic judgment, not a
  standardized, blinded re-adjudication against a single diagnostic
  criterion (e.g. Rotterdam criteria) applied uniformly.
- **Selection bias**: patients were drawn from clinical settings (likely
  gynecology/fertility-adjacent), not a general population sample. This
  probably inflates both PCOS prevalence and symptom severity relative to
  a general screening population, which — if this model were deployed
  against a broader population than it was trained on — would be expected
  to **increase false positives** (over-flagging), not false negatives.
  This directional reasoning is stated explicitly so a future reviewer can
  check it against real validation data rather than accept it on faith.
- **Small size for subgroup analysis**: 541 patients total, ~177 positive.
  `ml-platform/src/evaluate.py`'s `subgroup_metrics()` only reports a
  subgroup's metrics when it has ≥20 samples, and reports "not computed"
  otherwise — it does not compute a number that would be statistically
  meaningless and present it as if it were reliable.

## 2. Feature schema

Defined once, in `ml-platform/src/feature_schema.py`, and read by both the
training pipeline and (via `model_metadata.json`) the serving code in
`backend/app/ml/model_loader.py` — so training and serving can never define
the "same" feature differently.

### 2.1 Required features (block a result if missing — requirement #74)

| Feature | Type | Source column |
|---|---|---|
| `age` | numeric | `Age (yrs)` |
| `bmi` | numeric | `BMI` |
| `cycle_regularity` | categorical (regular/irregular) | `Cycle(R/I)` |
| `average_cycle_length_days` | numeric | `Cycle length(days)` |
| `acne` | categorical (yes/no) | `Pimples(Y/N)` |
| `hair_growth_excess` | categorical (yes/no) | `hair growth(Y/N)` |
| `hair_thinning` | categorical (yes/no) | `Hair loss(Y/N)` |
| `skin_darkening` | categorical (yes/no) | `Skin darkening (Y/N)` |
| `weight_gain` | categorical (yes/no) | `Weight gain(Y/N)` |

These map directly to what the product brief's questionnaire calls "Basic
Information," "Menstrual Information," and "Symptoms" — things a user can
always answer without a lab result.

### 2.2 Optional features (missing is fine — imputed by the trained pipeline)

| Feature | Type | Source column |
|---|---|---|
| `fsh`, `lh`, `fsh_lh_ratio` | numeric | `FSH(mIU/mL)`, `LH(mIU/mL)`, `FSH/LH` |
| `amh` | numeric | `AMH(ng/mL)` |
| `prolactin` | numeric | `PRL(ng/mL)` |
| `tsh` | numeric | `TSH (mIU/L)` |
| `follicle_count_left`, `follicle_count_right` | numeric | `Follicle No. (L)`, `Follicle No. (R)` |
| `fast_food_frequent`, `regular_exercise` | categorical (yes/no) | `Fast food (Y/N)`, `Reg.Exercise(Y/N)` |

BMI is one input among many here, weighted by the model like any other
feature — it is never given special/primary status in the pipeline
(requirement: "BMI can be calculated where appropriate but must not be the
central PCOS prediction factor").

### 2.3 Excluded candidate fields

The product brief lists testosterone, free testosterone, DHEA-S, and SHBG
as *potential* hormonal inputs, and fasting glucose/HbA1c/fasting
insulin/lipid profile as *potential* metabolic inputs. **None of these are
in the real dataset this schema targets** — the dataset has FSH, LH, the
FSH/LH ratio, AMH, and prolactin instead, and no metabolic panel beyond
what's listed above. Per the product rule "only use fields supported by the
final validated model," they are excluded here rather than added on
spec-document authority alone. If a future dataset or lab-integration adds
them, `feature_schema.py` is the one place to extend.

## 3. Model lifecycle

```
Development  →  Validation  →  Clinical/Safety Review  →  Staging  →  Production  →  Monitoring
```

- `ml-platform/src/train.py` writes ONLY to `ml-platform/models/staging/`.
  It never writes to `models/production/`.
- Promotion to production is a separate, manual step — matching
  requirement #77 ("never automatically replace a production model with an
  unvalidated model") — carried out by two scripts, neither of which runs
  automatically or on any schedule:
  - `backend/scripts/register_model_version.py` reads a trained artifact's
    `model_metadata.json` from `ml-platform/models/staging/` and inserts
    (or, if the same version already exists, updates) its `model_versions`
    row with `stage="staging"`. It refuses outright if a *different*
    version is already `production` and the caller tries to register
    straight into that stage — registration only ever lands in `staging`.
  - `backend/scripts/promote_model_version.py` moves exactly one already-
    `staging` version to `production`, requires `--reviewed-by` and
    `--confirm` on the command line (nothing promotes silently), and — in
    the same transaction — demotes whatever was previously `production` to
    `archived` first, so the database's single-production-model constraint
    (below) is never violated mid-transaction. It prints, but does not
    itself perform, the one remaining manual step: updating `MODEL_PATH` in
    `.env` and restarting the backend, since `app/ml/model_loader.py` loads
    a model once per process (`lru_cache`) and has no hot-swap mechanism.
  Running either script is still expected to happen only after confirming
  the dataset license (§1.3) and a clinical/safety content review (see
  `docs/clinical_safety.md`) — the scripts enforce the database-level
  invariants, not the human sign-off, which remains a manual precondition.
- The database schema enforces, at the constraint level, that **only one
  model can hold `production` stage at a time**
  (`ux_model_versions_single_production` in `database/schema/schema.sql` —
  verified against a real local PostgreSQL instance during development; see
  §6).
- `backend/app/ml/model_loader.load_production_model()` reads from
  `MODEL_PATH` (defaults to `ml-platform/models/production/`) and returns
  `None` if nothing is there. **This repository ships with nothing in that
  directory** — see §1, the dataset could not be downloaded — so a freshly
  cloned checkout's screening feature correctly reports
  "No validated production screening model is currently deployed" rather
  than fabricating a result. This was verified end-to-end; see §6.

## 4. Model comparison methodology (requirement #11)

`ml-platform/src/train.py` trains and compares:
1. Logistic Regression (`class_weight="balanced"`)
2. Random Forest (`class_weight="balanced"`)
3. XGBoost, **only if installed** — the script does not fail or silently
   skip it without saying so; it logs
   `"xgboost is not installed — excluded from this run's model comparison"`
   and the run proceeds with the remaining candidates. XGBoost was **not**
   installable in this project's development sandbox (see
   `docs/deployment.md`), so no run performed there included it.

**Selection rule** (stated explicitly, not left implicit): the candidate
with the highest **PR-AUC on the held-out test set** wins. PR-AUC (not
accuracy, and not ROC-AUC alone) is the primary metric because the classes
are imbalanced (~33%/67%) and PR-AUC is more sensitive to minority-class
(positive) performance — directly serving requirement #70's directive to
weight false negatives heavily. The full comparison table for every
candidate is written to `ml-platform/reports/training_report_<version>.json`
so the choice is auditable, not asserted. **XGBoost is never auto-preferred**
— it wins only if it has the best test-set PR-AUC in that specific run.

Every candidate is calibrated (`ml-platform/src/calibrate.py`,
`CalibratedClassifierCV`, Platt/sigmoid method, 5-fold) before evaluation,
so the compared probabilities are calibrated ones, not raw model scores.
The winning candidate's `model_metadata.json` (and, once registered, its
`model_versions` database row) records `calibration_method` (from
`calibrate.CALIBRATION_METHOD`) and `dataset_version` (a fixed identifier
for the specific dataset this schema targets,
`"kaggle-kottarathil-pcos-541-v1"` — see §1.1) alongside the fields it
already recorded (`model_version`, `feature_schema_version`,
`preprocessing_version`, `training_date`, `evaluation_metrics`), so every
served prediction remains traceable to exactly which calibration method
and dataset version produced the model behind it, not just which model
file. Both fields are optional/nullable end-to-end (`ModelMetadata`,
the `model_versions` table, `register_model_version.py`) so an older
artifact saved before this addition still loads and registers correctly.

### Threshold selection rationale (requirement #70)

`DECISION_THRESHOLD = 0.5` is the current starting point in
`train.py`. This is a **default, not a clinically validated cutoff** — it
is explicitly flagged as such in code comments and here. Before production
use, this should be revisited using the calibration curve and PR curve
computed by `evaluate.py` against a validation set, ideally with clinical
input on the relative cost of a false negative (missed screening
opportunity) vs. a false positive (unnecessary worry / follow-up), per
requirement #70's directive to document this rationale rather than pick a
number silently.

## 5. Production monitoring

`backend/app/services/monitoring_service.py` (surfaced via
`GET /admin/monitoring`, `docs/api_documentation.md`) tracks, over a
configurable rolling window (`window_days`, default 30):

- **Prediction outcome distribution** — counts of `higher_indication` /
  `lower_indication` / `insufficient_data` among recent predictions.
- **Assessment missing-field rate** — how often optional questionnaire
  fields are left blank, per field.
- **Inference errors and latency** — `prediction_service.generate_prediction_for_assessment()`
  times every call to `run_prediction()` and records success/failure and
  latency for each one (`record_inference_outcome`), including logging the
  exception (assessment id only — never the raw questionnaire responses)
  via `app.logging_config.log_structured` on failure.
- **Feature/input drift** — `compute_drift_signal()` computes the Population
  Stability Index between the recent positive-outcome rate and the
  currently-loaded model's *own recorded training-time* positive rate
  (`evaluation_metrics.n_positive`/`n_samples` in `model_metadata.json`) —
  deliberately never a second, separately invented "expected" distribution,
  since that would just be a different unverified number.
- **Model version currently serving** — read straight from
  `app/ml/model_loader.py`'s loaded metadata.

This is a **signal, not an action**: `compute_drift_signal()`'s own return
value states in plain language that no model is retrained or replaced
based on it (`backend/tests/test_monitoring_service.py`'s
`test_result_is_a_signal_never_an_instruction_to_retrain` checks this
directly), matching requirement #79 ("never automatically retrain or
replace a model based on drift"). Acting on a drift signal — investigating,
retraining, and going through the full promotion lifecycle in §3 — remains
a human decision.

## 6. What was actually executed vs. documented-and-ready

Being explicit here because the product's own rules (#54, #92) demand it:

**Executed, with real output, in this project's development sandbox:**
- `ml-platform/tests/test_pipeline_smoke.py` (10 tests) — preprocessing,
  feature engineering, and a full scikit-learn `Pipeline` fit/predict cycle,
  run against a small **synthetic** fixture (randomly generated, clearly
  labeled `SYNTHETIC TEST FIXTURE` in the code, never presented as real
  data or real metrics).
- `ml-platform/src/train.py`'s full pipeline (load → clean → engineer →
  split → train → calibrate → evaluate → explain → save artifact) run
  end-to-end against that same synthetic fixture, producing a real
  `model_pipeline.joblib` + `model_metadata.json` + training report — this
  proved the **code** runs correctly; the near-chance metrics it produced
  (PR-AUC ≈ 0.3–0.4 on label-independent random data) are exactly what
  should happen on data with no real signal, and are not reported anywhere
  as real model performance.
- `backend/tests/test_predictor_never_fabricates.py` (5 tests) — trains a
  small **real** (if synthetic-data) scikit-learn pipeline, saves it in
  the exact artifact format `app/ml/model_loader.py` expects, and proves
  the full serving-side contract against it: no model → refuse; required
  field missing → refuse; required field out of range → refuse; complete
  input → a real probability and a real (fallback-method, since SHAP
  wasn't installed in this sandbox either) explanation.
- The PostgreSQL schema (`database/schema/schema.sql`) applied to and
  verified against a real local PostgreSQL 16 server, including the
  `chk_probability_matches_outcome` and single-production-model
  constraints (§3) — proven live, not just written, by attempting inserts
  that should be rejected and confirming the database rejected them.
- `ml-platform/tests/test_train_metadata.py` (1 test, added in a later
  session) — calls `train.py`'s `_save_artifact()` directly with a
  synthetic pipeline to prove `dataset_version` and `calibration_method`
  land correctly in `model_metadata.json`, without needing the real
  dataset or a full training run.
- `backend/tests/test_register_model_version_logic.py` (6 tests) and
  `test_promote_model_version_logic.py` (4 tests), added in that same
  later session — the dependency-free metadata-validation and
  promotion-decision logic behind the two scripts described in §3 above
  (the SQLAlchemy-using `register()`/`promote()` functions themselves
  remain written-but-not-executed, same category as the rest of this
  list).

**Written and ready, not executed in this sandbox:**
- Training against the real Kaggle dataset (the file itself is
  unavailable — §1.1).
- SHAP-based explanations (package not installable — falls back to the
  documented coefficient/importance method, which IS what actually ran).
- XGBoost as a training candidate (package not installable).
- `register_model_version.py --confirm`/`promote_model_version.py
  --confirm`'s actual database writes (need SQLAlchemy + a live
  PostgreSQL connection from Python — the schema itself was still
  verified live via `psql`, above).
