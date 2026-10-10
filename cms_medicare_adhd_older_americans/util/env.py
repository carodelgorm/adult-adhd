"""
Project paths, resolved relative to this package so the code runs from any
checkout location. Each can be overridden with an environment variable,
e.g. to keep large downloads outside the repo:

  ADHD_DATA_DIR   analysis-ready datasets       (default: <package>/data)
  ADHD_OUT_DIR    generated workbooks/figures   (default: <package>)
  ADHD_CLEAN_DIR  intermediate cleaned files    (default: <package>/clean)
"""

from __future__ import annotations
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def _dir(var: str, default: Path) -> Path:
    value = os.environ.get(var)
    return Path(value).expanduser().resolve() if value else default


DATA_DIR = _dir("ADHD_DATA_DIR", PACKAGE_DIR / "data")
OUT_DIR = _dir("ADHD_OUT_DIR", PACKAGE_DIR)
CLEAN_DIR = _dir("ADHD_CLEAN_DIR", PACKAGE_DIR / "clean")

STIMULANT_DATASET = DATA_DIR / "medicare_partd_stimulant_prescribing_2013_2024.csv"

# Original helper API: DATA_PATH is the repository root, PJCT_PATH the package.
DATA_PATH = str(PACKAGE_DIR.parent)
PJCT_PATH = str(PACKAGE_DIR)


def data_path(*args):
    return os.path.join(DATA_PATH, *args)


def out_path(*args):
    return os.path.join(PJCT_PATH, "out", *args)
