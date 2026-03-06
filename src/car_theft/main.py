"""Entry point for the car_theft analysis.

This script:
1. Sets global random seeds for reproducibility (Python, NumPy, PyTorch).
2. Loads the raw NYC Vehicle Collisions CSV from data/raw/.
3. Prints summary statistics to stdout.

Usage
-----
    uv run python src/car_theft/main.py
    # or, if the package is installed:
    python -m car_theft.main
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

# ---------------------------------------------------------------------------
# Paths – resolve relative to this file so the script works from any CWD
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / "data" / "raw" / "vehicle_collisions.csv"

SEED = 42


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def set_seeds(seed: int = SEED) -> None:
    """Set random seeds for Python, NumPy and PyTorch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    print(f"[main] Random seeds set to {seed}.")


def load_data(path: Path) -> pd.DataFrame:
    """Load the collision CSV and return a DataFrame."""
    if not path.exists():
        print(
            f"[main] ERROR: Data file not found at '{path}'.\n"
            "       Run  `uv run python data/download_data.py`  first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[main] Loading data from '{path}' …")
    df = pd.read_csv(path, low_memory=False)
    print(f"[main] Loaded {len(df):,} rows × {len(df.columns)} columns.")
    return df


def print_summary(df: pd.DataFrame) -> None:
    """Print summary statistics for the DataFrame."""
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)

    print(f"\nShape : {df.shape[0]:,} rows × {df.shape[1]} columns")

    print("\n--- Column names & dtypes ---")
    for col, dtype in df.dtypes.items():
        print(f"  {col:<45} {dtype}")

    print("\n--- Missing values (columns with any nulls) ---")
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if missing.empty:
        print("  None")
    else:
        for col, count in missing.items():
            pct = 100.0 * count / len(df)
            print(f"  {col:<45} {count:>8,}  ({pct:.1f}%)")

    print("\n--- Numeric columns: descriptive statistics ---")
    numeric_cols = df.select_dtypes(include="number")
    if numeric_cols.empty:
        print("  No numeric columns found.")
    else:
        print(numeric_cols.describe().to_string())

    print("\n--- Temporal coverage ---")
    date_cols = [c for c in df.columns if "date" in c.lower()]
    for col in date_cols:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            valid = parsed.dropna()
            if not valid.empty:
                print(f"  {col}: {valid.min()} → {valid.max()}  ({len(valid):,} valid)")
        except Exception:  # noqa: BLE001
            pass

    print("\n--- Spatial coverage (sample of unique boroughs / zip codes) ---")
    for col in ["BOROUGH", "ZIP CODE"]:
        if col in df.columns:
            unique_vals = df[col].dropna().unique()
            sample = ", ".join(str(v) for v in sorted(unique_vals)[:10])
            print(f"  {col}: {len(unique_vals)} unique values  (sample: {sample})")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    set_seeds(SEED)
    df = load_data(DATA_FILE)
    print_summary(df)


if __name__ == "__main__":
    main()
