import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Project root
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Weather station (downtown LA) - shared by download_data.py and notebooks
WEATHER_LAT = 34.05
WEATHER_LON = -118.24

# Paths
DATA_DIR      = os.path.join(PROJECT_ROOT, "data")
RAW_DATA_DIR  = os.path.join(DATA_DIR, "raw")
PREPROCESSED  = os.path.join(DATA_DIR, "processed", "car_theft_la_geocoded.csv")
THEFT_CACHE   = os.path.join(DATA_DIR, "processed", "thefts_510.pkl")       # built by load_theft_data()
RECORDS_CACHE = os.path.join(DATA_DIR, "processed", "records_all.pkl")      # built by load_all_records()
CENSUS_TRACTS = os.path.join(DATA_DIR, "census_tracts_la.gpkg")              # 2020 tracts, LA County
CITY_BOUNDARY = os.path.join(DATA_DIR, "city_of_la.gpkg")                    # City of LA = LAPD jurisdiction
CITY_TRACTS   = os.path.join(DATA_DIR, "city_tracts.csv")                    # 2020 tracts >= 50 % inside the city
OSM_POI       = os.path.join(DATA_DIR, "osm_poi_la.gpkg")
WEATHER_DAILY = os.path.join(DATA_DIR, "weather_daily.csv")

FIGURES_DIR = os.path.join(PROJECT_ROOT, "reports", "figures")
TABLES_DIR  = os.path.join(PROJECT_ROOT, "reports", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR,  exist_ok=True)

# Study parameters
STUDY_YEARS     = list(range(2000, 2023))
SPATIAL_CRS     = "EPSG:2229"   # California State Plane V - units are US survey FEET, not metres
LATLON_CRS      = "EPSG:4326"
FT_PER_M        = 3.28083333    # US survey feet per metre
KDE_BANDWIDTH_M = 500           # Gaussian kernel sigma, metres
KDE_CELL_M      = 100           # KDE grid cell size, metres
CITY_BUFFER_M   = 100           # tolerance when testing whether a point lies inside the city

# ── Event definition ─────────────────────────────────────────────────────────
# The raw LAPD files hold every vehicle involved in a report (DR_NBR), one row per vehicle per crime
# class. Verified against the data (hour profiles, DR sharing, flags):
#   510  stolen-vehicle report (flag gta)            -> the theft event analysed here
#   521  vehicle recovered (flag gta_rcvd)           -> recovery of a stolen vehicle; usually shares the DR of
#                                                       the 510 report, with the recovery date and place
#   997  traffic report (flag traffic_dr)            -> vehicles involved in traffic DRs, not thefts
#   330  burglary from vehicle (flag bfv), 740/745 vandalism (vand*), 420/331 theft from vehicle (tfv*)
THEFT_CODE    = "510"
RECOVERY_CODE = "521"
TRAFFIC_CODE  = "997"
SEGMENT_CODES = {
    "Vehicle theft (510)":          ["510"],
    "Vehicle recovered (521)":      ["521"],
    "Traffic report vehicle (997)": ["997"],
    "Burglary from vehicle (330)":  ["330"],
    "Vandalism (740/745)":          ["740", "745"],
    "Theft from vehicle (420/331)": ["420", "331"],
}

# Coordinate-source priority when one report appears in several rows
COORD_PRIORITY = {"stored": 0, "census": 1, "nominatim": 2, "unresolved": 3}

# Years in which stored LAPD coordinates are (almost) absent and locations come from geocoding.
# Spatial patterns that change exactly at these years must be checked against this regime switch.
GEOCODED_REGIME_YEARS = [2001, 2018, 2019, 2020, 2021, 2022]

# The 2022 file was extracted on 2022-12-30 and its last weeks are incomplete: weekly counts by report date fall
# from ~480 (Oct) to ~300 (Dec) and December 2022 is the lowest month of the 23 years. Monthly time-series
# analyses therefore end at this month; annual totals for 2022 are slightly understated.
MONTHLY_SERIES_END = "2022-10-01"

# Vehicle model year bounds
MODL_YR_MIN = 1950
MODL_YR_MAX = 2023

# ── Denominators on 2020 tract geography ─────────────────────────────────────
# All vintages are re-allocated to 2020 tracts by data/download_data.py (harmonise step); income is in 2022
# dollars. Annual values are interpolated linearly per tract between the reference years of the vintages
# (Census 2000: 2000; ACS 5-year 2005-2009: 2007; 2012-2016: 2014; 2018-2022: 2020) and held constant outside
# them, so a tract's denominator changes smoothly instead of jumping when the vintage changes.
ACS_VINTAGES = [2000, 2009, 2016, 2022]
ACS_VINTAGE_MIDPOINT = {2000: 2000, 2009: 2007, 2016: 2014, 2022: 2020}
# Nearest-vintage assignment (step function), kept for sensitivity checks: annual_denominator(..., method="step")
ACS_VINTAGE_MAP = (
    {y: 2000 for y in range(2000, 2005)} |   # Census 2000 SF3
    {y: 2009 for y in range(2005, 2012)} |   # ACS 5-year 2005-2009
    {y: 2016 for y in range(2012, 2019)} |   # ACS 5-year 2012-2016
    {y: 2022 for y in range(2019, 2023)}     # ACS 5-year 2018-2022
)
ACS_COLUMNS = {"vehicles": "total_vehicles", "population": "total_population", "income": "median_income"}


def acs_path(kind, vintage):
    """Path of the harmonised (2020-tract) file for kind in {'vehicles', 'population', 'income'}."""
    return os.path.join(DATA_DIR, f"acs_{kind}_{vintage}_tr2020.csv")


def load_acs_all(kind):
    """Return {vintage: Series indexed by 2020 GEOID} for kind in {'vehicles', 'population', 'income'}."""
    col = ACS_COLUMNS[kind]
    out = {}
    for v in ACS_VINTAGES:
        df = pd.read_csv(acs_path(kind, v), dtype={"GEOID": str})
        df["GEOID"] = df["GEOID"].str.zfill(11)
        out[v] = pd.to_numeric(df[col], errors="coerce").set_axis(df["GEOID"])
    return out


def annual_denominator(kind, geoids, method="interpolate"):
    """
    DataFrame (index GEOID, columns STUDY_YEARS) of the annual denominator per tract.
    method="interpolate": linear between vintage reference years (ACS_VINTAGE_MIDPOINT), constant outside them;
        a vintage missing for a tract is bridged from the neighbouring vintages.
    method="step": nearest vintage per ACS_VINTAGE_MAP.
    """
    by_v = load_acs_all(kind)
    idx = pd.Index(geoids, name="GEOID")
    if method == "step":
        return pd.DataFrame({y: by_v[ACS_VINTAGE_MAP[y]].reindex(geoids).values for y in STUDY_YEARS}, index=idx)
    anchors = pd.DataFrame({ACS_VINTAGE_MIDPOINT[v]: by_v[v].reindex(geoids).values for v in ACS_VINTAGES}, index=idx)
    full = anchors.reindex(columns=STUDY_YEARS).astype(float)
    full = full.interpolate(axis=1, method="index", limit_area="inside").ffill(axis=1).bfill(axis=1)
    return full


def load_city_tracts():
    """2020 tract GEOIDs lying (>= 50 % of area) inside the City of Los Angeles."""
    ct = pd.read_csv(CITY_TRACTS, dtype={"GEOID": str})
    return ct.loc[ct["in_city"], "GEOID"].str.zfill(11).tolist()


def load_tracts(city_only=True):
    """2020 tract polygons in SPATIAL_CRS (City of LA only by default)."""
    import geopandas as gpd
    tracts = gpd.read_file(CENSUS_TRACTS)
    tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)
    if city_only:
        tracts = tracts[tracts["GEOID"].isin(load_city_tracts())]
    return tracts.to_crs(SPATIAL_CRS).reset_index(drop=True)


# ── Figure defaults ──────────────────────────────────────────────────────────
FIGURE_DPI          = 300
FIGURE_SIZE_FULL    = (12, 8)
FIGURE_SIZE_WIDE    = (16, 6)
FIGURE_SIZE_REGULAR = (10, 5)
FIGURE_SIZE_SQUARE  = (10, 10)

# Canonical Gi* significance tiers (two-sided pseudo p <= threshold). With 9,999 permutations the smallest
# attainable two-sided p is 2/10,000 = 0.0002, so the top tier is p <= 0.001.
GI_TIER_COLORS = {
    "HH p<=0.001"    : "#67000d",
    "HH p<=0.01"     : "#d6604d",
    "HH p<=0.05"     : "#fddbc7",
    "not significant": "#eeeeee",
    "LL p<=0.05"     : "#d1e5f0",
    "LL p<=0.01"     : "#4393c3",
    "LL p<=0.001"    : "#053061",
}
GI_TIER_ORDER = list(GI_TIER_COLORS)
GI_HOT_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "gi_hot", [GI_TIER_COLORS[t] for t in ["not significant", "HH p<=0.05", "HH p<=0.01", "HH p<=0.001"]])


def gi_tiers(z, p):
    """Assign Gi* tiers from z-scores and two-sided pseudo p-values (eps guards float32 p-values)."""
    eps = 1e-9
    tiers = np.full(len(z), "not significant", dtype=object)
    for thr in [0.05, 0.01, 0.001]:
        sig = np.asarray(p) <= thr + eps
        tiers[sig & (np.asarray(z) > 0)] = f"HH p<={thr:g}"
        tiers[sig & (np.asarray(z) < 0)] = f"LL p<={thr:g}"
    return tiers


def is_special_use(geoids):
    """Census special land-use tracts (tract code 98xx: airport, port, parks); excluded from rate analyses."""
    return pd.Series(geoids).astype(str).str[5:7].eq("98").values


def mann_kendall_hr(x):
    """
    Mann-Kendall trend test with the Hamed & Rao (1998) variance correction for serial correlation.
    Returns dict(tau, sen_slope, z, p). Use for short annual series instead of Spearman p-values.
    """
    from scipy.stats import norm, kendalltau, rankdata
    x = np.asarray(x, dtype=float)
    n = len(x)
    s = sum(np.sign(x[j] - x[i]) for i in range(n - 1) for j in range(i + 1, n))
    var_s = n * (n - 1) * (2 * n + 5) / 18
    slopes = [(x[j] - x[i]) / (j - i) for i in range(n - 1) for j in range(i + 1, n)]
    sen = np.median(slopes)
    r = rankdata(x - sen * np.arange(n))
    r = r - r.mean()
    acf = [np.sum(r[:-k] * r[k:]) / np.sum(r * r) for k in range(1, n - 1)]
    bound = 1.96 / np.sqrt(n)
    corr = 1 + 2 / (n * (n - 1) * (n - 2)) * sum((n - k) * (n - k - 1) * (n - k - 2) * a
                                                 for k, a in enumerate(acf, start=1) if abs(a) > bound)
    var_s *= max(corr, 1e-6)
    z = (s - np.sign(s)) / np.sqrt(var_s) if s != 0 else 0.0
    return {"tau": kendalltau(np.arange(n), x).statistic, "sen_slope": sen, "z": z, "p": 2 * (1 - norm.cdf(abs(z)))}


def gi_star(y, w, permutations=9999, seed=42):
    """
    Getis-Ord Gi* with an explicit self-weight: binary contiguity weights with the diagonal set to 1, then
    row-standardised, so each tract's own value enters its local sum with the same weight as each neighbour.
    Returns (z, p): p is two-sided, i.e. twice esda's directed (one-sided) conditional-permutation p_sim.
    """
    import libpysal
    from esda.getisord import G_Local
    wb = libpysal.weights.W(w.neighbors, id_order=w.id_order, silence_warnings=True)   # binary copy
    wb = libpysal.weights.fill_diagonal(wb, 1.0)
    gi = G_Local(np.asarray(y, dtype=float), wb, transform="R", star=None, permutations=permutations, seed=seed)
    return gi.Zs, np.minimum(1.0, 2.0 * gi.p_sim)


def bh_fdr(p):
    """Benjamini-Hochberg adjusted p-values."""
    from statsmodels.stats.multitest import multipletests
    return multipletests(np.asarray(p, dtype=float), method="fdr_bh")[1]


def shade_geocoded_regime(ax, alpha=0.08):
    """Shade years whose locations come almost entirely from geocoding (x-axis in years)."""
    for y in GEOCODED_REGIME_YEARS:
        ax.axvspan(y - 0.5, y + 0.5, color="#888888", alpha=alpha, lw=0, zorder=0)


def apply_plot_style():
    plt.rcParams.update({
        "font.size": 10,
        "legend.fontsize": 10,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "axes.labelsize": 12,
        "axes.titlesize": 15,
        "figure.titlesize": 15,
    })


# ── KDE on a fixed city grid ─────────────────────────────────────────────────
def city_grid(cell_m=KDE_CELL_M, pad_m=1000):
    """
    Fixed analysis grid over the City of LA in SPATIAL_CRS. Every surface (any period, any subset) is
    evaluated on this grid, so differences between surfaces compare the same cells.
    Returns dict(xedges, yedges, extent, mask) where mask is True for cells whose centre lies in the city.
    """
    import geopandas as gpd
    import shapely
    city = gpd.read_file(CITY_BOUNDARY).to_crs(SPATIAL_CRS).geometry.union_all()
    cell, pad = cell_m * FT_PER_M, pad_m * FT_PER_M
    xmin, ymin, xmax, ymax = city.bounds
    xedges = np.arange(xmin - pad, xmax + pad + cell, cell)
    yedges = np.arange(ymin - pad, ymax + pad + cell, cell)
    xc, yc = np.meshgrid((xedges[:-1] + xedges[1:]) / 2, (yedges[:-1] + yedges[1:]) / 2)
    mask = shapely.contains_xy(city, xc, yc)
    return {"xedges": xedges, "yedges": yedges, "mask": mask, "cell_ft": cell,
            "extent": (xedges[0], xedges[-1], yedges[0], yedges[-1])}


def kde_surface(xs, ys, grid, bandwidth_m=KDE_BANDWIDTH_M, normalise=True):
    """
    Gaussian KDE by binning + convolution on `grid` (rows = y, cols = x). With normalise=True the surface
    sums to 1 over the city, i.e. each cell holds its share of the period's density, so surfaces built from
    different numbers of events are directly comparable.
    """
    from scipy.ndimage import gaussian_filter
    h, _, _ = np.histogram2d(np.asarray(ys), np.asarray(xs), bins=[grid["yedges"], grid["xedges"]])
    z = gaussian_filter(h, sigma=bandwidth_m * FT_PER_M / grid["cell_ft"], mode="constant")
    z = np.where(grid["mask"], z, np.nan)
    if normalise:
        z = z / np.nansum(z)
    return z


def add_basemap(ax, zoom=11, alpha=0.5, source="Esri.WorldGrayCanvas"):
    """Basemap warped into SPATIAL_CRS (Esri light grey; CartoDB tiles now require an API key)."""
    import contextily as ctx
    ctx.add_basemap(ax, crs=SPATIAL_CRS, source=source, zoom=zoom, alpha=alpha, attribution=False)


# ── Parsing helpers ──────────────────────────────────────────────────────────
def parse_occurrence_date(s):
    """Three formats: 2000-2017 '2016-12-29 00:00:00', 2018-2021 '7/19/18 0:00', 2022 '10-MAR-22'."""
    s = s.astype(str).str.strip()
    parsed = pd.to_datetime(s, errors="coerce", format="%Y-%m-%d %H:%M:%S")
    for fmt in ["%m/%d/%y %H:%M", "%d-%b-%y"]:
        mask = parsed.isna()
        parsed[mask] = pd.to_datetime(s[mask], errors="coerce", format=fmt)
    return parsed


def parse_occurrence_hour(s):
    """
    Return (hour, time_unknown).
    Formats: 2000-2017 'HH:MM:SS', 2018-2021 'H:MM:SS' (not zero-padded), 2022 constant '01-JAN-00'
    (no time recorded). '00:01' is LAPD's placeholder for an unknown time. Unknown times get hour NaN.
    """
    s = s.astype(str).str.strip()
    parts = s.str.extract(r"^(\d{1,2}):(\d{2})")
    hh = pd.to_numeric(parts[0], errors="coerce")
    mm = pd.to_numeric(parts[1], errors="coerce")
    placeholder = (hh == 0) & (mm == 1)
    unknown = hh.isna() | ~hh.between(0, 23) | placeholder
    return hh.where(~unknown).astype("Int64"), unknown


# ── Loaders ──────────────────────────────────────────────────────────────────
_LOAD_COLS = ["data_year", "DR_NBR", "MODL_YR", "MKE_CD", "VEH_MODL_CD", "VEH_STYL_CD", "RPT_DIST_NBR",
              "CRME_OCCUR_DT", "CRME_OCCUR_TM", "CRME_CLSS_PRMRY_CD", "CRME_RPTD_DT",
              "LAT", "LON", "lat_final", "lon_final", "coord_source"]


def _cache_valid(path):
    return os.path.exists(path) and os.path.getmtime(path) > os.path.getmtime(PREPROCESSED) \
        and os.path.getmtime(path) > os.path.getmtime(__file__)


def _read_preprocessed():
    df = pd.read_csv(PREPROCESSED, usecols=_LOAD_COLS, dtype=str, low_memory=False)
    df["code"] = df["CRME_CLSS_PRMRY_CD"].str.strip()
    df["DR_NBR"] = df["DR_NBR"].str.strip()
    df["coord_source"] = df["coord_source"].fillna("unresolved")
    df["_prio"] = df["coord_source"].map(COORD_PRIORITY).fillna(9)
    return df


def _flag_in_city(lat, lon):
    """Boolean array: point inside the City of LA boundary (buffered by CITY_BUFFER_M). NaN coords -> False."""
    import geopandas as gpd
    ok = lat.notna() & lon.notna()
    inside = pd.Series(False, index=lat.index)
    city = gpd.read_file(CITY_BOUNDARY).to_crs(SPATIAL_CRS)
    poly = city.geometry.union_all().buffer(CITY_BUFFER_M * FT_PER_M)
    pts = gpd.GeoSeries(gpd.points_from_xy(lon[ok], lat[ok]), index=lat.index[ok], crs=LATLON_CRS).to_crs(SPATIAL_CRS)
    inside.loc[ok] = pts.within(poly).values
    return inside


def _assign_tract(lat, lon):
    """2020 tract GEOID for each point (NaN when no coordinates or outside LA County)."""
    import geopandas as gpd
    ok = lat.notna() & lon.notna()
    tracts = gpd.read_file(CENSUS_TRACTS)[["GEOID", "geometry"]].to_crs(SPATIAL_CRS)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon[ok], lat[ok]), index=lat.index[ok], crs=LATLON_CRS).to_crs(SPATIAL_CRS)
    j = gpd.sjoin(pts, tracts, how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return j["GEOID"].reindex(lat.index)


def _build_theft_table():
    df = _read_preprocessed()

    # Recovery linkage: a 510 report is "recovered" if a 521 row carries the same DR number.
    rec = df[df["code"] == RECOVERY_CODE].copy()
    rec["rec_dt"] = parse_occurrence_date(rec["CRME_OCCUR_DT"])
    rec = rec.groupby("DR_NBR")["rec_dt"].min()

    # One row per stolen-vehicle report: prefer the duplicate with the best coordinate source.
    th = df[df["code"] == THEFT_CODE].sort_values(["DR_NBR", "_prio"])
    n_rows = len(th)
    th = th.drop_duplicates("DR_NBR", keep="first").copy()
    th.attrs["n_rows_510"] = n_rows

    th["CRME_OCCUR_DT"] = parse_occurrence_date(th["CRME_OCCUR_DT"])
    th["CRME_RPTD_DT"] = parse_occurrence_date(th["CRME_RPTD_DT"])
    th["year"] = th["CRME_OCCUR_DT"].dt.year.astype("Int64")
    th = th[th["year"].between(STUDY_YEARS[0], STUDY_YEARS[-1])].copy()
    th["month"] = th["CRME_OCCUR_DT"].dt.month.astype("Int64")
    th["dow"] = th["CRME_OCCUR_DT"].dt.dayofweek.astype("Int64")
    th["hour"], th["time_unknown"] = parse_occurrence_hour(th["CRME_OCCUR_TM"])

    th["recovered"] = th["DR_NBR"].isin(rec.index)
    th["recovery_dt"] = th["DR_NBR"].map(rec)
    th["days_to_recovery"] = (th["recovery_dt"] - th["CRME_OCCUR_DT"]).dt.days
    th.loc[th["days_to_recovery"] < 0, "days_to_recovery"] = np.nan   # recovery dated before the theft: data error

    th["MODL_YR"] = pd.to_numeric(th["MODL_YR"], errors="coerce")
    th.loc[~th["MODL_YR"].between(MODL_YR_MIN, MODL_YR_MAX), "MODL_YR"] = np.nan
    th["modl_decade"] = pd.cut(th["MODL_YR"], bins=[1949, 1989, 1999, 2009, 2023],
                               labels=["pre-1990", "1990-1999", "2000-2009", "2010+"], right=True)
    for col in ["MKE_CD", "VEH_MODL_CD", "VEH_STYL_CD"]:
        th[col] = th[col].astype(str).str.strip().str.upper()
        th.loc[th[col].isin(["", "NAN", "NONE", "UNK", "UNKN"]), col] = np.nan

    # Coordinates: geocodes that fall outside the city cannot be LAPD incidents -> treat as unresolved.
    th["lat_final"] = pd.to_numeric(th["lat_final"], errors="coerce")
    th["lon_final"] = pd.to_numeric(th["lon_final"], errors="coerce")
    has = th["lat_final"].notna()
    th["in_city"] = _flag_in_city(th["lat_final"], th["lon_final"])
    outside = has & ~th["in_city"]
    th.loc[outside, "coord_source"] = "rejected_outside_city"
    th.loc[outside, ["lat_final", "lon_final"]] = np.nan
    th["GEOID"] = _assign_tract(th["lat_final"], th["lon_final"])

    keep = ["DR_NBR", "data_year", "year", "month", "dow", "hour", "time_unknown", "CRME_OCCUR_DT", "CRME_RPTD_DT",
            "CRME_OCCUR_TM", "RPT_DIST_NBR", "MKE_CD", "VEH_MODL_CD", "VEH_STYL_CD", "MODL_YR", "modl_decade",
            "recovered", "recovery_dt", "days_to_recovery", "lat_final", "lon_final", "coord_source", "GEOID"]
    th = th[keep].reset_index(drop=True)
    th.attrs["n_rows_510"] = n_rows
    return th


def load_theft_data(coords_required=False):
    """
    One row per stolen-vehicle report (crime class 510, deduplicated on DR_NBR), 2000-2022.

    Derived columns: year, month, dow, hour (NaN when time unknown), time_unknown, recovered (a 521 row
    shares the DR), days_to_recovery, modl_decade, GEOID (2020 tract), coord_source in
    {stored, census, nominatim, unresolved, rejected_outside_city}.

    coords_required : keep only reports with coordinates inside the City of Los Angeles.
    The table is cached in data/processed/thefts_510.pkl and rebuilt when the CSV or this file changes.
    """
    if _cache_valid(THEFT_CACHE):
        df = pd.read_pickle(THEFT_CACHE)
    else:
        df = _build_theft_table()
        df.to_pickle(THEFT_CACHE)
    if coords_required:
        df = df[df["lat_final"].notna()].copy()
    return df


def load_all_records():
    """
    All vehicle-related records, one row per (DR_NBR, crime class), with a 'segment' label from
    SEGMENT_CODES. Used for the dataset-composition table and figure only.
    """
    if _cache_valid(RECORDS_CACHE):
        return pd.read_pickle(RECORDS_CACHE)
    df = _read_preprocessed()
    n_rows = df.groupby("code").size()
    df = df.sort_values(["DR_NBR", "code", "_prio"]).drop_duplicates(["DR_NBR", "code"], keep="first").copy()
    code_to_seg = {c: seg for seg, codes in SEGMENT_CODES.items() for c in codes}
    df["segment"] = df["code"].map(code_to_seg).fillna("Other")
    df["CRME_OCCUR_DT"] = parse_occurrence_date(df["CRME_OCCUR_DT"])
    df["year"] = df["CRME_OCCUR_DT"].dt.year.astype("Int64")
    df["hour"], df["time_unknown"] = parse_occurrence_hour(df["CRME_OCCUR_TM"])
    df = df[["DR_NBR", "code", "segment", "data_year", "year", "hour", "time_unknown", "coord_source"]].reset_index(drop=True)
    df.attrs["rows_per_code"] = n_rows.to_dict()
    df.to_pickle(RECORDS_CACHE)
    return df
