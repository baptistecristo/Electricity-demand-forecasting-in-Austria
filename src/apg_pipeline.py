#!/usr/bin/env python3
"""
apg_pipeline.py — end-to-end reproduction of the result in README §8.

Everything from raw public downloads to the pre-registered regression. No API
token needed: APG publishes both load series as nested ZIPs with no registration,
and GeoSphere's station API needs no key.

    pip install pandas numpy requests statsmodels
    python src/apg_pipeline.py

Runtime is a few minutes, most of it the two ~6 MB APG downloads.

This reproduces the browser-side analysis that produced the numbers reported in
the README. The original run was executed in-page against the same endpoints
because the analysis sandbox had no route to these hosts; this script is the
portable equivalent and should give identical figures.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

CACHE = Path("cache"); CACHE.mkdir(exist_ok=True)

APG_ACTUAL   = "https://pb1-medien.apg.at/im/dl/apg-1191612034/Gesamtlast.zip"
APG_FORECAST = ("https://pb1-medien.apg.at/im/dl/apg-1333518940/"
                "Prognose%20%C3%BCber%20die%20Gesamtlast.zip")

GS = "https://dataset.api.hub.geosphere.at/v1"
REGION_WEIGHTS = {"Tirol": 0.50, "Salzburg": 0.24, "Vorarlberg": 0.10,
                  "Steiermark": 0.09, "Kärnten": 0.05}
ALT_MIN, ALT_MAX = 900, 2600
WB_THRESHOLD = -2.0
YEARS = range(2010, 2023)          # APG forecast archive coverage
NIGHT_HOURS = set(range(20, 24)) | set(range(0, 7))
MIN_NIGHT_HOURS = 8


# ---------------------------------------------------------------- APG load ---
def _download(url: str, name: str) -> bytes:
    f = CACHE / name
    if not f.exists():
        f.write_bytes(requests.get(url, timeout=600).content)
    return f.read_bytes()


def _apg_series(url: str, name: str, inner_pat: str) -> pd.Series:
    """Nested ZIP: outer archive holds one ZIP per year, each holding one CSV.

    CSV columns: 'Time from [CET/CEST]', 'Time to [CET/CEST]', value.
    Returned index is the wall-clock hour string 'YYYY-MM-DD HH' (local CET/CEST,
    matching how APG publishes). Both series use the same convention, so the join
    is consistent; DST-duplicated hours are averaged.
    """
    outer = zipfile.ZipFile(io.BytesIO(_download(url, name)))
    frames = []
    for member in outer.namelist():
        if not member.endswith("_English.zip"):
            continue
        if inner_pat not in member:
            continue
        year = int(member.split("_")[-2])
        if year not in YEARS:
            continue
        inner = zipfile.ZipFile(io.BytesIO(outer.read(member)))
        csv_name = next(n for n in inner.namelist() if n.lower().endswith(".csv"))
        df = pd.read_csv(io.BytesIO(inner.read(csv_name)))
        df.columns = ["t_from", "t_to", "value"]
        # APG writes the DST-repeated October hour as '2A' (02:00 CEST) and
        # '2B' (02:00 CET) instead of a numeric hour. Fold both onto '02' so the
        # groupby below averages them, as the docstring describes.
        df["hour"] = (df["t_from"].str.slice(0, 13)
                      .str.replace(r"^(\d{4}-\d{2}-\d{2}) 2[AB]$", r"\1 02",
                                   regex=True))
        frames.append(df.groupby("hour")["value"].mean())
    if not frames:
        raise RuntimeError(f"no members matched {inner_pat} in {name}")
    return pd.concat(frames).groupby(level=0).mean().sort_index()


def load_panel() -> pd.DataFrame:
    actual = _apg_series(APG_ACTUAL, "apg_actual.zip", "Ist-Last_M15_")
    fcst = _apg_series(APG_FORECAST, "apg_forecast.zip", "Lastprognose_M15_")
    df = pd.concat([actual.rename("actual"), fcst.rename("forecast")],
                   axis=1, join="inner").dropna()
    df["err"] = df["actual"] - df["forecast"]        # >0 = under-forecast
    ts = pd.to_datetime(df.index, format="%Y-%m-%d %H")
    df["Y"], df["M"], df["D"], df["H"] = ts.year, ts.month, ts.day, ts.hour
    return df


# ------------------------------------------------------------- wet bulb ------
def _es_water(t):
    """Saturation vapour pressure over water, hPa (WMO Magnus). Snowmakers'
    wet bulb uses a supercooled-water wick below 0 C, so stay over water."""
    return 6.112 * np.exp(17.62 * t / (243.12 + t))


def pressure_from_altitude(alt_m):
    """ISA pressure, hPa. At 1800 m this moves wet bulb 0.2-0.4 C versus a
    sea-level assumption, comparable to the RD bandwidth. Do not skip it."""
    return 1013.25 * (1 - 2.25577e-5 * np.asarray(alt_m, float)) ** 5.25588


def wet_bulb(t_c, rh_pct, p_hpa, iters: int = 50):
    """Bisection on es(Tw) - A*P*(T-Tw) - e = 0, A = 6.53e-4 (1 + 9.44e-4 Tw).
    Matches psychrometric tables to ~0.2 C; the Stull (2011) closed form errs
    ~0.7-1.0 C below freezing, which is worse than the effect being tested."""
    t = np.asarray(t_c, float)
    rh = np.clip(np.asarray(rh_pct, float), 1, 100)
    p = np.broadcast_to(np.asarray(p_hpa, float), t.shape).astype(float)
    e = rh / 100.0 * _es_water(t)
    lo, hi = np.full_like(t, -60.0), t.copy()
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        a = 6.53e-4 * (1 + 0.000944 * mid)
        f = _es_water(mid) - a * p * (t - mid) - e
        hi = np.where(f > 0, mid, hi)
        lo = np.where(f > 0, lo, mid)
    return 0.5 * (lo + hi)


def pick_stations(per_region: int = 4) -> pd.DataFrame:
    meta = requests.get(f"{GS}/station/historical/klima-v2-1h/metadata",
                        timeout=120).json()
    st = pd.DataFrame(meta["stations"])
    st["altitude"] = pd.to_numeric(st["altitude"], errors="coerce")
    st = st[st.altitude.between(ALT_MIN, ALT_MAX)]
    st = st[st.state.isin(REGION_WEIGHTS)]
    st = st[st.get("is_active", True) != False]                       # noqa: E712
    st = st[pd.to_datetime(st.valid_from, utc=True)
            <= pd.Timestamp("2009-01-01", tz="UTC")]
    st = (st.sort_values("altitude", ascending=False)
            .groupby("state", group_keys=False).head(per_region))
    # Some sites appear twice under different instrument ids; keep one so the
    # region weighting is not silently doubled for those sites.
    return st.drop_duplicates(subset="name")


def wetbulb_index(stations: pd.DataFrame) -> pd.Series:
    """Region-weighted alpine wet-bulb index, hourly, Oct-Dec of each year."""
    ids = ",".join(stations.id.astype(str))
    num, den = {}, {}
    for year in YEARS:
        # GeoSphere stamps everything UTC ('2015-12-01T00:00+00:00'); APG
        # publishes local CET/CEST wall clock. Joining the raw strings misaligns
        # the index by an hour (two under CEST), so convert first. The query
        # starts a day early because 1 Oct 00:00 local precedes 1 Oct 00:00 UTC.
        url = (f"{GS}/station/historical/klima-v2-1h?parameters=tl,rf"
               f"&start={year}-09-30T00:00&end={year}-12-31T23:00"
               f"&station_ids={ids}&output_format=geojson")
        g = requests.get(url, timeout=600).json()
        local = pd.DatetimeIndex(
            pd.to_datetime(g["timestamps"], utc=True)).tz_convert("Europe/Vienna")
        stamps = local.strftime("%Y-%m-%d %H")
        in_season = local.month.isin([10, 11, 12])
        for feat in g["features"]:
            props = feat["properties"]
            sid = str(props.get("station", props.get("id")))
            row = stations[stations.id.astype(str) == sid]
            if row.empty:
                continue
            w = REGION_WEIGHTS[row.state.iloc[0]]
            p = pressure_from_altitude(row.altitude.iloc[0])
            tl = np.array(props["parameters"]["tl"]["data"], dtype=float)
            rf = np.array(props["parameters"]["rf"]["data"], dtype=float)
            ok = np.isfinite(tl) & np.isfinite(rf)
            wb = np.full(tl.shape, np.nan)
            wb[ok] = wet_bulb(tl[ok], rf[ok], p)
            for s, v, keep in zip(stamps, wb, in_season):
                if keep and np.isfinite(v):
                    num[s] = num.get(s, 0.0) + v * w
                    den[s] = den.get(s, 0.0) + w
    idx = {k: num[k] / den[k] for k in num if den[k] > 0.5}
    return pd.Series(idx, name="wb").sort_index()


# ------------------------------------------------------------ night panel ----
def night_panel(load: pd.DataFrame, wb: pd.Series) -> pd.DataFrame:
    full = load.join(wb, how="inner")
    full = full[full.M.isin([10, 11, 12])].copy().sort_index()
    full["season"] = full["Y"]

    # cum_cold_h accumulates hours below threshold from 1 Oct, lagged so the
    # current hour never contributes to its own regressor. It runs over EVERY
    # hour of the season, not only night hours: the base a resort has already
    # built is the product of all the cold it has had, daytime included. Taking
    # the cumsum after the night filter would halve the running variable
    # (~497 h/season instead of ~1,011) and inflate every cum100 coefficient
    # and standard error by the same factor of ~2.05.
    below_h = (full["wb"] < WB_THRESHOLD).astype(int)
    full["cum_cold_h"] = (below_h.groupby(full["season"])
                          .transform(lambda s: s.shift(1).fillna(0).cumsum()))

    df = full[full.H.isin(NIGHT_HOURS)].copy()
    ts = pd.to_datetime(df.index, format="%Y-%m-%d %H")
    # A night runs 20:00-06:59 and is labelled by the date of its 20:00 hour.
    df["night_date"] = (ts - pd.Timedelta(hours=7)).date

    g = df.groupby("night_date")
    p = pd.DataFrame({
        "n_hours": g.size(),
        "err": g["err"].mean(),
        "wb": g["wb"].mean(),
        "cum_cold_h": g["cum_cold_h"].min(),
        "season": g["season"].first(),
    })
    p = p[p.n_hours >= MIN_NIGHT_HOURS].reset_index()
    d = pd.to_datetime(p.night_date)
    p["month"], p["doy"], p["dow"] = d.dt.month, d.dt.dayofyear, d.dt.dayofweek
    # Christmas industrial shutdown. Large, real, and must be controlled.
    p["holiday"] = ((p.month == 12) & (d.dt.day >= 21)).astype(int)
    p["below"] = (p.wb < WB_THRESHOLD).astype(int)
    p["dist"] = p.wb - WB_THRESHOLD

    # campaign start: first below-threshold night after >=2 nights above
    p = p.sort_values("night_date").reset_index(drop=True)
    starts = np.zeros(len(p), dtype=int)
    for _, idx in p.groupby("season").groups.items():
        a = p.loc[idx].sort_values("night_date")
        b = (a.wb < WB_THRESHOLD).to_numpy()
        for i in range(2, len(b)):
            if b[i] and not b[i - 1] and not b[i - 2]:
                starts[a.index[i]] = 1
    p["campaign_start"] = starts
    # campaign_night2: the night immediately after a start. Tested separately
    # because the highest-alpha scenario is the one where the forecast's
    # autoregressive terms have not yet caught up with a running campaign.
    night2 = np.zeros(len(p), dtype=int)
    for _, idx in p.groupby("season").groups.items():
        a = p.loc[idx].sort_values("night_date")
        cs = a.campaign_start.to_numpy()
        for i in range(1, len(cs)):
            if cs[i - 1] == 1:
                night2[a.index[i]] = 1
    p["campaign_night2"] = night2
    return p[p.month.isin([11, 12])].reset_index(drop=True)


# ------------------------------------------------------------- estimation ----
def estimate(p: pd.DataFrame, label: str, extra: str = "") -> None:
    import statsmodels.formula.api as smf
    d = p.copy()
    d["cum100"] = (d.cum_cold_h - d.cum_cold_h.median()) / 100.0
    d["doy_c"] = (d.doy - d.doy.mean()) / 10.0
    f = ("err ~ below * cum100 + dist + below:dist + holiday "
         "+ doy_c + I(doy_c**2) + C(season) + C(dow)" + extra)
    m = smf.ols(f, data=d).fit(cov_type="HC1")
    keep = [t for t in m.params.index
            if any(k in t for k in ("below", "cum100", "dist", "holiday",
                                    "campaign"))]
    print(f"\n=== {label}  (n={int(m.nobs)}) ===")
    print(m.summary2().tables[1].loc[keep][["Coef.", "Std.Err.", "z", "P>|z|"]]
          .round(2).to_string())


def descriptives(load: pd.DataFrame) -> None:
    """README 8.3: night-level forecast bias by month and in 10-day bins.

    Estimated at night level, so the standard errors count nights rather than
    the heavily autocorrelated hours inside them.
    """
    d = load[load.H.isin(NIGHT_HOURS)].copy()
    ts = pd.to_datetime(d.index, format="%Y-%m-%d %H")
    d["night_date"] = (ts - pd.Timedelta(hours=7)).date
    g = d.groupby("night_date")
    n = pd.DataFrame({"err": g["err"].mean(), "n_hours": g.size()})
    n = n[n.n_hours >= MIN_NIGHT_HOURS].reset_index()
    dt = pd.to_datetime(n.night_date)
    n["month"], n["day"] = dt.dt.month, dt.dt.day

    print("\n8.3 — night bias by month (MW, +- s.e.)")
    m = n.groupby("month")["err"].agg(["mean", "sem"]).round(1)
    print("  " + "  ".join(f"{i:02d}:{r['mean']:+.0f}+-{r['sem']:.0f}"
                           for i, r in m.iterrows()))

    print("8.3 — Nov 1 - Dec 30 in 10-day bins (Dec 31 excluded)")
    b = n[(n.month.isin([11, 12])) & (n.day <= 30)].copy()
    b["bin"] = b.month.map({11: "Nov", 12: "Dec"}) + " " + pd.cut(
        b.day, [0, 10, 20, 30], labels=["1-10", "11-20", "21-30"]).astype(str)
    order = [f"{mo} {d}" for mo in ("Nov", "Dec")
             for d in ("1-10", "11-20", "21-30")]
    r = b.groupby("bin")["err"].agg(["mean", "sem", "count"]).reindex(order)
    print(r.round(1).to_string())


def main() -> None:
    print("downloading APG load series ...")
    load = load_panel()
    print(f"  hourly observations: {len(load):,}  "
          f"{load.index.min()} .. {load.index.max()}")

    # The gate uses the same 20:00-06:59 night as the estimation sample.
    night_all = load[load.H.isin(NIGHT_HOURS) & load.M.isin([11, 12])].copy()
    mae = night_all.err.abs().mean()
    print(f"\nGATE — Nov-Dec night hours, day-ahead forecast error")
    print(f"  mean load : {night_all.actual.mean():,.0f} MW")
    print(f"  bias      : {night_all.err.mean():+,.1f} MW")
    print(f"  sd        : {night_all.err.std():,.1f} MW")
    print(f"  MAE       : {mae:,.1f} MW "
          f"({100*mae/night_all.actual.mean():.2f}% of load)")

    # sd after hour/dow/season fixed effects, and the alpha pass mark it
    # implies through the detectability formula in src/power.py.
    import statsmodels.formula.api as smf
    night_all["dow"] = pd.to_datetime(night_all.index,
                                      format="%Y-%m-%d %H").dayofweek
    sd_fe = smf.ols("err ~ C(H) + C(dow) + C(Y)", data=night_all).fit().resid.std()
    n_ep = 13 * 9                                   # seasons x episodes/season
    alpha = (2.80 * sd_fe * np.sqrt(0.7 + 0.3 / 8)
             * np.sqrt(2 / (n_ep * 0.5)) / 900)
    print(f"  sd after hour/dow/season FE : {sd_fe:,.1f} MW")
    print(f"  implied alpha pass mark, 13 seasons : {alpha:.1%}")

    descriptives(load)

    print("\nselecting alpine stations ...")
    stations = pick_stations()
    print(stations[["id", "name", "state", "altitude"]].to_string(index=False))

    print("\nbuilding wet-bulb index ...")
    wb = wetbulb_index(stations)
    print(f"  hours: {len(wb):,}   share below {WB_THRESHOLD} C: "
          f"{100*(wb < WB_THRESHOLD).mean():.1f}%")

    p = night_panel(load, wb)
    print(f"\nnight panel: {len(p)} nights across {p.season.nunique()} seasons, "
          f"{int(p.campaign_start.sum())} campaign starts")
    p.to_csv("data/night_panel.csv", index=False)

    estimate(p, "PRIMARY — Nov-Dec, all nights")
    estimate(p[p.dist.abs() <= 3], "Bandwidth |wb+2| <= 3 C")
    estimate(p, "With campaign-start dummy", extra=" + campaign_start")
    estimate(p[p.season >= 2016], "Seasons 2016-2022 only")
    estimate(p, "Campaign start + second night",
             extra=" + campaign_start + campaign_night2")


if __name__ == "__main__":
    main()
