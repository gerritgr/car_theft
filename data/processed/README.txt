data/processed/
===============

car_theft_la_geocoded.csv  All raw rows (2000-2022) with lat_final, lon_final, coord_source
                           (stored / census / nominatim / unresolved), written by data/preprocess_data.ipynb.
thefts_510.pkl             Cache of config.load_theft_data(): one row per stolen-vehicle report (class 510).
records_all.pkl            Cache of config.load_all_records(): one row per (report, crime class).

Caches are rebuilt automatically when the CSV or config.py changes.
