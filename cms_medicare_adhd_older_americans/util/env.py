"""
Project paths, resolved relative to this package so the code runs from any
checkout location. Each can be overridden with an environment variable,
e.g. to keep large downloads outside the repo:

  ADHD_CLEAN_DIR  analysis-ready datasets       (default: <package>/clean)
  ADHD_OUT_DIR    generated workbooks/figures   (default: <package>/out)
"""

from __future__ import annotations
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def _dir(var: str, default: Path) -> Path:
    value = os.environ.get(var)
    return Path(value).expanduser().resolve() if value else default


CLEAN_DIR = _dir("ADHD_CLEAN_DIR", PACKAGE_DIR / "clean")
OUT_DIR = _dir("ADHD_OUT_DIR", PACKAGE_DIR / "out")

STIMULANT_DATASET = CLEAN_DIR / "medicare_partd_stimulant_prescribing_2013_2024.csv"

# Original helper API: DATA_PATH is the repository root, PJCT_PATH the package.
DATA_PATH = str(PACKAGE_DIR.parent)
PJCT_PATH = str(PACKAGE_DIR)


def data_path(*args):
    return os.path.join(DATA_PATH, *args)


def out_path(*args):
    return os.path.join(str(OUT_DIR), *args)
