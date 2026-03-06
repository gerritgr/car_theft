data/
=====

This folder holds all data used in the project.

Subdirectories
--------------
raw/        - Original, immutable raw data dumps. Do NOT modify files here.
processed/  - Cleaned and transformed data ready for analysis or modelling.

Usage
-----
Run `python data/download_data.py` (or `uv run python data/download_data.py`) to
download the NYC Vehicle Collisions dataset into data/raw/.  The script is a
no-op if the file is already present, so it is safe to run repeatedly.

Note: CSV files are excluded from version control via .gitignore.
