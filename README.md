# Multi-Scale Spatio-Temporal Exploratory Analysis of Urban Vehicle Theft

Code and results for the paper [Multi-Scale Spatio-Temporal Exploratory Analysis of Urban Vehicle Theft](https://arxiv.org/abs/2610.36478):
an analysis of vehicle theft in the City of Los Angeles (LAPD jurisdiction), 2000-2022, based on LAPD vehicle-related crime records.

**Data availability:** the LAPD crime records are not public and are not included here. The figures and tables
they produce are in `reports/`, and the executed notebooks show their outputs. Rerunning the pipeline requires the
records in `data/raw/`; all other data can be downloaded with `data/download_data.py`.

## Project Layout

```
car_theft/
├── config.py                     <- Paths, constants, event definition, data loaders, KDE/Gi* helpers
├── data/
│   ├── raw/                      <- Yearly LAPD CSV files (not in git)
│   ├── processed/                <- Geocoded output + loader caches (not in git)
│   ├── download_data.py          <- Downloads and harmonizes weather, Census/ACS, boundaries, OSM POIs
│   └── preprocess_data.ipynb     <- Geocoding pipeline → car_theft_la_geocoded.csv
├── notebooks/                    <- Analysis notebooks 01-06
├── reports/
│   ├── figures/                  <- Generated plots (committed)
│   └── tables/                   <- Generated CSV tables (committed)
├── src/car_theft/main.py         <- Runs notebooks 01-06 in order
├── LICENSE
├── pyproject.toml
└── README.md
```

## Dataset

### Crime data (not public)
LAPD vehicle-related crime records, one CSV per year (`rd_cnvy_crme_YYYY.csv`, 2000-2022), placed in `data/raw/`.
The files contain one row per vehicle per report (DR number) per crime class. Meaning of the classes:

| Crime class | Flag | Meaning | Used as |
|-------------|------|---------|---------|
| 510 | `gta` | Stolen-vehicle report | **The theft event** (one per DR number) |
| 521 | `gta_rcvd` | Vehicle recovered (usually shares the DR of the 510 report) | Recovery outcome |
| 997 | `traffic_dr` | Vehicle in a traffic report | Excluded |
| 330 | `bfv` | Burglary from vehicle | Excluded |
| 740 / 745 | `vand*` | Vandalism | Excluded |
| 420 / 331 | `tfv*` | Theft from vehicle | Excluded |

Data-quality facts the analysis accounts for:
- **Occurrence time**: 2022 records carry no time (`01-JAN-00`); `00:01` is a placeholder for unknown time;
  2018-2021 use non-zero-padded `H:MM:SS`. Unknown times are excluded from hour-of-day analyses.
- **Coordinates**: in 2001 and 2018-2022 stored coordinates are (almost) absent, so locations in those years come
  from address geocoding (`config.GEOCODED_REGIME_YEARS`). Spatial results that change at these years are flagged.
- **End of record**: the 2022 file ends on December 30, 2022, and its last weeks are incomplete, so monthly analyses
  end in October 2022.
- **Jurisdiction**: LAPD covers the City of Los Angeles only. Geocodes outside the city are rejected and all
  tract-level analyses use the 1,110 2020 census tracts with ≥ 50 % of their area inside the city.

### External data

```bash
set CENSUS_API_KEY=your_key_here          # Windows (export ... on Linux/Mac); needed for census2000/acs steps
uv run python data/download_data.py       # all steps; existing outputs are skipped (use --force to redo)
uv run python data/download_data.py harmonise   # run selected steps only
```

| File(s) | Source | Key? |
|---------|--------|------|
| `weather_daily.csv` | Open-Meteo historical archive (downtown LA) | No |
| `acs_{vehicles,income,population}_{2000,2009,2016,2022}.csv` | Census 2000 SF3 (H046, P053, P001); ACS 5-year (B25046, with B25044 where B25046 is suppressed; B19013, B01003) | Yes |
| `census_tracts_la.gpkg` | TIGER/Line 2022 tracts, LA County | No |
| `city_of_la.gpkg` | TIGER/Line 2022 place 0644000 (City of Los Angeles) | No |
| `rel_tract_2000_2010_ca.txt`, `rel_tract_2010_2020_ca.txt` | Census tract relationship files | No |
| `acs_*_{vintage}_tr2020.csv`, `city_tracts.csv` | Built by the `harmonise` step | No |
| `osm_poi_la.gpkg` | OpenStreetMap POIs via osmnx | No |

#### Annual denominators on 2020 tracts

| Vintage | Reference year | Source tract geography |
|---------|----------------|------------------------|
| Census 2000 SF3 | 2000 | 2000 |
| ACS 5-year 2005-2009 | 2007 | 2000 |
| ACS 5-year 2012-2016 | 2014 | 2010 |
| ACS 5-year 2018-2022 | 2020 | 2020 |

Annual values are interpolated linearly per tract between reference years and held constant outside them
(`config.annual_denominator`; `method="step"` gives nearest-vintage values for sensitivity checks).
Older vintages are re-allocated to 2020 tracts with the Census relationship files (2000→2010 by population share,
2010→2020 by land-area share); a target tract is left missing, never zero, when a contributing source value is missing. Vehicle denominators are aggregate vehicles available to households (B25046; estimated from B25044 households by vehicles available where suppressed). Median income is
the population-weighted mean of overlapping source tracts, converted to 2022 dollars with CPI-U.

## Quickstart

```bash
git clone https://github.com/gerritgr/car_theft
cd car_theft
uv sync
# 1. Place data/raw/rd_cnvy_crme_YYYY.csv (2000-2022)
# 2. External data
uv run python data/download_data.py
# 3. Geocoding (one-time; uses Census and Nominatim APIs, resumes from checkpoints in data/)
uv run jupyter nbconvert --to notebook --execute --inplace data/preprocess_data.ipynb
# 4. Analysis notebooks 01-06 → reports/figures, reports/tables
uv run car-theft
```

Notebook 03 must run before 04 and 05 (it writes `data/tracts_plot_gi.gpkg`).
`config.load_theft_data()` caches the deduplicated theft table in `data/processed/thefts_510.pkl` and rebuilds it
whenever the processed CSV or `config.py` changes.

## Notebooks

| Notebook | Contents |
|----------|----------|
| `01_baseline` | Dataset composition, records by crime class, coordinate regimes, geocoding-error validation, time quality, recovery rate |
| `02_temporal_analysis` | STL decomposition, PELT change points (deseasonalized series), seasonality, temperature (seasonal-cycle and anomaly tests), hour × weekday |
| `03_spatial_analysis` | Tract counts and pooled rates, fixed-grid KDE and difference maps, Gi* robustness grid and FDR-controlled hotspots, point-stacking diagnostic |
| `04_explanatory_analysis` | POI presence vs hotspot status (area-adjusted, BH-corrected), negative-binomial count models of theft on exposure, income and POI density |
| `05_vehicle_analysis` | Makes/models, Kia/Hyundai shares with CIs, vehicle age, make concentration maps, old vs new vehicles within the same years |
| `06_spatiotemporal_analysis` | Annual Moran's I, exact-distance Knox test with within-year permutation, rate-based persistence (FDR), centroid drift, Jaccard, diurnal by tier |

## Data Flow

1. `data/preprocess_data.ipynb` turns the raw LAPD files into `data/processed/car_theft_la_geocoded.csv`.
2. `data/download_data.py` fetches and harmonizes the census data, boundaries, weather and POIs.
3. `config.load_theft_data()` combines these into the analysis table: class 510 only, one row per DR number, with
   recovery linkage, parsed times, a city filter and a 2020 tract ID.
4. Notebooks 01, 02, 03 and 06 run independently on that table. Notebook 03 also writes
   `data/tracts_plot_gi.gpkg`, which notebooks 04 and 05 require.

## Citation

```bibtex
@misc{jobanputra2026multiscalespatiotemporalexploratoryanalysis,
  title={Multi-Scale Spatio-Temporal Exploratory Analysis of Urban Vehicle Theft},
  author={Chaitanya Jobanputra and George Mohler and Sebastian Vollmer and Gerrit Gro{\ss}mann},
  year={2026},
  eprint={2610.36478},
  archivePrefix={arXiv},
  primaryClass={cs.CY},
  url={https://arxiv.org/abs/2610.36478},
}
```

## License

MIT, see [LICENSE](LICENSE). The license covers this repository's code and generated outputs, not the LAPD crime
records or third-party data sources.
