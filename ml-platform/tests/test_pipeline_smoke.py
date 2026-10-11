"""
Pipeline mechanics tests, run against a small SYNTHETIC fixture — NOT real
patient data (see module-level SYNTHETIC_NOTE). These verify the
preprocessing/feature-engineering/training CODE runs correctly end-to-end
(requirement #46: "ML tests: preprocessing, feature validation, model
loading, prediction, missing values, invalid values, schema compatibility"),
not that the resulting model is clinically meaningful — a synthetic fixture
cannot demonstrate that, and this file makes no such claim anywhere.

Run with: python3 -m unittest ml_platform.tests.test_pipeline_smoke -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from feature_engineering import apply_feature_engineering  # noqa: E402
from feature_schema import CATEGORICAL_FEATURE_NAMES, NUMERIC_FEATURE_NAMES, REQUIRED_FEATURE_NAMES  # noqa: E402
from preprocessing import (  # noqa: E402
    UnexpectedRawValueError,
    clean_and_rename,
    drop_rows_missing_required,
)

SYNTHETIC_NOTE = "SYNTHETIC TEST FIXTURE — randomly generated, not real patient data."


def _make_synthetic_raw_df(n: int = 60, seed: int = 7) -> pd.DataFrame:
    """Builds a DataFrame with the real dataset's documented raw column
    names/encodings (see feature_schema.py source_column values and the
    VERIFY-BEFORE-TRAINING notes in preprocessing.py), populated with
    random values. Used only to exercise the pipeline's code paths."""
    rng = np.random.default_rng(seed)
    yes_no = lambda: rng.choice([1, 0], size=n)  # documented raw encoding

    df = pd.DataFrame(
        {
            "Age (yrs)": rng.integers(18, 40, size=n),
            "BMI": rng.uniform(18, 35, size=n),
            "Cycle(R/I)": rng.choice([2, 4], size=n),  # 2=regular, 4=irregular per VERIFY-BEFORE-TRAINING
            "Cycle length(days)": rng.integers(21, 45, size=n),
            "Pimples(Y/N)": yes_no(),
            "hair growth(Y/N)": yes_no(),
            "Hair loss(Y/N)": yes_no(),
            "Skin darkening (Y/N)": yes_no(),
            "Weight gain(Y/N)": yes_no(),
            "FSH(mIU/mL)": rng.uniform(2, 12, size=n),
            "LH(mIU/mL)": rng.uniform(2, 15, size=n),
            "FSH/LH": rng.uniform(0.5, 3, size=n),
            "AMH(ng/mL)": rng.uniform(1, 10, size=n),
            "PRL(ng/mL)": rng.uniform(5, 25, size=n),
            "TSH (mIU/L)": rng.uniform(0.5, 5, size=n),
            "Follicle No. (L)": rng.integers(2, 20, size=n),
            "Follicle No. (R)": rng.integers(2, 20, size=n),
            "Fast food (Y/N)": yes_no(),
            "Reg.Exercise(Y/N)": yes_no(),
            "PCOS (Y/N)": rng.choice([1, 0], size=n, p=[0.33, 0.67]),  # mirrors the real dataset's class split
        }
    )
    return df


class TestPreprocessingOnSyntheticFixture(unittest.TestCase):
    """SYNTHETIC TEST FIXTURE — see module docstring."""

    def setUp(self):
        self.raw_df = _make_synthetic_raw_df()

    def test_clean_and_rename_produces_expected_columns(self):
        cleaned = clean_and_rename(self.raw_df)
        for feature_name in NUMERIC_FEATURE_NAMES + CATEGORICAL_FEATURE_NAMES:
            self.assertIn(feature_name, cleaned.columns)

    def test_yes_no_columns_become_canonical_strings(self):
        cleaned = clean_and_rename(self.raw_df)
        self.assertTrue(set(cleaned["acne"].dropna().unique()).issubset({"yes", "no"}))

    def test_cycle_regularity_codes_mapped(self):
        cleaned = clean_and_rename(self.raw_df)
        self.assertTrue(set(cleaned["cycle_regularity"].dropna().unique()).issubset({"regular", "irregular"}))

    def test_unexpected_yes_no_value_raises_rather_than_guesses(self):
        bad_df = self.raw_df.copy()
        bad_df["Pimples(Y/N)"] = bad_df["Pimples(Y/N)"].astype(object)
        bad_df.loc[0, "Pimples(Y/N)"] = "maybe"
        with self.assertRaises(UnexpectedRawValueError):
            clean_and_rename(bad_df)

    def test_unexpected_cycle_code_raises_rather_than_guesses(self):
        bad_df = self.raw_df.copy()
        bad_df.loc[0, "Cycle(R/I)"] = 99
        with self.assertRaises(UnexpectedRawValueError):
            clean_and_rename(bad_df)

    def test_missing_expected_column_raises(self):
        incomplete_df = self.raw_df.drop(columns=["BMI"])
        with self.assertRaises(UnexpectedRawValueError):
            clean_and_rename(incomplete_df)

    def test_drop_rows_missing_required_only_drops_incomplete_rows(self):
        cleaned = clean_and_rename(self.raw_df)
        cleaned.loc[0, "age"] = None  # age is required
        clean, n_dropped = drop_rows_missing_required(cleaned, REQUIRED_FEATURE_NAMES)
        self.assertEqual(n_dropped, 1)
        self.assertEqual(len(clean), len(cleaned) - 1)


class TestFeatureEngineering(unittest.TestCase):
    def test_derives_fsh_lh_ratio_when_missing(self):
        df = pd.DataFrame({"fsh": [10.0], "lh": [5.0], "fsh_lh_ratio": [np.nan]})
        result = apply_feature_engineering(df)
        self.assertAlmostEqual(result.loc[0, "fsh_lh_ratio"], 2.0)

    def test_does_not_overwrite_existing_ratio(self):
        df = pd.DataFrame({"fsh": [10.0], "lh": [5.0], "fsh_lh_ratio": [999.0]})
        result = apply_feature_engineering(df)
        self.assertEqual(result.loc[0, "fsh_lh_ratio"], 999.0)


class TestFullPipelineFitsWithoutError(unittest.TestCase):
    """Confirms the ColumnTransformer + classifier combination in train.py
    actually fits and predicts on cleaned synthetic data — i.e. the
    schema/preprocessing/training code is mechanically correct. Makes no
    claim about accuracy, since the input is synthetic."""

    def test_pipeline_fits_and_predicts(self):
        from sklearn.linear_model import LogisticRegression

        import train as train_module

        raw_df = _make_synthetic_raw_df(n=120)
        df = clean_and_rename(raw_df)
        df = apply_feature_engineering(df)
        df, _ = drop_rows_missing_required(df, REQUIRED_FEATURE_NAMES)

        X = df[NUMERIC_FEATURE_NAMES + CATEGORICAL_FEATURE_NAMES]
        y = df["pcos_label"].astype(int)

        pipeline = train_module.build_preprocessor()
        from sklearn.pipeline import Pipeline

        full_pipeline = Pipeline([("preprocessor", pipeline), ("classifier", LogisticRegression(max_iter=1000))])
        full_pipeline.fit(X, y)
        proba = full_pipeline.predict_proba(X)[:, 1]

        self.assertEqual(len(proba), len(X))
        self.assertTrue(np.all((proba >= 0) & (proba <= 1)))


if __name__ == "__main__":
    unittest.main()
