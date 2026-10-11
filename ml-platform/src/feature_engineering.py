"""Small, explicit derived-feature step. Kept separate from preprocessing.py
so it's obvious which columns are raw-cleaned vs. computed."""
from __future__ import annotations

import numpy as np
import pandas as pd


def fill_derived_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """The raw file has an explicit FSH/LH column, but if it's missing for a
    row while both fsh and lh are present, compute it rather than leaving a
    derivable value as a needless imputation target."""
    df = df.copy()
    if {"fsh", "lh", "fsh_lh_ratio"}.issubset(df.columns):
        can_derive = df["fsh_lh_ratio"].isna() & df["fsh"].notna() & df["lh"].notna() & (df["lh"] != 0)
        df.loc[can_derive, "fsh_lh_ratio"] = df.loc[can_derive, "fsh"] / df.loc[can_derive, "lh"]
    return df


def apply_feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    return fill_derived_ratio(df)
