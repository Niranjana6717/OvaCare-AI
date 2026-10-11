"""
Canonical feature schema — the single source of truth shared by training
(`train.py`) and serving (`backend/app/ml/model_loader.py` reads the
`model_metadata.json` this schema is written into). Defining it once here
means the trained pipeline and the API's input validation can never drift
apart.

--- Where this schema comes from ---

Built against the structure of the real, public "Polycystic ovary syndrome
(PCOS)" dataset by Prasoon Kottarathil on Kaggle
(https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos),
a widely-cited dataset of 541 patients collected across 10 hospitals in
Kerala, India, with 44 raw columns and a binary "PCOS (Y/N)" target
(~33% positive / 67% negative). See docs/ml_documentation.md for full
sourcing, license status, and citations — this docstring is not the
canonical documentation.

FEATURE_SCHEMA_VERSION below is bumped any time a feature is added,
removed, renamed, or has its `required`/range changed.

--- Why some spec-mentioned fields are absent ---

The product brief's questionnaire section lists testosterone, free
testosterone, DHEA-S, and SHBG as *potential* hormonal inputs. The actual
dataset this schema is built against does not include those columns (it has
FSH, LH, the FSH/LH ratio, AMH, and prolactin instead). Per the product
rule "only use fields supported by the final validated model," they are
excluded here rather than added speculatively — see docs/ml_documentation.md
"Excluded candidate fields."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

FEATURE_SCHEMA_VERSION = "1.0.0"

CATEGORICAL_YES_NO = ["yes", "no"]
CYCLE_REGULARITY_VALUES = ["regular", "irregular"]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    dtype: str  # "numeric" | "categorical"
    required: bool
    categories: Optional[list[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    # Raw source column name(s) in the Kaggle CSV this feature is derived
    # from, after normalize_column_name() — see preprocessing.py. Purely
    # documentation/traceability; train.py's REQUIRED_COLUMN_MAP is what's
    # actually used to parse the file.
    source_column: str = ""


# "Basic + menstrual + visible-symptom" fields: things a user can always
# answer without a lab result, so they're required for a screening result
# to be considered reliable (feeds app.ml.preprocessing's missing-required
# check -> INSUFFICIENT_DATA when absent).
FEATURES: list[FeatureSpec] = [
    FeatureSpec("age", "numeric", required=True, min_value=10, max_value=60, source_column="Age (yrs)"),
    FeatureSpec("bmi", "numeric", required=True, min_value=10, max_value=60, source_column="BMI"),
    FeatureSpec(
        "cycle_regularity",
        "categorical",
        required=True,
        categories=CYCLE_REGULARITY_VALUES,
        source_column="Cycle(R/I)",
    ),
    FeatureSpec(
        "average_cycle_length_days",
        "numeric",
        required=True,
        min_value=10,
        max_value=90,
        source_column="Cycle length(days)",
    ),
    FeatureSpec("acne", "categorical", required=True, categories=CATEGORICAL_YES_NO, source_column="Pimples(Y/N)"),
    FeatureSpec(
        "hair_growth_excess",
        "categorical",
        required=True,
        categories=CATEGORICAL_YES_NO,
        source_column="hair growth(Y/N)",
    ),
    FeatureSpec(
        "hair_thinning", "categorical", required=True, categories=CATEGORICAL_YES_NO, source_column="Hair loss(Y/N)"
    ),
    FeatureSpec(
        "skin_darkening",
        "categorical",
        required=True,
        categories=CATEGORICAL_YES_NO,
        source_column="Skin darkening (Y/N)",
    ),
    FeatureSpec(
        "weight_gain", "categorical", required=True, categories=CATEGORICAL_YES_NO, source_column="Weight gain(Y/N)"
    ),
    # --- Optional clinical fields (requirement #9): present in the source
    # dataset, but a user may legitimately not have these results, so
    # missing values here do not block a screening result — the trained
    # pipeline's imputer handles them (see train.py's ColumnTransformer). ---
    FeatureSpec("fsh", "numeric", required=False, min_value=0, max_value=50, source_column="FSH(mIU/mL)"),
    FeatureSpec("lh", "numeric", required=False, min_value=0, max_value=50, source_column="LH(mIU/mL)"),
    FeatureSpec("fsh_lh_ratio", "numeric", required=False, min_value=0, max_value=20, source_column="FSH/LH"),
    FeatureSpec("amh", "numeric", required=False, min_value=0, max_value=30, source_column="AMH(ng/mL)"),
    FeatureSpec("prolactin", "numeric", required=False, min_value=0, max_value=100, source_column="PRL(ng/mL)"),
    FeatureSpec("tsh", "numeric", required=False, min_value=0, max_value=20, source_column="TSH (mIU/L)"),
    FeatureSpec(
        "follicle_count_left",
        "numeric",
        required=False,
        min_value=0,
        max_value=40,
        source_column="Follicle No. (L)",
    ),
    FeatureSpec(
        "follicle_count_right",
        "numeric",
        required=False,
        min_value=0,
        max_value=40,
        source_column="Follicle No. (R)",
    ),
    FeatureSpec(
        "fast_food_frequent",
        "categorical",
        required=False,
        categories=CATEGORICAL_YES_NO,
        source_column="Fast food (Y/N)",
    ),
    FeatureSpec(
        "regular_exercise",
        "categorical",
        required=False,
        categories=CATEGORICAL_YES_NO,
        source_column="Reg.Exercise(Y/N)",
    ),
]

TARGET_COLUMN_RAW = "PCOS (Y/N)"
TARGET_COLUMN = "pcos_label"

REQUIRED_FEATURE_NAMES = [f.name for f in FEATURES if f.required]
ALL_FEATURE_NAMES = [f.name for f in FEATURES]
NUMERIC_FEATURE_NAMES = [f.name for f in FEATURES if f.dtype == "numeric"]
CATEGORICAL_FEATURE_NAMES = [f.name for f in FEATURES if f.dtype == "categorical"]


def feature_specs_as_dicts() -> list[dict]:
    """Serializable form written into model_metadata.json."""
    return [
        {
            "name": f.name,
            "dtype": f.dtype,
            "required": f.required,
            "categories": f.categories,
            "min_value": f.min_value,
            "max_value": f.max_value,
        }
        for f in FEATURES
    ]
