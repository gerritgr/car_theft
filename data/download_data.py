"""
Download and harmonise all external data used by the analysis notebooks.

Steps (each is skipped if its output already exists, unless --force is given):
  weather       Open-Meteo daily mean temperature, downtown LA (no key)
  census2000    Census 2000 SF3 tract data: vehicles (H046), income (P053), population (P001)   [key]
  acs           ACS 5-year 2009 / 2016 / 2022 tract data: vehicles (B25046), income (B19013),
                population (B01003)                                                            [key]
  tracts        TIGER/Line 2022 tract polygons, LA County (no key)
  city          TIGER/Line 2022 place polygon for the City of Los Angeles = LAPD jurisdiction (no key)
  relationship  Census tract relationship files 2000->2010 and 2010->2020 for California (no key)
  harmonise     Re-allocate every vintage onto 2020 tract boundaries, convert income to 2022 dollars,
                and list the 2020 tracts that lie inside the City of Los Angeles
  osm           OpenStreetMap POIs for LA County via osmnx (no key)

Usage:
  uv run python data/download_data.py                 # all steps
  uv run python data/download_data.py harmonise       # selected steps
  uv run python data/download_data.py acs --force     # re-download

Steps marked [key] need a free Census API key in the CENSUS_API_KEY environment variable
(https://api.census.gov/data/key_signup.html).
"""

import io
import os
import sys
import zipfile

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
import requests

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(DATA_DIR))
import config  # noqa: E402

CENSUS_GOV_API_KEY = os.environ.get("CENSUS_API_KEY", "")

# ACS 5-year vintages. Tract geography of each vintage:
#   2009 (2005-2009) -> 2000 tracts, 2016 (2012-2016) -> 2010 tracts, 2022 (2018-2022) -> 2020 tracts.
# Census 2000 SF3 is also on 2000 tracts.
ACS_VINTAGES = [2009, 2016, 2022]
SOURCE_TRACT_DECADE = {2000: 2000, 2009: 2000, 2016: 2010, 2022: 2020}

# CPI-U, US city average, annual average (BLS series CUUR0000SA0). Income dollar years:
# SF3 P053 = 1999 dollars; ACS 5-year estimates are in dollars of the final survey year.
CPI_U = {1999: 166.6, 2009: 214.537, 2016: 240.007, 2022: 292.655}
INCOME_DOLLAR_YEAR = {2000: 1999, 2009: 2009, 2016: 2016, 2022: 2022}

LA_CITY_PLACE_GEOID = "0644000"
REL_2000_2010 = os.path.join(DATA_DIR, "rel_tract_2000_2010_ca.txt")
REL_2010_2020 = os.path.join(DATA_DIR, "rel_tract_2010_2020_ca.txt")


def _require_key():
    if not CENSUS_GOV_API_KEY:
        raise EnvironmentError(
            "CENSUS_API_KEY environment variable is not set.\n"
            "Register for a free key at: https://api.census.gov/data/key_signup.html\n"
            "  Windows : set CENSUS_API_KEY=your_key_here\n"
            "  Linux/Mac: export CENSUS_API_KEY=your_key_here"
        )


def _census_get(base_url, variables):
    """Query the Census API for all LA County tracts and return a DataFrame with a GEOID column."""
    _require_key()
    params = {"get": ",".join(variables), "for": "tract:*", "in": "state:06 county:037", "key": CENSUS_GOV_API_KEY}
    resp = requests.get(base_url, params=params, timeout=60)
    if not resp.ok or resp.text.lstrip().startswith("<"):
        raise RuntimeError(f"Census API error {resp.status_code} for {base_url}:\n{resp.text[:300]}")
    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    for v in variables:
        df[v] = pd.to_numeric(df[v], errors="coerce")
    # Census 2000 SF3 returns tracts without a suffix as 4 digits ("1013" = tract 1013.00 = "101300").
    tract = df["tract"].where(df["tract"].str.len() != 4, df["tract"] + "00")
    df["GEOID"] = df["state"].str.zfill(2) + df["county"].str.zfill(3) + tract.str.zfill(6)
    return df


def _acs5_base(vintage):
    """Pre-2012 vintages use the legacy 'acs5' path; 2012+ use 'acs/acs5'."""
    if vintage < 2012:
        return f"https://api.census.gov/data/{vintage}/acs5"
    return f"https://api.census.gov/data/{vintage}/acs/acs5"


def _save(df, name):
    out = os.path.join(DATA_DIR, name)
    df.to_csv(out, index=False)
    print(f"  Saved {out} ({len(df):,} rows)")


def download_weather_data():
    """Daily mean 2 m temperature for downtown LA from the Open-Meteo historical archive."""
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={config.WEATHER_LAT}&longitude={config.WEATHER_LON}"
        "&start_date=2000-01-01&end_date=2022-12-31"
        "&daily=temperature_2m_mean&timezone=America%2FLos_Angeles"
    )
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    weather = pd.DataFrame({"date": pd.to_datetime(data["daily"]["time"]), "mean_temp_c": data["daily"]["temperature_2m_mean"]})
    weather["year"] = weather["date"].dt.year
    weather["month"] = weather["date"].dt.month
    _save(weather, "weather_daily.csv")


def download_census_2000_data():
    """
    Census 2000 SF3, LA County tracts (2000 tract geography):
      H046001 aggregate number of vehicles available (exact total, no top-coding)
      P053001 median household income in 1999 (1999 dollars)
      P001001 total population
    H046 is used rather than H044 (tenure by vehicles available), which is split by owner/renter and top-coded.
    """
    base = "https://api.census.gov/data/2000/dec/sf3"
    veh = _census_get(base, ["H046001"]).rename(columns={"H046001": "total_vehicles"})
    _save(veh[["GEOID", "total_vehicles"]], "acs_vehicles_2000.csv")
    inc = _census_get(base, ["P053001"]).rename(columns={"P053001": "median_income"})
    _save(inc[["GEOID", "median_income"]], "acs_income_2000.csv")
    pop = _census_get(base, ["P001001"]).rename(columns={"P001001": "total_population"})
    _save(pop[["GEOID", "total_population"]], "acs_population_2000.csv")


def download_acs_data(vintage):
    """
    ACS 5-year tract data. Vehicles: B25046_001E, the aggregate number of vehicles available. Where the aggregate
    is suppressed (null or a negative sentinel), it is estimated from B25044 (tenure by vehicles available) as
    sum(k x households with k vehicles), counting "5 or more" as 5; `vehicles_source` records which was used.
    """
    base = _acs5_base(vintage)
    owner = [f"B25044_{i:03d}E" for i in range(4, 9)]      # owner-occupied, 1..5+ vehicles
    renter = [f"B25044_{i:03d}E" for i in range(11, 16)]   # renter-occupied, 1..5+ vehicles
    veh = _census_get(base, ["B25046_001E"] + owner + renter).rename(columns={"B25046_001E": "total_vehicles"})
    k = np.array([1, 2, 3, 4, 5])
    hh = veh[owner].clip(lower=0).values @ k + veh[renter].clip(lower=0).values @ k
    hh_ok = (veh[owner + renter] >= 0).all(axis=1)
    missing = veh["total_vehicles"].isna() | (veh["total_vehicles"] < 0)
    veh["vehicles_source"] = np.where(missing, np.where(hh_ok, "B25044_estimate", "missing"), "B25046")
    veh.loc[missing, "total_vehicles"] = np.where(hh_ok[missing], hh[missing], np.nan)
    print(f"  {vintage}: vehicles from B25046 {(~missing).sum():,}, estimated from B25044 {(missing & hh_ok).sum():,}, "
          f"missing {(missing & ~hh_ok).sum():,}")
    _save(veh[["GEOID", "total_vehicles", "vehicles_source"]], f"acs_vehicles_{vintage}.csv")
    inc = _census_get(base, ["B19013_001E"]).rename(columns={"B19013_001E": "median_income"})
    _save(inc[["GEOID", "median_income"]], f"acs_income_{vintage}.csv")
    pop = _census_get(base, ["B01003_001E"]).rename(columns={"B01003_001E": "total_population"})
    _save(pop[["GEOID", "total_population"]], f"acs_population_{vintage}.csv")


def download_census_tract_shapefile():
    url = "/vsizip//vsicurl/https://www2.census.gov/geo/tiger/TIGER2022/TRACT/tl_2022_06_tract.zip"
    gdf = gpd.read_file(url)
    la = gdf[gdf["COUNTYFP"] == "037"].to_crs(config.LATLON_CRS)
    la[["GEOID", "NAME", "NAMELSAD", "ALAND", "AWATER", "geometry"]].to_file(config.CENSUS_TRACTS, driver="GPKG")
    print(f"  Saved {config.CENSUS_TRACTS}")


def download_city_boundary():
    """City of Los Angeles (Census place 0644000) = LAPD jurisdiction."""
    url = "/vsizip//vsicurl/https://www2.census.gov/geo/tiger/TIGER2022/PLACE/tl_2022_06_place.zip"
    gdf = gpd.read_file(url)
    city = gdf[gdf["GEOID"] == LA_CITY_PLACE_GEOID].to_crs(config.LATLON_CRS)
    if len(city) != 1:
        raise RuntimeError(f"Expected one polygon for place {LA_CITY_PLACE_GEOID}, got {len(city)}")
    city[["GEOID", "NAME", "ALAND", "AWATER", "geometry"]].to_file(config.CITY_BOUNDARY, driver="GPKG")
    print(f"  Saved {config.CITY_BOUNDARY}")


def download_relationship_files():
    files = {
        REL_2000_2010: "https://www2.census.gov/geo/docs/maps-data/data/rel/trf_txt/ca06trf.txt",
        REL_2010_2020: "https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_st06.txt",
    }
    for out, url in files.items():
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        with open(out, "wb") as f:
            f.write(resp.content)
        print(f"  Saved {out}")


def _allocation_weights():
    """
    Return {decade: DataFrame[src, tgt, w]} mapping source-decade tracts (LA County) to 2020 tracts.
    w is the share of the source tract allocated to the target tract (sums to ~1 per source tract).
      2000 -> 2010: population share (POPPCT00, 2010 population of the part as % of the 2000 tract),
                    falling back to land-area share for unpopulated tracts.
      2010 -> 2020: land-area share (the 2020 relationship file carries no population).
      2000 -> 2020: composition of the two.
    """
    cols00 = ["STATE00", "COUNTY00", "TRACT00", "GEOID00", "POP00", "HU00", "PART00", "AREA00", "AREALAND00",
              "STATE10", "COUNTY10", "TRACT10", "GEOID10", "POP10", "HU10", "PART10", "AREA10", "AREALAND10",
              "AREAPT", "AREALANDPT", "AREAPCT00PT", "AREALANDPCT00PT", "AREAPCT10PT", "AREALANDPCT10PT",
              "POP10PT", "POPPCT00", "POPPCT10", "HU10PT", "HUPCT00", "HUPCT10"]
    r0 = pd.read_csv(REL_2000_2010, header=None, names=cols00, dtype=str)
    r0 = r0[r0["COUNTY00"] == "037"]
    for c in ["POP00", "POPPCT00", "AREALANDPCT00PT", "AREAPCT00PT"]:
        r0[c] = pd.to_numeric(r0[c], errors="coerce")
    w = np.where(r0["POP00"] > 0, r0["POPPCT00"], np.where(r0["AREALANDPCT00PT"] > 0, r0["AREALANDPCT00PT"], r0["AREAPCT00PT"])) / 100
    w00_10 = pd.DataFrame({"src": r0["GEOID00"], "tgt": r0["GEOID10"], "w": w})

    r1 = pd.read_csv(REL_2010_2020, sep="|", dtype=str, encoding="utf-8-sig")
    r1 = r1[r1["GEOID_TRACT_10"].str[2:5] == "037"]
    for c in ["AREALAND_PART", "AREALAND_TRACT_10", "AREAWATER_PART", "AREAWATER_TRACT_10"]:
        r1[c] = pd.to_numeric(r1[c], errors="coerce")
    land_ok = r1["AREALAND_TRACT_10"] > 0
    w = np.where(land_ok, r1["AREALAND_PART"] / r1["AREALAND_TRACT_10"].where(land_ok, 1),
                 r1["AREAWATER_PART"] / r1["AREAWATER_TRACT_10"].replace(0, np.nan))
    w10_20 = pd.DataFrame({"src": r1["GEOID_TRACT_10"], "tgt": r1["GEOID_TRACT_20"], "w": w}).fillna({"w": 0})

    w00_20 = (w00_10.merge(w10_20, left_on="tgt", right_on="src", suffixes=("", "_2"))
              .assign(w=lambda d: d["w"] * d["w_2"])
              .groupby(["src", "tgt_2"], as_index=False)["w"].sum()
              .rename(columns={"tgt_2": "tgt"}))
    for d in (w00_20, w10_20):
        d.drop(d[d["w"] <= 0].index, inplace=True)
    return {2000: w00_20, 2010: w10_20}


def harmonise_to_2020_tracts():
    """
    Write acs_{vehicles,population,income}_{vintage}_tr2020.csv on 2020 tract geography:
      counts (vehicles, population) are re-allocated with the source->target weights;
      median income is the source-population-weighted mean of the overlapping source tracts' medians,
      converted to 2022 dollars with CPI-U (an approximation: medians do not aggregate exactly).
    Also writes city_tracts.csv: 2020 tracts with >= 50 % of their area inside the City of Los Angeles.
    """
    weights = _allocation_weights()
    tracts = gpd.read_file(config.CENSUS_TRACTS)
    tract_ids = set(tracts["GEOID"].astype(str).str.zfill(11))

    for vintage in [2000] + ACS_VINTAGES:
        decade = SOURCE_TRACT_DECADE[vintage]
        veh = pd.read_csv(os.path.join(DATA_DIR, f"acs_vehicles_{vintage}.csv"), dtype={"GEOID": str})
        pop = pd.read_csv(os.path.join(DATA_DIR, f"acs_population_{vintage}.csv"), dtype={"GEOID": str})
        inc = pd.read_csv(os.path.join(DATA_DIR, f"acs_income_{vintage}.csv"), dtype={"GEOID": str})
        src = (veh[["GEOID", "total_vehicles"]].merge(pop[["GEOID", "total_population"]], on="GEOID", how="outer")
               .merge(inc[["GEOID", "median_income"]], on="GEOID", how="outer"))
        src["GEOID"] = src["GEOID"].str.zfill(11)
        for c in ["total_vehicles", "total_population", "median_income"]:
            src[c] = pd.to_numeric(src[c], errors="coerce")
            src.loc[src[c] < 0, c] = np.nan            # Census sentinels (-666666666 etc.)
        src["median_income"] *= CPI_U[2022] / CPI_U[INCOME_DOLLAR_YEAR[vintage]]

        if decade == 2020:
            out = src.copy()
        else:
            m = weights[decade].merge(src, left_on="src", right_on="GEOID", how="left")
            m["veh_part"] = m["w"] * m["total_vehicles"]
            m["pop_part"] = m["w"] * m["total_population"]
            # A target is missing if any source part that contributes to it (w >= 1 %) is missing: missing values
            # must never be summed as zero.
            m["veh_missing"] = m["veh_part"].isna() & (m["w"] >= 0.01)
            m["pop_missing"] = m["pop_part"].isna() & (m["w"] >= 0.01)
            ok = m["median_income"].notna() & (m["pop_part"] > 0)
            m["inc_x_pop"] = np.where(ok, m["median_income"] * m["pop_part"], 0.0)
            m["pop_for_inc"] = np.where(ok, m["pop_part"], 0.0)
            out = m.groupby("tgt").agg(total_vehicles=("veh_part", "sum"), total_population=("pop_part", "sum"),
                                       veh_missing=("veh_missing", "any"), pop_missing=("pop_missing", "any"),
                                       inc_x_pop=("inc_x_pop", "sum"), pop_for_inc=("pop_for_inc", "sum")).reset_index()
            out.loc[out["veh_missing"], "total_vehicles"] = np.nan
            out.loc[out["pop_missing"], "total_population"] = np.nan
            out["median_income"] = out["inc_x_pop"] / out["pop_for_inc"].replace(0, np.nan)
            out = out.rename(columns={"tgt": "GEOID"})[["GEOID", "total_vehicles", "total_population", "median_income"]]
            src_tot, out_tot = src["total_vehicles"].sum(), out["total_vehicles"].sum()
            print(f"  {vintage}: vehicles before {src_tot:,.0f} / after crosswalk {out_tot:,.0f} ({out_tot/src_tot*100:.1f}%), "
                  f"{out['total_vehicles'].isna().sum()} 2020 tracts without a vehicle value")

        out = out[out["GEOID"].isin(tract_ids)]
        print(f"  {vintage}: {len(out):,} of {len(tract_ids):,} 2020 tracts receive values")
        out[["GEOID", "total_vehicles"]].to_csv(os.path.join(DATA_DIR, f"acs_vehicles_{vintage}_tr2020.csv"), index=False)
        out[["GEOID", "total_population"]].to_csv(os.path.join(DATA_DIR, f"acs_population_{vintage}_tr2020.csv"), index=False)
        out[["GEOID", "median_income"]].to_csv(os.path.join(DATA_DIR, f"acs_income_{vintage}_tr2020.csv"), index=False)

    city = gpd.read_file(config.CITY_BOUNDARY).to_crs(config.SPATIAL_CRS)
    t = tracts.to_crs(config.SPATIAL_CRS)
    t["GEOID"] = t["GEOID"].astype(str).str.zfill(11)
    t["area"] = t.geometry.area
    inter = gpd.overlay(t[["GEOID", "area", "geometry"]], city[["geometry"]], how="intersection")
    share = (inter.assign(a=inter.geometry.area).groupby("GEOID")["a"].sum() / t.set_index("GEOID")["area"]).fillna(0)
    city_tracts = share.rename("city_area_share").reset_index()
    city_tracts["in_city"] = city_tracts["city_area_share"] >= 0.5
    city_tracts.to_csv(config.CITY_TRACTS, index=False)
    print(f"  Saved {config.CITY_TRACTS}: {city_tracts['in_city'].sum():,} tracts inside the City of Los Angeles")


def download_osm_pois():
    """OSM POIs for LA County, reduced to points (polygon centroids)."""
    place = "Los Angeles County, California, USA"
    queries = [
        {"railway": ["station", "halt", "tram_stop", "subway_entrance"]},
        {"highway": "bus_stop"},
        {"amenity": ["bus_station", "ferry_terminal", "parking", "parking_space", "parking_entrance", "motorcycle_parking",
                     "bicycle_parking", "fast_food", "restaurant", "bar", "cafe", "nightclub", "food_court", "pub", "bank", "atm"]},
        {"parking": True},
        {"shop": True},
        {"landuse": ["retail", "commercial"]},
        {"building": ["retail", "commercial"]},
        {"public_transport": ["stop_position", "platform", "station"]},
    ]
    gdfs = []
    for tags in queries:
        gdf_q = ox.features_from_place(place, tags=tags)
        gdf_q = gdf_q[gdf_q.geometry.notna()].copy()
        gdf_q["geometry"] = gdf_q.geometry.apply(lambda g: g.centroid if g.geom_type != "Point" else g)
        keep = ["geometry"] + [c for c in ["amenity", "shop", "railway", "highway", "parking", "public_transport",
                                           "landuse", "building", "name"] if c in gdf_q.columns]
        gdfs.append(gdf_q[keep].reset_index(drop=True))
    osm_all = pd.concat(gdfs, ignore_index=True).drop_duplicates(subset=["geometry"]).to_crs(config.LATLON_CRS)
    osm_all.to_file(config.OSM_POI, driver="GPKG")
    print(f"  Saved {config.OSM_POI}")


STEPS = {
    "weather":      (download_weather_data, [config.WEATHER_DAILY]),
    "census2000":   (download_census_2000_data, [os.path.join(DATA_DIR, "acs_vehicles_2000.csv")]),
    "acs":          (lambda: [download_acs_data(v) for v in ACS_VINTAGES],
                     [os.path.join(DATA_DIR, f"acs_vehicles_{v}.csv") for v in ACS_VINTAGES]),
    "tracts":       (download_census_tract_shapefile, [config.CENSUS_TRACTS]),
    "city":         (download_city_boundary, [config.CITY_BOUNDARY]),
    "relationship": (download_relationship_files, [REL_2000_2010, REL_2010_2020]),
    "harmonise":    (harmonise_to_2020_tracts, []),
    "osm":          (download_osm_pois, [config.OSM_POI]),
}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    for name in (args or STEPS):
        func, outputs = STEPS[name]
        if outputs and not force and all(os.path.exists(o) for o in outputs):
            print(f"[{name}] outputs exist, skipping (use --force to re-download)")
            continue
        print(f"[{name}]")
        func()
