#!/usr/bin/env python3
"""
snowload.py — the one-day raw look.

Tests whether the ENTSO-E day-ahead load forecast error for Austria jumps at the
snowmaking wet-bulb threshold on Nov–Dec nights, and whether that jump decays as
the season's snow base gets built.

Requires:
    pip install entsoe-py pandas numpy requests statsmodels matplotlib
    export ENTSOE_TOKEN=...        # free, request via transparency@entsoe.eu

Run:
    python snowload.py --seasons 2018 2019 2021 2022 2023 2024

Design note: the primary test is NOT the raw threshold discontinuity — that is
confounded by everything else that happens when it gets cold. The primary test is
the INTERACTION between the threshold crossing and season-to-date accumulated
snowmaking opportunity. Heating load does not care how much snow has already been
made; snowmaking does. See PLACEBOS below.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

CACHE = Path("./cache")
CACHE.mkdir(exist_ok=True)

# Share of Austrian skier visits by state — used to weight the alpine wet-bulb
# index. Refine with equipped-hectare shares from the resort survey if available.
#
# CAVEAT on Vorarlberg: APG's published total load covers all of Austria "with
# the exception of a corridor in Vorarlberg" (markt.apg.at). VUEN is a legally
# separate control area under §23 ElWOG 2010, jointly operated with APG since
# 1.1.2012. Some Vorarlberg snowmaking (Lech/Zuers, Montafon) is therefore in the
# wet-bulb index but NOT in the dependent variable. Try weight 0.10 and 0.0 and
# report both; if the result moves, quantify the corridor before believing either.
REGION_WEIGHTS = {
    "Tirol": 0.50,
    "Salzburg": 0.24,
    "Vorarlberg": 0.10,
    "Steiermark": 0.09,
    "Kärnten": 0.05,
    "Oberösterreich": 0.015,
    "Niederösterreich": 0.005,
}
ALT_MIN, ALT_MAX = 900, 2600   # snowmaking altitude band

# Olefs et al. (2010, JAMC 49(6)): manufacturers quote -1.5 C wet bulb for BOTH
# air-water lances and fan guns; they round to -2.0 C. TechnoAlpin quotes -2.5 C.
# Efficient production wants -4 C or colder, so the effective start is
# state-dependent (how far behind the base is, how close opening day is) — which
# is what the below x cum_cold_hours interaction exploits.
WB_THRESHOLD = -2.0


# ----------------------------------------------------------------------------
# 1. Weather — GeoSphere Austria, no key required
# ----------------------------------------------------------------------------
GS = "https://dataset.api.hub.geosphere.at/v1"


def geosphere_stations() -> pd.DataFrame:
    f = CACHE / "gs_stations.csv"
    if f.exists():
        return pd.read_csv(f)
    r = requests.get(f"{GS}/station/historical/klima-v2-1h/metadata", timeout=60)
    r.raise_for_status()
    st = pd.DataFrame(r.json()["stations"])
    st.to_csv(f, index=False)
    return st


def pick_alpine_stations(st: pd.DataFrame, per_region: int = 4) -> pd.DataFrame:
    """Highest-altitude stations in the snowmaking band, per ski state."""
    st = st.copy()
    st["altitude"] = pd.to_numeric(st.get("altitude"), errors="coerce")
    st = st[(st.altitude.between(ALT_MIN, ALT_MAX)) & (st.get("is_active", True))]
    st = st[st["state"].isin(REGION_WEIGHTS)]
    out = (st.sort_values("altitude", ascending=False)
             .groupby("state", group_keys=False)
             .head(per_region))
    if out.empty:
        sys.exit("No alpine stations matched — inspect gs_stations.csv columns.")
    return out


def fetch_weather(station_ids: list[str], start: str, end: str) -> pd.DataFrame:
    """Hourly air temperature (tl, °C) and relative humidity (rf, %)."""
    key = f"gs_{start}_{end}_{len(station_ids)}.parquet"
    f = CACHE / key
    if f.exists():
        return pd.read_parquet(f)
    params = {
        "parameters": "tl,rf",
        "start": f"{start}T00:00",
        "end": f"{end}T23:00",
        "station_ids": ",".join(map(str, station_ids)),
        "output_format": "csv",
    }
    r = requests.get(f"{GS}/station/historical/klima-v2-1h",
                     params=params, timeout=600)
    r.raise_for_status()
    from io import StringIO
    df = pd.read_csv(StringIO(r.text))
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df.to_parquet(f)
    return df


def _es_water(t_c):
    """Saturation vapour pressure over water, hPa (WMO Magnus). Snowmakers'
    'wet bulb' uses a supercooled-water wick below 0 °C, so stay over water."""
    return 6.112 * np.exp(17.62 * t_c / (243.12 + t_c))


def pressure_from_altitude(alt_m):
    """ISA barometric pressure, hPa. At 1800 m this shifts wet bulb by ~0.2–0.4 °C
    versus a sea-level assumption — larger than the RD bandwidth you care about,
    so do not skip it."""
    return 1013.25 * (1 - 2.25577e-5 * np.asarray(alt_m, float)) ** 5.25588


def wet_bulb(t_c, rh_pct, p_hpa=1013.25, iters: int = 60):
    """Psychrometric wet bulb by bisection on
       es(Tw) - A*P*(T - Tw) - e = 0,  A = 6.53e-4 (1 + 9.44e-4 Tw).
    Agrees with psychrometric tables to ~0.2 °C from -20 to +30 °C, versus
    ~1 °C error for the Stull (2011) closed form at sub-zero temperatures."""
    t = np.asarray(t_c, float)
    rh = np.clip(np.asarray(rh_pct, float), 1, 100)
    p = np.broadcast_to(np.asarray(p_hpa, float), t.shape).astype(float)
    e = rh / 100.0 * _es_water(t)
    lo = np.full_like(t, -60.0)
    hi = t.copy()
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        a = 6.53e-4 * (1 + 0.000944 * mid)
        f = _es_water(mid) - a * p * (t - mid) - e
        hi = np.where(f > 0, mid, hi)
        lo = np.where(f > 0, lo, mid)
    return 0.5 * (lo + hi)


def alpine_wetbulb_index(wx: pd.DataFrame, stations: pd.DataFrame) -> pd.Series:
    """Region-weighted mean wet bulb across alpine stations."""
    meta = stations[["id", "state", "altitude"]].rename(columns={"id": "station"})
    wx = wx.merge(meta, on="station", how="inner")
    wx["wb"] = wet_bulb(wx["tl"].to_numpy(float),
                        wx["rf"].to_numpy(float),
                        pressure_from_altitude(wx["altitude"].to_numpy(float)))
    by_region = wx.groupby(["time", "state"])["wb"].mean().unstack()
    w = pd.Series(REGION_WEIGHTS).reindex(by_region.columns).fillna(0)
    w = w / w.sum()
    return (by_region * w).sum(axis=1).rename("wb_index")


# ----------------------------------------------------------------------------
# 2. Load — ENTSO-E Transparency Platform
# ----------------------------------------------------------------------------
def fetch_load(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    from entsoe import EntsoePandasClient
    token = os.environ.get("ENTSOE_TOKEN")
    if not token:
        sys.exit("Set ENTSOE_TOKEN. Free: register at transparency.entsoe.eu, "
                 "then email transparency@entsoe.eu, subject 'RESTful API access'.")
    f = CACHE / f"load_{start:%Y%m%d}_{end:%Y%m%d}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    c = EntsoePandasClient(api_key=token)
    actual = c.query_load("AT", start=start, end=end)
    fcst = c.query_load_forecast("AT", start=start, end=end)
    df = pd.concat([actual.iloc[:, 0].rename("actual"),
                    fcst.iloc[:, 0].rename("forecast")], axis=1)
    df = df.resample("1h").mean()
    df.index = df.index.tz_convert("UTC")
    df["err"] = df["actual"] - df["forecast"]      # >0 = under-forecast
    df.to_parquet(f)
    return df


# ----------------------------------------------------------------------------
# 3. Panel construction
# ----------------------------------------------------------------------------
def build_panel(load: pd.DataFrame, wb: pd.Series) -> pd.DataFrame:
    df = load.join(wb, how="inner").dropna()
    loc = df.index.tz_convert("Europe/Vienna")
    df["hour"] = loc.hour
    df["month"] = loc.month
    df["doy"] = loc.dayofyear
    df["dow"] = loc.dayofweek
    df["date"] = loc.date
    # season label: Nov 2023 and Jan 2024 both belong to season 2023
    df["season"] = np.where(loc.month >= 9, loc.year, loc.year - 1)
    df["night"] = df["hour"].isin(list(range(21, 24)) + list(range(0, 6)))
    df["below"] = (df["wb_index"] < WB_THRESHOLD).astype(int)
    df["dist"] = df["wb_index"] - WB_THRESHOLD

    # Season-to-date snowmaking opportunity: cumulative hours below threshold
    # since 1 Oct. This is the proxy for "how much base is already built".
    df = df.sort_index()
    df["cum_cold_h"] = (df.groupby("season")["below"]
                          .transform(lambda s: s.shift(1).fillna(0).cumsum()))

    # Campaign starts: first hour below threshold after >=48 h above it.
    below = df["below"].to_numpy()
    gap = pd.Series(below).rolling(48, min_periods=1).max().shift(1).fillna(0)
    df["campaign_start"] = ((below == 1) & (gap.to_numpy() == 0)).astype(int)

    # Normalise the error so seasons with different load levels are comparable
    df["err_pct"] = 100 * df["err"] / df["actual"]
    return df


# ----------------------------------------------------------------------------
# 4. Tests
# ----------------------------------------------------------------------------
def run_tests(df: pd.DataFrame, bandwidth: float = 3.0) -> None:
    import statsmodels.formula.api as smf

    # STEP ZERO. This single number decides whether the rest is worth running.
    # With 7 clean seasons the design needs the forecast to be leaving >=~19% of
    # the ~900 MW snowmaking load unexplained. That pass mark scales with this sd.
    night_all = df[df.night]
    sd = night_all["err"].std()
    mae_pct = 100 * night_all["err"].abs().mean() / night_all["actual"].mean()
    print(f"AT day-ahead forecast error, night hours: sd = {sd:.0f} MW, "
          f"MAE = {mae_pct:.2f}% of load")
    print(f"  -> alpha needed at 7 seasons (9 episodes, 8 h, rho 0.7): "
          f"{2.80 * sd * np.sqrt(0.7 + 0.3/8) * np.sqrt(2/(7*9/2)) / 900:.1%}")
    print("     (DE-LU benchmark MAE is 3.14%; if AT is much worse, stop here.)")

    early = df[(df.night) & (df.month.isin([11, 12]))].copy()
    rd = early[early["dist"].abs() <= bandwidth].copy()
    # Centred on the median so the `below` main effect reads as the jump at a
    # typical point in the season, not at cum_cold_h = 0 (which is off-support).
    rd["cum100"] = (rd["cum_cold_h"] - rd["cum_cold_h"].median()) / 100.0

    print(f"\nNight hours, Nov–Dec: {len(early):,}   "
          f"within ±{bandwidth}°C of threshold: {len(rd):,}   "
          f"distinct nights: {rd['date'].nunique():,}\n")

    def show(name, formula, data):
        m = smf.ols(formula, data=data).fit(
            cov_type="cluster", cov_kwds={"groups": data["date"].astype(str)})
        print(f"--- {name}")
        keep = [p for p in m.params.index
                if "below" in p or "cum100" in p or p == "Intercept"]
        print(m.summary2().tables[1].loc[keep].round(3).to_string(), "\n")
        return m

    # (1) The note's headline test. Expect a positive jump if snowmaking is
    #     unmodelled — but see PLACEBOS before believing it.
    show("RD: does the error jump at the threshold?",
         "err ~ below + dist + below:dist + C(hour) + C(dow) + C(season)", rd)

    # (2) The test that actually identifies snowmaking. Heating load does not
    #     care about season-to-date accumulated cold; snowmaking does.
    #     Prediction: below:cum100 coefficient is NEGATIVE and significant.
    show("RD × accumulated base (PRIMARY TEST)",
         "err ~ below * cum100 + dist + below:dist "
         "+ C(hour) + C(dow) + C(season)", rd)

    # (3) Event study on campaign starts — isolates the first night, which is
    #     when an autoregressive forecast has not yet caught up.
    starts = df.index[df["campaign_start"] == 1]
    rows = []
    for t0 in starts:
        w = df.loc[t0 - pd.Timedelta("48h"): t0 + pd.Timedelta("96h")]
        if len(w) < 100:
            continue
        w = w.assign(rel=((w.index - t0) / pd.Timedelta("1h")).astype(int),
                     ev=str(t0))
        rows.append(w[["err", "rel", "ev", "night"]])
    if rows:
        ev = pd.concat(rows)
        prof = ev[ev.night].groupby("rel")["err"].agg(["mean", "sem", "count"])
        print("--- Event study: mean forecast error around campaign start "
              f"({len(rows)} events, night hours only)")
        print(prof.reindex(range(-48, 97, 12)).round(1).to_string(), "\n")

    # PLACEBOS ---------------------------------------------------------------
    # If any of these show the same jump, the result is heating, not snow.
    print("--- PLACEBO 1: same threshold logic, Jun–Aug (no snowmaking)")
    su = df[(df.night) & (df.month.isin([6, 7, 8]))].copy()
    su["dist_s"] = su["wb_index"] - su["wb_index"].quantile(0.10)
    su["below_s"] = (su["dist_s"] < 0).astype(int)
    su = su[su["dist_s"].abs() <= bandwidth]
    if len(su) > 200:
        show("summer pseudo-threshold", "err ~ below_s + dist_s + C(hour)", su)

    print("--- PLACEBO 2: rerun the whole script with country_code='NL' or 'DK'.")
    print("    Cold, flat, no snowmaking. A jump there is a heating artefact.\n")

    print("--- PLACEBO 3: restrict to nights AFTER each resort's opening date.")
    print("    Snowmaking drops once the base is built; heating does not.\n")


# ----------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int,
                    default=[2018, 2019, 2021, 2022, 2023, 2024],
                    help="Season start years. 2020 omitted: COVID closures.")
    ap.add_argument("--bandwidth", type=float, default=3.0)
    a = ap.parse_args()

    start = pd.Timestamp(f"{min(a.seasons)}-09-01", tz="Europe/Vienna")
    end = pd.Timestamp(f"{max(a.seasons)+1}-09-01", tz="Europe/Vienna")

    st = geosphere_stations()
    alp = pick_alpine_stations(st)
    print(f"Alpine stations ({len(alp)}):")
    print(alp[["id", "name", "state", "altitude"]].to_string(index=False), "\n")

    wx = fetch_weather(alp["id"].astype(str).tolist(),
                       f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}")
    wb = alpine_wetbulb_index(wx, alp)
    load = fetch_load(start, end)
    df = build_panel(load, wb)
    run_tests(df, a.bandwidth)

    df.to_parquet("panel.parquet")
    print("Panel written to panel.parquet")


if __name__ == "__main__":
    main()
