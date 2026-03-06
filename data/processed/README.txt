data/processed/
================

Cleaned, transformed, and feature-engineered datasets derived from the raw
data.  These files are produced by the notebooks or the src/ scripts and are
safe to overwrite.

Examples of files placed here
------------------------------
- collisions_clean.csv      - Deduplicated and type-cast collision records.
- collisions_hourly.parquet - Aggregated counts binned by hour and borough.

Note: CSV and Parquet files are excluded from version control via .gitignore.
