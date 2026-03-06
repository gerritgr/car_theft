"""Download the NYC Vehicle Collisions dataset if it is not already present.

Dataset: NYC Vehicle Collisions
Source:  https://www.kaggle.com/datasets/nypd/vehicle-collisions

Usage
-----
    python data/download_data.py
    # or
    uv run python data/download_data.py

Notes
-----
The Kaggle API (kaggle-python SDK) is used to fetch the data.  You need a
Kaggle account and an API token (~/.kaggle/kaggle.json) before running this
script.  See https://www.kaggle.com/docs/api for setup instructions.

The CSV is placed at data/raw/vehicle_collisions.csv.  If that file already
exists the script exits early without downloading anything.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent          # data/
RAW_DIR = SCRIPT_DIR / "raw"
TARGET_FILE = RAW_DIR / "vehicle_collisions.csv"

KAGGLE_DATASET = "nypd/vehicle-collisions"
KAGGLE_FILENAME = "vehicle-collisions.csv"


def download() -> None:
    """Download the dataset unless the target file already exists."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if TARGET_FILE.exists():
        print(f"[download_data] Dataset already present at '{TARGET_FILE}'. Skipping download.")
        return

    print(f"[download_data] Downloading '{KAGGLE_DATASET}' from Kaggle …")

    try:
        import kaggle  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "The 'kaggle' package is required to download the dataset.  "
            "Install it with:  uv pip install kaggle"
        ) from exc

    kaggle.api.authenticate()
    kaggle.api.dataset_download_files(
        KAGGLE_DATASET,
        path=str(RAW_DIR),
        unzip=False,
        quiet=False,
    )

    # The Kaggle API downloads a zip archive; extract the CSV from it.
    zip_path = RAW_DIR / f"{KAGGLE_DATASET.split('/')[-1]}.zip"
    if not zip_path.exists():
        # Some datasets are downloaded without a zip wrapper.
        # Try to locate any zip in RAW_DIR.
        zips = list(RAW_DIR.glob("*.zip"))
        if zips:
            zip_path = zips[0]

    if zip_path.exists():
        print(f"[download_data] Extracting '{zip_path}' …")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(RAW_DIR)
        os.remove(zip_path)

    # Rename to a stable filename if needed.
    downloaded_csv = RAW_DIR / KAGGLE_FILENAME
    if downloaded_csv.exists() and downloaded_csv != TARGET_FILE:
        downloaded_csv.rename(TARGET_FILE)

    if TARGET_FILE.exists():
        print(f"[download_data] Dataset saved to '{TARGET_FILE}'.")
    else:
        raise FileNotFoundError(
            f"Download appeared to succeed but '{TARGET_FILE}' was not found.  "
            "Please check the Kaggle dataset page for the actual file name."
        )


if __name__ == "__main__":
    download()
