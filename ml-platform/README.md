# ml-platform/

The ML pipeline: data loading → cleaning/preprocessing → feature
engineering → train + compare candidate models → calibrate → evaluate →
explain → save a versioned artifact. See `docs/ml_documentation.md` for
the full write-up (dataset sourcing, feature schema, limitations, model
lifecycle, threshold rationale); this file is just the "how to run it."

## Setup

```bash
cd ml-platform
pip install -r requirements.txt
```

## Get the real dataset (not committed to this repo)

Training requires a real, licensed dataset — this project does not ship
one, and `src/data_loader.py` raises a clear, actionable error rather
than silently substituting synthetic data if it's missing (requirement
#54: "NEVER fabricate a dataset"). Download:

**Kottarathil, P. "Polycystic ovary syndrome (PCOS)" dataset, Kaggle.**
<https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos>
(541 patients, 10 hospitals across Kerala, India.)

Place the file at:

```
ml-platform/data/raw/PCOS_data_without_infertility.csv
```

(`PCOS_infertility.csv` is an optional supplementary file the loader
also recognizes; not required.)

This file could not be downloaded in this project's original development
sandbox — it had no general internet access (see
`docs/deployment.md`'s "Environment constraints encountered") — so no
model trained on it has been produced or committed here. `src/train.py`
and everything downstream of it are real, complete, and were verified
against a synthetic, clearly-labeled fixture instead (see
`tests/test_pipeline_smoke.py`); running them for real is the very next
step once the CSV above is in place.

## Train

```bash
python src/train.py [--model-version 1.0.0]
```

Trains and compares Logistic Regression, Random Forest, and XGBoost (if
installed — falls back with a logged warning if not, never silently
skipped), selects the winner by PR-AUC (not accuracy — see
`docs/ml_documentation.md`), calibrates it, and writes the artifact plus
full metadata to `models/staging/`. Nothing here writes to
`models/production/` — promotion is a separate, deliberate step
(requirement #39/#77).

## Test

```bash
python -m pytest tests/ -v
```

10 tests, all executable with only `requirements.txt` installed, run
against a synthetic fixture (`tests/test_pipeline_smoke.py`'s
`_make_synthetic_raw_df`) — they check the pipeline's logic (schema
handling, leakage guards, "raise rather than guess" on unexpected raw
values), not real-world model performance, which requires the real
dataset above.
