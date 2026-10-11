"""
Raw-CSV -> canonical-schema cleaning.

The public PCOS dataset this pipeline targets is well-documented in
secondary sources (see docs/ml_documentation.md) but this repository has not
been able to open the actual file in this development environment (see
docs/deployment.md, "Environment constraints"). Two encoding assumptions
below are therefore marked VERIFY-BEFORE-TRAINING: they reflect what
multiple independent secondary analyses of this dataset report, but
`validate_raw_columns()` and `_convert_yes_no()` / `_convert_cycle_regularity()`
FAIL LOUDLY on any value outside what's expected, rather than silently
mis-mapping something we guessed wrong. Do not relax those checks without
confirming against the actual downloaded file's data dictionary.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from feature_schema import FEATURES, TARGET_COLUMN, TARGET_COLUMN_RAW

PREPROCESSING_VERSION = "1.0.0"


def normalize_column_name(name: str) -> str:
    """Collapses whitespace/case/punctuation differences so a raw header
    like ' Cycle length(days)' or 'Cycle length (days) ' both match the same
    canonical key. The known messiness of this dataset's headers (inconsistent
    spacing) is exactly why this exists rather than a plain exact-match dict."""
    return re.sub(r"[^a-z0-9]", "", name.strip().lower())


_RAW_TO_CANONICAL = {normalize_column_name(f.source_column): f.name for f in FEATURES if f.source_column}
_RAW_TO_CANONICAL[normalize_column_name(TARGET_COLUMN_RAW)] = TARGET_COLUMN

# VERIFY-BEFORE-TRAINING: multiple secondary analyses of this dataset report
# the Yes/No clinical-symptom columns are stored as integer 1/0. This
# converter also accepts literal "Y"/"N"/"yes"/"no" text so it degrades
# gracefully if that's wrong, but raises on anything else instead of
# guessing.
_YES_VALUES = {"1", "1.0", "y", "yes", "true"}
_NO_VALUES = {"0", "0.0", "n", "no", "false"}

# VERIFY-BEFORE-TRAINING: multiple secondary analyses report the
# "Cycle(R/I)" column uses numeric codes 2 = regular, 4 = irregular. This is
# NOT independently confirmed against the original file in this repository
# (see module docstring) — `_convert_cycle_regularity` raises on any other
# value so a wrong assumption fails the pipeline instead of corrupting labels.
_CYCLE_REGULARITY_CODE_MAP = {"2": "regular", "4": "irregular", "2.0": "regular", "4.0": "irregular"}


class UnexpectedRawValueError(ValueError):
    pass


def _convert_yes_no(series: pd.Series, column_name: str) -> pd.Series:
    def convert(value):
        if pd.isna(value):
            return None
        key = str(value).strip().lower()
        if key in _YES_VALUES:
            return "yes"
        if key in _NO_VALUES:
            return "no"
        raise UnexpectedRawValueError(
            f"Column {column_name!r} contained value {value!r}, which is not a "
            "recognized Yes/No encoding (expected 1/0, Y/N, or yes/no). "
            "Refusing to guess — update _YES_VALUES/_NO_VALUES only after "
            "confirming the real encoding against the source file."
        )

    return series.map(convert)


def _convert_cycle_regularity(series: pd.Series) -> pd.Series:
    def convert(value):
        if pd.isna(value):
            return None
        key = str(value).strip().lower()
        if key in _CYCLE_REGULARITY_CODE_MAP:
            return _CYCLE_REGULARITY_CODE_MAP[key]
        if key in ("regular", "irregular"):
            return key
        raise UnexpectedRawValueError(
            f"Column 'Cycle(R/I)' contained value {value!r}, which is not a "
            "recognized regularity code (expected 2/4 or 'regular'/'irregular'). "
            "See the VERIFY-BEFORE-TRAINING note in this module before changing "
            "the mapping."
        )

    return series.map(convert)


def clean_and_rename(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Renames raw columns to canonical names, drops anything not in the
    schema (identifier columns, columns this schema intentionally excludes),
    and converts known messy encodings. Returns a DataFrame with exactly the
    canonical feature columns + the target column."""
    df = raw_df.copy()
    df.columns = [normalize_column_name(c) for c in df.columns]

    rename_map = {raw: canonical for raw, canonical in _RAW_TO_CANONICAL.items() if raw in df.columns}
    missing_expected = set(_RAW_TO_CANONICAL) - set(df.columns)
    if missing_expected:
        missing_canonical = [_RAW_TO_CANONICAL[m] for m in missing_expected]
        raise UnexpectedRawValueError(
            f"The raw file is missing expected column(s): {missing_canonical}. "
            "Either the schema in feature_schema.py needs updating to match "
            "the actual file, or the wrong file was provided."
        )

    df = df[list(rename_map.keys())].rename(columns=rename_map)

    # AMH is documented (see docs/ml_documentation.md) as sometimes stored
    # as text in the raw file; coerce defensively either way.
    if "amh" in df.columns:
        df["amh"] = pd.to_numeric(df["amh"], errors="coerce")

    for feature in FEATURES:
        if feature.name not in df.columns:
            continue
        if feature.dtype == "categorical" and feature.categories == ["yes", "no"]:
            df[feature.name] = _convert_yes_no(df[feature.name], feature.name)
        elif feature.name == "cycle_regularity":
            df[feature.name] = _convert_cycle_regularity(df[feature.name])
        elif feature.dtype == "numeric":
            df[feature.name] = pd.to_numeric(df[feature.name], errors="coerce")

    df[TARGET_COLUMN] = pd.to_numeric(df[TARGET_COLUMN], errors="coerce").astype("Int64")

    return df


def drop_rows_missing_required(df: pd.DataFrame, required_columns: list[str]) -> tuple[pd.DataFrame, int]:
    """Training (unlike serving) drops rows missing a REQUIRED field rather
    than imputing them — we don't want the model learning from imputed
    values in the fields we've told users are mandatory for a reliable
    result. Returns (clean_df, n_dropped)."""
    before = len(df)
    clean = df.dropna(subset=required_columns + [TARGET_COLUMN])
    return clean, before - len(clean)
