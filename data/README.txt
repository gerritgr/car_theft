data/
=====

All data used in the project. Data files are excluded from version control (.gitignore).

Subdirectories
--------------
raw/        LAPD vehicle-related crime CSVs, one per year (rd_cnvy_crme_YYYY.csv, 2000-2022). Do not modify.
processed/  car_theft_la_geocoded.csv (output of preprocess_data.ipynb) and loader caches
            (thefts_510.pkl, records_all.pkl), rebuilt automatically by config.py.

Files produced by download_data.py
----------------------------------
weather_daily.csv                       Daily mean temperature, downtown LA (Open-Meteo)
acs_{vehicles,income,population}_V.csv  Census 2000 SF3 (V=2000) and ACS 5-year (V=2009, 2016, 2022), source tract geography
acs_*_V_tr2020.csv                      Same, re-allocated to 2020 tracts; income in 2022 dollars
rel_tract_2000_2010_ca.txt              Census tract relationship file 2000 -> 2010
rel_tract_2010_2020_ca.txt              Census tract relationship file 2010 -> 2020
census_tracts_la.gpkg                   TIGER/Line 2022 tracts, LA County
city_of_la.gpkg                         TIGER/Line 2022 place 0644000 (City of Los Angeles = LAPD jurisdiction)
city_tracts.csv                         2020 tracts with their share of area inside the city (in_city: >= 50 %)
osm_poi_la.gpkg                         OpenStreetMap POIs, LA County

Geocoding checkpoints (preprocess_data.ipynb)
---------------------------------------------
phase2_reverse.csv     Reverse-geocoded verification sample of stored coordinates (Nominatim)
phase3_census.csv      Census batch geocoder results (with match type)
phase3_nominatim.csv   Nominatim fallback results

Written by notebook 03
----------------------
tracts_plot_gi.gpkg    City tracts with counts, rates, Gi* results and hotspot flags (used by 04 and 05)

Usage
-----
uv run python data/download_data.py      (needs CENSUS_API_KEY for the census2000 / acs steps)
uv run jupyter nbconvert --to notebook --execute --inplace data/preprocess_data.ipynb
