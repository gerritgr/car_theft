"""Run the full analysis pipeline: executes notebooks 01-06 in order.

Prerequisites (one-time setup before running this):
    1. Place LAPD raw CSVs in data/raw/
    2. uv run python data/download_data.py
    3. uv run jupyter nbconvert --to notebook --execute --inplace data/preprocess_data.ipynb

Usage:
    uv run car-theft
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

NOTEBOOKS = [
    "notebooks/01_baseline.ipynb",
    "notebooks/02_temporal_analysis.ipynb",
    "notebooks/03_spatial_analysis.ipynb",
    "notebooks/04_explanatory_analysis.ipynb",
    "notebooks/05_vehicle_analysis.ipynb",
    "notebooks/06_spatiotemporal_analysis.ipynb",
]


def run() -> None:
    print(f"Project root: {ROOT}")
    for nb_rel in NOTEBOOKS:
        nb = ROOT / nb_rel
        print(f"\n{'=' * 60}\n> {nb_rel}\n{'=' * 60}")
        subprocess.run(
            [
                sys.executable, "-m", "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                "--inplace",
                "--ExecutePreprocessor.timeout=3600",
                str(nb),
            ],
            check=True,
            cwd=ROOT,
        )
    print("\nDone: All notebooks executed.")
    print("   Figures -> reports/figures/")
    print("   Tables  -> reports/tables/")


if __name__ == "__main__":
    run()
