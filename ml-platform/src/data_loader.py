"""
Loads the raw PCOS dataset from ml-platform/data/raw/.

Deliberately does NOT fall back to synthetic or bundled data when the real
file is absent — that would be exactly the "fabricate a dataset" failure
mode this project is built to avoid. If the file isn't there, this raises
`DatasetNotFoundError` naming the exact dependency and how to satisfy it,
per the product rule: "identify the dependency rather than inventing it."
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# The dataset's own two files, as distributed on Kaggle. See
# docs/ml_documentation.md for the full citation and license discussion.
PRIMARY_FILENAME = "PCOS_data_without_infertility.csv"
SECONDARY_FILENAME = "PCOS_infertility.csv"  # optional supplementary file; not required


class DatasetNotFoundError(FileNotFoundError):
    pass


def load_raw_primary(raw_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    path = raw_dir / PRIMARY_FILENAME
    if not path.exists():
        raise DatasetNotFoundError(
            f"Expected the real dataset file at {path}, but it is not present.\n\n"
            "This repository does not ship the dataset itself (it requires a free "
            "Kaggle account to download, and this training environment may not "
            "have general internet access — see docs/ml_documentation.md and "
            "docs/deployment.md).\n\n"
            "To proceed:\n"
            f"  1. Download '{PRIMARY_FILENAME}' from "
            "https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos\n"
            f"  2. Place it at {path}\n"
            "  3. Re-run this script.\n\n"
            "No synthetic or placeholder data will be substituted automatically."
        )
    return pd.read_csv(path)


def load_raw_secondary(raw_dir: Path = RAW_DATA_DIR) -> pd.DataFrame | None:
    """The smaller 'with infertility' supplementary file. Optional — several
    published analyses of this dataset use only the primary file, since the
    secondary file mostly duplicates AMH and adds two beta-HCG columns not
    used in this schema (see ml-platform/src/feature_schema.py)."""
    path = raw_dir / SECONDARY_FILENAME
    if not path.exists():
        return None
    return pd.read_csv(path)
