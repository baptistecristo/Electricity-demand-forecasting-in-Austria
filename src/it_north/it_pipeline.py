#!/usr/bin/env python3
"""
it_pipeline.py - Italy-North replication of the Austrian snowmaking / day-ahead
load-forecast test in src/apg_pipeline.py.

Same question, same specification, same estimator, different system. Austria
came back a clean null. Italy-North ranks ~45 on snowmaking GWh per GW of winter
overnight load (Austria = 43), so it is the one system that plausibly beats
Austria on statistical power and is a fair replication rather than a fishing
expedition.

Everything from raw public downloads to the pre-registered regression. No API
token needed: Terna's Download Center serves CSV over an unauthenticated
endpoint, and the Autonomous Province of Bolzano / South Tyrol open-data weather
API needs no key.

    pip install pandas numpy requests statsmodels
    python src/it_north/it_pipeline.py

Runtime is roughly 10-20 minutes on a cold cache, almost all of it the
station-by-station weather pulls. Everything is cached, so a second run is fast.

READ THE README IN THIS DIRECTORY BEFORE READING THE NUMBERS. The pre-specified
sanity gate (a strongly negative `holiday` coefficient, the Christmas industrial
shutdown showing up in the forecast error) DOES NOT FIRE for Italy-North. It
does not fire because Terna's day-ahead forecast anticipates the shutdown almost
perfectly, not because the pipeline is broken; `shutdown_diagnostic()` below
prints the evidence for that claim. The consequence is that the Austrian
design's sensitivity certificate has no analogue here, so the primary
coefficient is reported WITHOUT a power warranty.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# --------------------------------------------------------------- paths -------
# Scratch/cache lives outside the repo; only the deliverables land next to this
# file. Nothing here writes to the Austrian run's cache/ or data/ directories.
CACHE = Path(r"C:\Users\bcris\.claude-snow\jobs\11224758\tmp\it_cache")
CACHE.mkdir(parents=True, exist_ok=True)
OUT = Path(__file__).resolve().parent

UA = {"User-Agent": "Mozilla/5.0 (research replication; contact: repo owner)"}

# ------------------------------------------------------------- constants -----
# Terna Download Center. The Vue front-end at https://dati.terna.it/en/download-center
# builds exactly this GET; f=csv is undocumented but served. filterDay is
# accepted and ignored, so we page a whole month at a time.
TERNA = "https://dati.terna.it/api/sitecore/dati/downloadcenter/records"
TERNA_PAGESIZE = 1048573          # the front-end's own maxPageSize

# Autonomous Province of Bolzano / South Tyrol open weather data.
BZ = "https://daten.buergernetz.bz.it/services/meteo/v1"

# Austria weighted five federal states by share of ski volume. Only one Italian
# alpine weather authority served open historical hourly temperature AND
# relative humidity (see README §"Weather sources tried"), so the index rests on
# a single region at weight 1.0. The num/den weighting machinery below is kept
# structurally intact so a second region can be dropped in unchanged.
REGION_WEIGHTS = {"Bolzano/South Tyrol": 1.00}

ALT_MIN, ALT_MAX = 900, 2600      # where snow is actually made; unchanged
WB_THRESHOLD = -2.0               # wet-bulb snowmaking threshold; unchanged
YEARS = range(2019, 2026)         # Terna zonal Total Load archive coverage
NIGHT_HOURS = set(range(20, 24)) | set(range(0, 7))
MIN_NIGHT_HOURS = 8
N_STATIONS = 4                    # apg's per_region=4, one region here
N_STATIONS_ROBUST = 20            # README robustness pass, ~= Austria's count


# ------------------------------------------------------------- Terna load ----
def _terna_month(year: int, month: int) -> str:
    """One month of 15-minute IT-North Total Load, actual and forecast."""
    f = CACHE / f"TotalLoad_North_{year}_{month:02d}.csv"
    if not f.exists():
        url = (f"{TERNA}?f=csv&filterDataset=TotalLoad&filterBiddingZone=North"
               f"&filterYear={year}&filterMonth={month}"
               f"&orderByColumn=Date&orderByDir=asc&db=dati"
               f"&pageSize={TERNA_PAGESIZE}")
        f.write_bytes(requests.get(url, headers=UA, timeout=600).content)
        time.sleep(0.4)
    return f.read_text(encoding="utf-8", errors="replace")


def load_panel() -> pd.DataFrame:
    """Hourly IT-North load panel, October-December of each season.

    Terna's f=csv export writes Italian decimal commas INTO a comma-separated
    file, so `17003,081000` is one number, not two fields. read_csv cannot see
    that. Parse positionally instead and assert the field count, so a format
    change fails loudly rather than silently halving every load value:

        Date, actual_int, actual_frac, forecast_int, forecast_frac, zone, ''

    Timestamps are local Europe/Rome wall clock, verified: October has 2,980
    quarter-hours (the 02:00 hour appears twice) and March has 2,972 (it is
    missing), which only happens on a local clock. That is the same convention
    APG publishes on, so the hour-string groupby below folds the DST-repeated
    hour by averaging it, exactly as apg_pipeline does.
    """
    rows = []
    for year in YEARS:
        for month in (10, 11, 12):
            text = _terna_month(year, month)
            lines = [l for l in text.strip().split("\n") if l.strip()]
            if len(lines) <= 1:
                raise RuntimeError(f"Terna returned no rows for {year}-{month}")
            for line in lines[1:]:
                parts = line.rstrip(",").split(",")
                if len(parts) != 6:
                    raise RuntimeError(
                        f"unexpected Terna CSV layout ({len(parts)} fields) "
                        f"in {year}-{month}: {line!r}")
                rows.append((parts[0][:13].replace("T", " "),
                             float(parts[1] + "." + parts[2]),
                             float(parts[3] + "." + parts[4])))

    df = pd.DataFrame(rows, columns=["hour", "actual", "forecast"])
    df = df.groupby("hour")[["actual", "forecast"]].mean().sort_index()
    df["err"] = df["actual"] - df["forecast"]        # >0 = under-forecast
    ts = pd.to_datetime(df.index, format="%Y-%m-%d %H")
    df["Y"], df["M"], df["D"], df["H"] = ts.year, ts.month, ts.day, ts.hour
    return df


# ------------------------------------------------------------- wet bulb ------
# Verbatim from src/apg_pipeline.py. Do not substitute a closed form.
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


# ----------------------------------------------------------- BZ weather ------
def _bz_json(name: str, url: str):
    f = CACHE / name
    if not f.exists():
        f.write_bytes(requests.get(url, headers=UA, timeout=300).content)
        time.sleep(0.2)
    return json.loads(f.read_text(encoding="utf-8", errors="replace"))


def bz_series(station: str, sensor: str, year: int) -> pd.Series:
    """One station-sensor-season of 10-minute readings, keyed by local hour.

    South Tyrol stamps local time with an explicit CEST/CET suffix
    ('2019-10-01T00:00:00CEST'). Slicing to 'YYYY-MM-DD HH' therefore lands on
    the same local wall-clock key Terna publishes on, and the DST-repeated
    October hour is folded by averaging on both sides of the join. Consistent by
    construction, unlike the GeoSphere/APG pair which needed a UTC conversion.
    """
    f = CACHE / f"bz_{station}_{sensor}_{year}.json"
    if not f.exists():
        url = (f"{BZ}/timeseries?station_code={station}&output_format=JSON"
               f"&sensor_code={sensor}"
               f"&date_from={year}10010000&date_to={year + 1}01010000")
        f.write_bytes(requests.get(url, headers=UA, timeout=300).content)
        time.sleep(0.1)
    try:
        data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return pd.Series(dtype=float)
    if not data:
        return pd.Series(dtype=float)
    d = pd.DataFrame(data)
    hour = d["DATE"].str.slice(0, 13).str.replace("T", " ", regex=False)
    v = pd.to_numeric(d["VALUE"], errors="coerce")
    return v.groupby(hour).mean().dropna()


def pick_stations(n: int = N_STATIONS) -> pd.DataFrame:
    """Highest stations in the 900-2600 m band carrying both air temperature
    (LT) and relative humidity (LF), and reporting from the start of the sample.

    Mirrors apg_pipeline.pick_stations: altitude band, highest-first, drop
    duplicate site names, and require the station to predate the sample -- APG's
    `valid_from <= 2009` becomes 'has October 2019 data' here, since the South
    Tyrol API exposes no commissioning date.

    Valley stations are excluded for the same reason as in Austria: they cross
    the wet-bulb threshold hundreds of hours later than the altitudes where snow
    is actually made, and would manufacture a null.
    """
    st = _bz_json("bz_stations.json", f"{BZ}/stations")
    sen = _bz_json("bz_sensors.json", f"{BZ}/sensors")

    have: dict[str, set[str]] = {}
    for s in sen:
        have.setdefault(s["SCODE"], set()).add(s["TYPE"])

    cand = [f["properties"] for f in st["features"]]
    cand = [p for p in cand if p.get("ALT") and ALT_MIN <= p["ALT"] <= ALT_MAX]
    cand = [p for p in cand if {"LT", "LF"} <= have.get(p["SCODE"], set())]
    cand.sort(key=lambda p: -p["ALT"])

    picked, seen = [], set()
    for p in cand:
        if p["NAME_I"] in seen:
            continue
        # cheap probe: does this station report T and RH at the sample start?
        first = YEARS[0] if isinstance(YEARS, list) else min(YEARS)
        if bz_series(p["SCODE"], "LT", first).empty:
            continue
        if bz_series(p["SCODE"], "LF", first).empty:
            continue
        seen.add(p["NAME_I"])
        picked.append(p)
        if len(picked) >= n:
            break

    out = pd.DataFrame(picked)
    out = out.rename(columns={"SCODE": "id", "NAME_I": "name", "ALT": "altitude"})
    out["state"] = "Bolzano/South Tyrol"
    return out[["id", "name", "state", "altitude", "LAT", "LONG"]]


def wetbulb_index(stations: pd.DataFrame) -> pd.Series:
    """Region-weighted alpine wet-bulb index, hourly, Oct-Dec of each season.

    10-minute readings are averaged to the hour first, then wet_bulb() is
    evaluated on the hourly means -- one bisection per station-hour rather than
    per raw reading, which is both faster and what the Austrian run did with
    GeoSphere's natively hourly klima-v2-1h series.
    """
    num, den = {}, {}
    for _, row in stations.iterrows():
        w = REGION_WEIGHTS[row.state]
        p = pressure_from_altitude(row.altitude)
        for year in YEARS:
            tl = bz_series(row.id, "LT", year)
            rf = bz_series(row.id, "LF", year)
            both = tl.index.intersection(rf.index)
            if len(both) == 0:
                continue
            t = tl.loc[both].to_numpy(float)
            r = rf.loc[both].to_numpy(float)
            ok = np.isfinite(t) & np.isfinite(r)
            if not ok.any():
                continue
            wb = np.full(t.shape, np.nan)
            wb[ok] = wet_bulb(t[ok], r[ok], p)
            for s, v in zip(both, wb):
                # keep Oct-Dec only; the API window can bleed one hour into Jan
                if s[5:7] not in ("10", "11", "12"):
                    continue
                if np.isfinite(v):
                    num[s] = num.get(s, 0.0) + v * w
                    den[s] = den.get(s, 0.0) + w
    idx = {k: num[k] / den[k] for k in num if den[k] > 0.5}
    return pd.Series(idx, name="wb").sort_index()


# ------------------------------------------------------------ night panel ----
# Verbatim from src/apg_pipeline.py.
def night_panel(load: pd.DataFrame, wb: pd.Series) -> pd.DataFrame:
    full = load.join(wb, how="inner")
    full = full[full.M.isin([10, 11, 12])].copy().sort_index()
    full["season"] = full["Y"]

    # cum_cold_h accumulates hours below threshold from 1 Oct, lagged so the
    # current hour never contributes to its own regressor. It runs over EVERY
    # hour of the season, not only night hours: the base a resort has already
    # built is the product of all the cold it has had, daytime included.
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
    # campaign_night2: the night immediately after a start.
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
    """Night-level forecast bias by month and in 10-day bins.

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

    print("\n8.3 - night bias by month (MW, +- s.e.)")
    m = n.groupby("month")["err"].agg(["mean", "sem"]).round(1)
    print("  " + "  ".join(f"{i:02d}:{r['mean']:+.0f}+-{r['sem']:.0f}"
                           for i, r in m.iterrows()))

    print("8.3 - Nov 1 - Dec 30 in 10-day bins (Dec 31 excluded)")
    b = n[(n.month.isin([11, 12])) & (n.day <= 30)].copy()
    b["bin"] = b.month.map({11: "Nov", 12: "Dec"}) + " " + pd.cut(
        b.day, [0, 10, 20, 30], labels=["1-10", "11-20", "21-30"]).astype(str)
    order = [f"{mo} {d}" for mo in ("Nov", "Dec")
             for d in ("1-10", "11-20", "21-30")]
    r = b.groupby("bin")["err"].agg(["mean", "sem", "count"]).reindex(order)
    print(r.round(1).to_string())


def shutdown_diagnostic(load: pd.DataFrame) -> None:
    """Proof that a weak `holiday` coefficient is not a broken pipeline.

    The pre-specified sanity gate assumes the day-ahead forecaster MISSES the
    Christmas industrial shutdown, which is what APG does. If the gate comes
    back near zero there are two candidate explanations: the pipeline is broken,
    or the forecaster simply is not missing it. Those are separable. A broken
    pipeline (timezone shift, sign flip, decimal-comma corruption) destroys the
    forecast's tracking of the shutdown. A competent forecaster preserves it.

    So print the shutdown as it appears in ACTUAL load and, separately, as it
    appears in the FORECAST. If both show the same multi-GW drop, the data are
    intact and the gate's premise is what failed.
    """
    dec = load[load.M == 12].copy()
    ts = pd.to_datetime(dec.index, format="%Y-%m-%d %H")
    dec["day"] = ts.day
    print("\nGATE DIAGNOSTIC - is a weak `holiday` coefficient breakage?")
    print("  Christmas shutdown, Dec 21-31 minus Dec 1-20 (MW)")
    print(f"  {'window':<14}{'in ACTUAL':>12}{'in FORECAST':>14}"
          f"{'left in error':>15}")
    for lbl, hours in [("night 20-06", NIGHT_HOURS),
                       ("day 09-17", set(range(9, 18))),
                       ("all hours", set(range(0, 24)))]:
        s = dec[dec.H.isin(hours)]
        a, b = s[s.day <= 20], s[s.day >= 21]
        da = b.actual.mean() - a.actual.mean()
        df_ = b.forecast.mean() - a.forecast.mean()
        print(f"  {lbl:<14}{da:>+12,.0f}{df_:>+14,.0f}{da - df_:>+15,.0f}")
    print("  A pipeline fault cannot preserve the forecast column's tracking")
    print("  of a multi-GW calendar event. If ACTUAL ~ FORECAST here, the data")
    print("  are intact and it is the gate's premise that fails.")

    print("\n  per season, night hours (MW):")
    print(f"  {'season':<9}{'actual drop':>13}{'forecast drop':>15}"
          f"{'residual':>11}")
    for y, g in dec[dec.H.isin(NIGHT_HOURS)].groupby("Y"):
        a, b = g[g.day <= 20], g[g.day >= 21]
        da = b.actual.mean() - a.actual.mean()
        df_ = b.forecast.mean() - a.forecast.mean()
        print(f"  {y:<9}{da:>+13,.0f}{df_:>+15,.0f}{da - df_:>+11,.0f}")


def main() -> None:
    print("downloading Terna IT-North Total Load (actual + day-ahead forecast) ...")
    load = load_panel()
    print(f"  hourly observations: {len(load):,}  "
          f"{load.index.min()} .. {load.index.max()}")

    # The gate uses the same 20:00-06:59 night as the estimation sample.
    night_all = load[load.H.isin(NIGHT_HOURS) & load.M.isin([11, 12])].copy()
    mae = night_all.err.abs().mean()
    print("\nGATE - Nov-Dec night hours, day-ahead forecast error")
    print(f"  mean load : {night_all.actual.mean():,.0f} MW")
    print(f"  bias      : {night_all.err.mean():+,.1f} MW")
    print(f"  sd        : {night_all.err.std():,.1f} MW")
    print(f"  MAE       : {mae:,.1f} MW "
          f"({100 * mae / night_all.actual.mean():.2f}% of load)")

    # sd after hour/dow/season fixed effects, and the alpha pass mark it
    # implies through the detectability formula in src/power.py.
    import statsmodels.formula.api as smf
    night_all["dow"] = pd.to_datetime(night_all.index,
                                      format="%Y-%m-%d %H").dayofweek
    sd_fe = smf.ols("err ~ C(H) + C(dow) + C(Y)",
                    data=night_all).fit().resid.std()
    n_ep = len(list(YEARS)) * 9                 # seasons x episodes/season
    # Austria divided by 900 MW, its central coincident snowmaking draw. Italy's
    # snowmaking fleet is larger in absolute terms; 900 is kept so the printed
    # pass mark is directly comparable to the Austrian run's, and the README
    # states this explicitly.
    alpha = (2.80 * sd_fe * np.sqrt(0.7 + 0.3 / 8)
             * np.sqrt(2 / (n_ep * 0.5)) / 900)
    print(f"  sd after hour/dow/season FE : {sd_fe:,.1f} MW")
    print(f"  implied alpha pass mark, {len(list(YEARS))} seasons : {alpha:.1%}")

    descriptives(load)
    shutdown_diagnostic(load)

    print("\nselecting alpine stations (South Tyrol, 900-2600 m) ...")
    stations = pick_stations()
    print(stations[["id", "name", "state", "altitude"]].to_string(index=False))

    print("\nbuilding wet-bulb index ...")
    wb = wetbulb_index(stations)
    print(f"  hours: {len(wb):,}   share below {WB_THRESHOLD} C: "
          f"{100 * (wb < WB_THRESHOLD).mean():.1f}%")

    p = night_panel(load, wb)
    print(f"\nnight panel: {len(p)} nights across {p.season.nunique()} seasons, "
          f"{int(p.campaign_start.sum())} campaign starts")
    print(f"  cum_cold_h at season end (median across seasons): "
          f"{p.groupby('season').cum_cold_h.max().median():.0f} h")
    p.to_csv(OUT / "night_panel_it.csv", index=False)

    estimate(p, "PRIMARY - Nov-Dec, all nights")
    estimate(p[p.dist.abs() <= 3], "Bandwidth |wb+2| <= 3 C")
    estimate(p, "With campaign-start dummy", extra=" + campaign_start")
    # Austria's "seasons 2016-2022 only" late-half cut has no Italian analogue
    # (the archive starts in 2019). Seasons >= 2022 is the closest equivalent:
    # the later half of the available sample.
    estimate(p[p.season >= 2022], "Seasons 2022-2025 only (late-half analogue)")
    estimate(p, "Campaign start + second night",
             extra=" + campaign_start + campaign_night2")

    # Robustness: Austria's five-region selection produced ~20 stations. One
    # Italian region at per_region=4 produces 4. Re-run the primary on a
    # 20-station index so the README can say whether that thinning matters.
    print("\n" + "=" * 70)
    print(f"ROBUSTNESS - wet-bulb index from {N_STATIONS_ROBUST} stations "
          f"instead of {N_STATIONS}")
    print("=" * 70)
    st20 = pick_stations(N_STATIONS_ROBUST)
    print(f"  stations: {len(st20)}  altitude "
          f"{st20.altitude.min():.0f}-{st20.altitude.max():.0f} m")
    wb20 = wetbulb_index(st20)
    print(f"  hours: {len(wb20):,}   share below {WB_THRESHOLD} C: "
          f"{100 * (wb20 < WB_THRESHOLD).mean():.1f}%")
    p20 = night_panel(load, wb20)
    print(f"  night panel: {len(p20)} nights, "
          f"{int(p20.campaign_start.sum())} campaign starts")
    p20.to_csv(OUT / "night_panel_it_20stations.csv", index=False)
    estimate(p20, f"PRIMARY, {N_STATIONS_ROBUST}-station index")


if __name__ == "__main__":
    main()
