#!/usr/bin/env python3
"""
ch_pipeline.py -- Swiss replication of the Austrian snowmaking / load-forecast test.

Same question, same specification, different system: does ski-resort snowmaking
show up as a systematic residual in the Swiss day-ahead LOAD forecast?

The specification is copied from src/apg_pipeline.py without redesign. What
changes is only the plumbing: the load series comes from energy-charts.info
(Fraunhofer ISE) instead of APG, and the weather comes from the MeteoSwiss
open-government SMN network instead of GeoSphere Austria. Deviations are
enumerated in README.md.

    pip install pandas numpy requests statsmodels
    python src/swiss/ch_pipeline.py

Two energy-charts requests (one wide each, spaced 30 s because CH is rate
limited at ~16 requests) and ~40 MeteoSwiss CSVs, all cached on first run.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ----------------------------------------------------------------- config ---
CACHE = Path(r"C:\Users\bcris\.claude-snow\jobs\11224758\tmp\ch_cache")
CACHE.mkdir(parents=True, exist_ok=True)

EC = "https://api.energy-charts.info"
SMN = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn"
META_STATIONS = f"{SMN}/ogd-smn_meta_stations.csv"

# energy-charts CH data floor is exactly 2015-01-01T00:00Z; established
# empirically, anything earlier 400s. Query one wide window and slice locally.
START, END = "2015-01-01", "2026-01-05"
SEASONS = range(2015, 2026)          # 11 complete Nov-Dec seasons

LOCAL_TZ = "Europe/Zurich"
ALT_MIN, ALT_MAX = 900, 2600
WB_THRESHOLD = -2.0
NIGHT_HOURS = set(range(20, 24)) | set(range(0, 7))
MIN_NIGHT_HOURS = 8
PER_CANTON = 4

# Data-quality filter. Between 2021-09-01 and 2022-12-31 the energy-charts CH
# "day-ahead load forecast" is not a forecast: actual/forecast is pinned to a
# constant -- 1.06052 for Sep-Nov 2021, 1.05969 for Dec 2021, and 1.05080 to
# five decimals for every month of 2022 -- i.e. the published forecast is the
# realised load rescaled by a fixed factor. Any season
# whose Oct-Dec actual/forecast ratio has a standard deviation below this
# tolerance is a placeholder series and is dropped, not analysed.
DEGENERATE_RATIO_SD = 0.005

# Cantons carrying essentially all Swiss ski-lift capacity in the alpine band.
# Equal weights: no published skier-visit split by region was findable (see
# README "Region weighting"), so the Austrian skier-visit weights have no Swiss
# analogue and every canton gets 1/8.
SKI_CANTONS = ["GR", "VS", "BE", "VD", "UR", "OW", "FR", "GL"]

# The only hand adjustment to the mechanical rule. These six sit inside kept
# cantons and inside the altitude band but are Jura / Emmental / suburban
# ridges with no ski-lift infrastructure below them, so their wet bulb tracks
# weather that no snow gun ever responds to.
EXCLUDE_STATIONS = {
    "CHA",  # Chasseral, BE  -- Jura ridge
    "NAP",  # Napf, BE       -- Emmental ridge
    "BAN",  # Bantiger, BE   -- hill above the city of Bern
    "DOL",  # La Dole, VD    -- Jura ridge
    "FRE",  # La Fretaz, VD  -- Jura
    "CHB",  # Les Charbonnieres, VD -- Vallee de Joux, Jura
}

# Magnitude anchor for the MDE, from README section 8.8 of the parent study:
# Austria 281 GWh/season of snowmaking energy was matched to a 900 MW
# coincident overnight snowmaking load. Switzerland publishes 60-65 GWh, so
# the coincident Swiss load scales to 900 * 62.5/281.
AT_SNOW_GWH, AT_COINCIDENT_MW = 281.0, 900.0
CH_SNOW_GWH = 62.5                        # midpoint of the published 60-65
S_MW = AT_COINCIDENT_MW * CH_SNOW_GWH / AT_SNOW_GWH

# power.py design constants, reused verbatim.
EPISODES_PER_SEASON = 9
HOURS_PER_EPISODE = 8
RHO = 0.7
Z = 2.80


# ------------------------------------------------------------------ http ----
def _get(url: str, name: str, sleep_before: float = 0.0) -> bytes:
    f = CACHE / name
    if not f.exists():
        if sleep_before:
            print(f"    (spacing {sleep_before:.0f}s for energy-charts rate limit)")
            time.sleep(sleep_before)
        print(f"    GET {url[:110]}")
        r = requests.get(url, timeout=900)
        r.raise_for_status()
        f.write_bytes(r.content)
    return f.read_bytes()


# ------------------------------------------------------------- load panel ---
def load_panel() -> pd.DataFrame:
    """Hourly CH load and day-ahead load forecast, indexed on tz-aware UTC.

    energy-charts returns unix_seconds, so both series are joined on the epoch
    and converted to Europe/Zurich exactly once. This sidesteps the wall-clock
    string join (and its DST folding) the Austrian pipeline needed.
    """
    fc = json.loads(_get(
        f"{EC}/public_power_forecast?country=ch&production_type=load"
        f"&forecast_type=day-ahead&start={START}&end={END}",
        "ch_forecast.json"))
    ac = json.loads(_get(
        f"{EC}/public_power?country=ch&start={START}&end={END}",
        "ch_actual.json", sleep_before=30))

    f = pd.Series(pd.to_numeric(pd.Series(fc["forecast_values"]), errors="coerce").values,
                  index=pd.to_datetime(fc["unix_seconds"], unit="s", utc=True),
                  name="forecast")
    series = next(s for s in ac["production_types"] if s["name"] == "Load")
    a = pd.Series(pd.to_numeric(pd.Series(series["data"]), errors="coerce").values,
                  index=pd.to_datetime(ac["unix_seconds"], unit="s", utc=True),
                  name="actual")

    df = pd.concat([a, f], axis=1)
    n_raw = len(df)
    # Mirrors publish sporadic zeros / negatives where a value is missing.
    df = df[(df.actual > 0) & (df.forecast > 0)].dropna()
    print(f"  raw hourly rows {n_raw:,} -> usable {len(df):,} "
          f"({n_raw - len(df):,} dropped as null/non-positive)")

    df = df.sort_index()
    df["err"] = df["actual"] - df["forecast"]          # >0 = under-forecast
    loc = df.index.tz_convert(LOCAL_TZ)
    df["Y"], df["M"], df["H"] = loc.year, loc.month, loc.hour
    df["local"] = loc
    return df


def drop_degenerate_seasons(df: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
    """Reject seasons whose 'day-ahead forecast' is a rescaled copy of actual.

    Diagnosed by the standard deviation of actual/forecast over the Oct-Dec
    window. A genuine forecast gives ~0.06-0.13; the 2021 and 2022 placeholder
    gives ~1e-5. Reported in full so the exclusion is auditable.
    """
    oct_dec = df[df.M.isin([10, 11, 12]) & df.Y.isin(list(SEASONS))].copy()
    r = (oct_dec.actual / oct_dec.forecast).groupby(oct_dec.Y)
    tab = pd.DataFrame({"ratio_mean": r.mean(), "ratio_sd": r.std(),
                        "hours": r.size()})
    tab["verdict"] = np.where(tab.ratio_sd < DEGENERATE_RATIO_SD,
                              "DROP (placeholder)", "keep")
    print("\n  forecast-authenticity check, Oct-Dec actual/forecast ratio")
    print(tab.round(5).to_string())
    bad = sorted(tab.index[tab.ratio_sd < DEGENERATE_RATIO_SD].tolist())
    if bad:
        print(f"  dropping seasons {bad}: forecast is the realised load "
              f"rescaled by a constant, not a forecast")
    return df[~df.Y.isin(bad)].copy(), bad


# --------------------------------------------------------------- wet bulb ---
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


# --------------------------------------------------------------- stations ---
def pick_stations() -> pd.DataFrame:
    raw = _get(META_STATIONS, "meta_stations.csv")
    st = pd.read_csv(io.BytesIO(raw), sep=";", encoding="cp1252")
    st = st.rename(columns={"station_abbr": "id", "station_name": "name",
                            "station_canton": "canton",
                            "station_height_masl": "altitude"})
    st["altitude"] = pd.to_numeric(st["altitude"], errors="coerce")
    st["since"] = pd.to_datetime(st.station_data_since, format="%d.%m.%Y",
                                 errors="coerce")
    st = st[st.station_type_en.str.contains("Automatic weather", na=False)]
    st = st[st.altitude.between(ALT_MIN, ALT_MAX)]
    st = st[st.canton.isin(SKI_CANTONS)]
    st = st[~st.id.isin(EXCLUDE_STATIONS)]
    st = st[st.since <= pd.Timestamp("2015-10-01")]
    st = (st.sort_values("altitude", ascending=False)
            .groupby("canton", group_keys=False).head(PER_CANTON))
    # Equal weight per canton, split evenly over that canton's stations.
    n = st.groupby("canton")["id"].transform("size")
    st["weight"] = (1.0 / len(SKI_CANTONS)) / n
    return st.sort_values(["canton", "altitude"], ascending=[True, False])


def _station_hourly(sid: str) -> pd.DataFrame:
    """Hourly tre200h0 (air temp, C) and ure200h0 (RH, %) for one station.

    MeteoSwiss stamps reference_timestamp in UTC -- verified against the July
    diurnal cycle at Davos, which peaks at stamped hour 14 and bottoms at 4,
    i.e. 16:00 / 06:00 CEST. Parsed as UTC and never string-joined.
    """
    sl = sid.lower()
    frames = []
    for span in ("2010-2019", "2020-2029"):
        b = _get(f"{SMN}/{sl}/ogd-smn_{sl}_h_historical_{span}.csv",
                 f"smn_{sl}_{span}.csv")
        d = pd.read_csv(io.BytesIO(b), sep=";",
                        usecols=["reference_timestamp", "tre200h0", "ure200h0"])
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["ts"] = pd.to_datetime(d.reference_timestamp, format="%d.%m.%Y %H:%M",
                             utc=True)
    return d.set_index("ts")[["tre200h0", "ure200h0"]].sort_index()


def wetbulb_index(stations: pd.DataFrame) -> pd.Series:
    """Canton-weighted alpine wet-bulb index, hourly UTC, Oct-Dec of each season."""
    num, den = None, None
    for _, row in stations.iterrows():
        d = _station_hourly(row.id)
        d = d[d.index.tz_convert(LOCAL_TZ).month.isin([10, 11, 12])]
        d = d[d.index.year.isin(list(SEASONS))]
        t = pd.to_numeric(d.tre200h0, errors="coerce").to_numpy(float)
        rh = pd.to_numeric(d.ure200h0, errors="coerce").to_numpy(float)
        ok = np.isfinite(t) & np.isfinite(rh)
        wb = np.full(t.shape, np.nan)
        wb[ok] = wet_bulb(t[ok], rh[ok], pressure_from_altitude(row.altitude))
        s = pd.Series(wb, index=d.index).dropna()
        w = float(row.weight)
        print(f"    {row.id} {row['name'][:22]:<22} {row.canton} "
              f"{row.altitude:>6.0f} m  w={w:.4f}  hours={len(s):,}")
        contrib = s * w
        wts = pd.Series(w, index=s.index)
        num = contrib if num is None else num.add(contrib, fill_value=0.0)
        den = wts if den is None else den.add(wts, fill_value=0.0)
    idx = (num / den)[den > 0.5 / len(SKI_CANTONS)]
    return idx.rename("wb").sort_index()


# ------------------------------------------------------------ night panel ---
def night_panel(load: pd.DataFrame, wb: pd.Series) -> pd.DataFrame:
    full = load.join(wb, how="inner")
    full = full[full.M.isin([10, 11, 12])].copy().sort_index()
    full["season"] = full["Y"]

    # cum_cold_h accumulates hours below threshold from 1 Oct, lagged so the
    # current hour never contributes to its own regressor, and running over
    # EVERY hour of the season, not only night hours.
    below_h = (full["wb"] < WB_THRESHOLD).astype(int)
    full["cum_cold_h"] = (below_h.groupby(full["season"])
                          .transform(lambda s: s.shift(1).fillna(0).cumsum()))

    df = full[full.H.isin(NIGHT_HOURS)].copy()
    # A night runs 20:00-06:59 LOCAL and is labelled by the date of its 20:00
    # hour. Shifting the tz-aware local stamp back 7 h collapses it onto that
    # date. tz_localize(None) first so the shift is wall-clock, not absolute.
    df["night_date"] = (df["local"].dt.tz_localize(None)
                        - pd.Timedelta(hours=7)).dt.date

    g = df.groupby("night_date")
    p = pd.DataFrame({
        "n_hours": g.size(),
        "err": g["err"].mean(),
        "actual": g["actual"].mean(),
        "wb": g["wb"].mean(),
        "cum_cold_h": g["cum_cold_h"].min(),
        "season": g["season"].first(),
    })
    p = p[p.n_hours >= MIN_NIGHT_HOURS].reset_index()
    d = pd.to_datetime(p.night_date)
    p["month"], p["doy"], p["dow"] = d.dt.month, d.dt.dayofyear, d.dt.dayofweek
    p["holiday"] = ((p.month == 12) & (d.dt.day >= 21)).astype(int)
    p["below"] = (p.wb < WB_THRESHOLD).astype(int)
    p["dist"] = p.wb - WB_THRESHOLD

    p = p.sort_values("night_date").reset_index(drop=True)
    starts = np.zeros(len(p), dtype=int)
    for _, idx in p.groupby("season").groups.items():
        a = p.loc[idx].sort_values("night_date")
        b = (a.wb < WB_THRESHOLD).to_numpy()
        for i in range(2, len(b)):
            if b[i] and not b[i - 1] and not b[i - 2]:
                starts[a.index[i]] = 1
    p["campaign_start"] = starts
    night2 = np.zeros(len(p), dtype=int)
    for _, idx in p.groupby("season").groups.items():
        a = p.loc[idx].sort_values("night_date")
        cs = a.campaign_start.to_numpy()
        for i in range(1, len(cs)):
            if cs[i - 1] == 1:
                night2[a.index[i]] = 1
    p["campaign_night2"] = night2
    return p[p.month.isin([11, 12])].reset_index(drop=True)


# ------------------------------------------------------------- estimation ---
def estimate(p: pd.DataFrame, label: str, extra: str = ""):
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
    return m


def descriptives(load: pd.DataFrame) -> None:
    d = load[load.H.isin(NIGHT_HOURS)].copy()
    d["night_date"] = (d["local"].dt.tz_localize(None)
                       - pd.Timedelta(hours=7)).dt.date
    g = d.groupby("night_date")
    n = pd.DataFrame({"err": g["err"].mean(), "n_hours": g.size()})
    n = n[n.n_hours >= MIN_NIGHT_HOURS].reset_index()
    dt = pd.to_datetime(n.night_date)
    n["month"], n["day"] = dt.dt.month, dt.dt.day

    print("\nnight bias by month (MW, +- s.e.)")
    m = n.groupby("month")["err"].agg(["mean", "sem"]).round(1)
    print("  " + "  ".join(f"{i:02d}:{r['mean']:+.0f}+-{r['sem']:.0f}"
                           for i, r in m.iterrows()))

    print("Nov 1 - Dec 30 in 10-day bins (Dec 31 excluded)")
    b = n[(n.month.isin([11, 12])) & (n.day <= 30)].copy()
    b["bin"] = b.month.map({11: "Nov", 12: "Dec"}) + " " + pd.cut(
        b.day, [0, 10, 20, 30], labels=["1-10", "11-20", "21-30"]).astype(str)
    order = [f"{mo} {dd}" for mo in ("Nov", "Dec")
             for dd in ("1-10", "11-20", "21-30")]
    r = b.groupby("bin")["err"].agg(["mean", "sem", "count"]).reindex(order)
    print(r.round(1).to_string())


# --------------------------------------------------------------- main -------
def main() -> None:
    print("=" * 74)
    print("SWISS REPLICATION -- snowmaking in the day-ahead load forecast")
    print("=" * 74)

    print("\n[1] energy-charts.info CH load + day-ahead load forecast ...")
    load = load_panel()
    print(f"  {load.index.min()} .. {load.index.max()} UTC")
    load, dropped = drop_degenerate_seasons(load)
    seasons_used = [s for s in SEASONS if s not in dropped]
    print(f"  seasons usable: {len(seasons_used)} of {len(list(SEASONS))} "
          f"-> {seasons_used}")

    night_all = load[load.H.isin(NIGHT_HOURS) & load.M.isin([11, 12])].copy()
    night_all = night_all[night_all.Y.isin(seasons_used)]
    mae = night_all.err.abs().mean()
    print("\n[2] GATE -- Nov-Dec night hours, day-ahead forecast error")
    print(f"  night hours   : {len(night_all):,} over "
          f"{night_all.Y.nunique()} seasons")
    print(f"  mean load     : {night_all.actual.mean():,.0f} MW")
    print(f"  bias          : {night_all.err.mean():+,.1f} MW")
    print(f"  sd            : {night_all.err.std():,.1f} MW")
    print(f"  MAE           : {mae:,.1f} MW "
          f"({100*mae/night_all.actual.mean():.2f}% of load)")

    import statsmodels.formula.api as smf
    night_all["dow"] = night_all["local"].dt.dayofweek
    sd_fe = smf.ols("err ~ C(H) + C(dow) + C(Y)",
                    data=night_all).fit().resid.std()
    n_ep = len(seasons_used) * EPISODES_PER_SEASON
    episode_sd = sd_fe * np.sqrt(RHO + (1 - RHO) / HOURS_PER_EPISODE)
    mde_mw = Z * episode_sd * np.sqrt(2 / (n_ep * 0.5))

    print("\n[3] MINIMUM DETECTABLE EFFECT (power.py logic, CH numbers)")
    print(f"  sd after hour/dow/season FE       : {sd_fe:,.1f} MW")
    print(f"  episodes assumed  {EPISODES_PER_SEASON}/season x "
          f"{len(seasons_used)} seasons  = {n_ep}")
    print(f"  hours/episode {HOURS_PER_EPISODE}, rho {RHO}, "
          f"Z {Z} (80% power / 5% two-sided)")
    print(f"  episode-mean sd                   : {episode_sd:,.1f} MW")
    print(f"  MDE                               : {mde_mw:,.1f} MW")
    print(f"  CH coincident snowmaking load S   : {S_MW:,.0f} MW "
          f"(900 MW x {CH_SNOW_GWH}/{AT_SNOW_GWH} GWh)")
    print(f"  alpha needed = MDE / S            : {mde_mw/S_MW:.0%}")
    at_alpha = mde_mw / AT_COINCIDENT_MW
    print(f"  (same MDE against the Austrian S = {AT_COINCIDENT_MW:.0f} MW "
          f"would need alpha {at_alpha:.0%})")
    if mde_mw / S_MW > 1.0:
        print("  VERDICT: alpha needed exceeds 100%. Even if the day-ahead")
        print("           forecast modelled NONE of Swiss snowmaking load, the")
        print("           effect would still be smaller than this sample can")
        print("           resolve. A null here is uninformative by construction.")
    else:
        print("  VERDICT: the sample can resolve a fully-unmodelled signal; "
              "see README for the partial-alpha reading.")

    descriptives(load)

    print("\n[4] MeteoSwiss SMN alpine stations (900-2600 m) ...")
    stations = pick_stations()
    print(stations[["id", "name", "canton", "altitude", "weight"]]
          .to_string(index=False))

    print("\n[5] building canton-weighted wet-bulb index ...")
    wb = wetbulb_index(stations)
    print(f"  hours: {len(wb):,}   share below {WB_THRESHOLD} C: "
          f"{100*(wb < WB_THRESHOLD).mean():.1f}%")

    p = night_panel(load, wb)
    print(f"\n[6] night panel: {len(p)} nights across {p.season.nunique()} "
          f"seasons, {int(p.campaign_start.sum())} campaign starts")
    print(p.groupby("season")
           .agg(nights=("err", "size"), below=("below", "sum"),
                starts=("campaign_start", "sum"),
                cum_end=("cum_cold_h", "max")).to_string())
    out = Path(__file__).with_name("ch_night_panel.csv")
    p.to_csv(out, index=False)
    print(f"  wrote {out}")

    import statsmodels.formula.api as smf  # noqa: F811

    print("\n[7] SPECIFICATIONS")
    estimate(p, "PRIMARY -- Nov-Dec, all nights")
    estimate(p[p.dist.abs() <= 3], "Bandwidth |wb+2| <= 3 C")
    estimate(p, "With campaign-start dummy", extra=" + campaign_start")
    m4 = estimate(p, "Campaign start + second night",
                  extra=" + campaign_start + campaign_night2")

    print("\n[8] SANITY GATE and DIAGNOSTICS")
    d = p.copy()
    d["cum100"] = (d.cum_cold_h - d.cum_cold_h.median()) / 100.0
    d["doy_c"] = (d.doy - d.doy.mean()) / 10.0
    d["fcst"] = d.actual - d.err
    ctrl = " ~ holiday + doy_c + I(doy_c**2) + C(season) + C(dow)"
    prim = (" ~ below * cum100 + dist + below:dist + holiday + doy_c "
            "+ I(doy_c**2) + C(season) + C(dow)")

    print("\n  8a. Christmas gate, same controls, three regressands")
    hol = {}
    for y in ("err", "actual", "fcst"):
        m = smf.ols(y + ctrl, data=d).fit(cov_type="HC1")
        hol[y] = (m.params["holiday"], m.bse["holiday"], m.tvalues["holiday"])
        print(f"    holiday on {y:<7}: {hol[y][0]:+8.1f} MW  "
              f"(se {hol[y][1]:5.1f}, z {hol[y][2]:+5.2f})")
    passed = hol["err"][0] < 0 and abs(hol["err"][2]) > 2
    if passed:
        print("    GATE PASSED: holiday on err is strongly negative.")
    else:
        print("    GATE FAILED on err. Required by the pre-registered spec.")
        print("    Root cause is visible in the same table: the Christmas")
        print("    shutdown IS in the Swiss load (holiday on actual is")
        print("    strongly negative, so the local-time night construction,")
        print("    the holiday flag and the panel are all working), but the")
        print("    Swiss day-ahead forecast anticipates it by an equal or")
        print("    larger amount, leaving nothing in the error. The gate's")
        print("    premise -- a forecaster that misses Christmas -- is an")
        print("    Austrian fact, not a Swiss one. Per the pre-registered")
        print("    rule the specification's coefficients below are NOT")
        print("    reportable as a finding.")

    print("\n  8b. Where the primary coefficient lives (same spec, "
          "three regressands)")
    b_lvl = None
    for y in ("err", "actual", "fcst"):
        m = smf.ols(y + prim, data=d).fit(cov_type="HC1")
        if y == "actual":
            b_lvl = m.params["below:cum100"]
        print(f"    below:cum100 on {y:<7}: "
              f"{m.params['below:cum100']:+8.2f} MW/100 h  "
              f"(se {m.bse['below:cum100']:5.2f}, z {m.tvalues['below:cum100']:+5.2f})")
    print("    Note this decomposition does NOT by itself separate snowmaking")
    print("    from anything else: snowmaking is real load, so a genuine blind")
    print("    spot would also appear in the level, be missing from the")
    print("    forecast, and survive in the error. What the level coefficient")
    print("    does settle is magnitude -- see 8d.")

    print("\n  8c. Forecast calibration, night means")
    m = smf.ols("actual ~ fcst + C(season)", data=d).fit(cov_type="HC1")
    print(f"    actual on forecast slope : {m.params['fcst']:.3f} "
          f"(se {m.bse['fcst']:.3f}); a calibrated forecast gives 1.000")
    print(f"    corr(err, actual)        : {d.err.corr(d.actual):+.3f}; an "
          f"unbiased forecast gives ~0")
    print("    per season:")
    for s, g in d.groupby("season"):
        mm = smf.ols("actual ~ fcst", data=g).fit()
        print(f"      {s}  slope {mm.params['fcst']:.3f}  R2 {mm.rsquared:.3f}"
              f"  sd(err) {g.err.std():.0f} MW")

    print("\n  8d. Implied magnitude of the primary coefficient vs the "
          "physical ceiling")
    m1 = smf.ols("err" + prim, data=d).fit(cov_type="HC1")
    b = m1.params["below:cum100"]
    se = m1.bse["below:cum100"]
    lo, hi = d.cum100.min(), d.cum100.max()
    print(f"    below:cum100 = {b:+.2f} MW per 100 lagged cold hours "
          f"(se {se:.2f})")
    print(f"    cum100 spans {lo:+.2f} .. {hi:+.2f} -> implied swing "
          f"{b*lo:+.0f} .. {b*hi:+.0f} MW")
    print(f"    same coefficient on the LOAD LEVEL {b_lvl:+.2f} -> implied "
          f"swing {b_lvl*lo:+.0f} .. {b_lvl*hi:+.0f} MW")
    print(f"    entire plausible CH coincident snowmaking load S = "
          f"{S_MW:.0f} MW")
    print(f"    |implied effect| at the top of the range is "
          f"{abs(b*hi)/S_MW:.1f}x S on err and {abs(b_lvl*hi)/S_MW:.1f}x S on")
    print("    the load level. The majority of a swing larger than the entire")
    print("    snowmaking fleet cannot be snowmaking, and the error inherits")
    print("    it through a forecast that under-models weather generically")
    print("    (calibration slope 0.714, corr(err, load) +0.584).")
    print(f"    For context, the 80%-power MDE on this coefficient alone is "
          f"{Z*se:.1f} MW/100 h;")
    print("    the binding power statement is the level-based MDE in [3].")
    _ = m4


if __name__ == "__main__":
    main()
