#!/usr/bin/env python
"""Does the day-ahead SPOT price move with snowmaking weather?

Four markets on one specification: Austria, Italy-North, Switzerland, and the
Vermont zone of ISO New England. The design, the predicted sign, the kill
criteria and the power gate are all fixed in src/price/README.md, which was
committed before this file produced a single coefficient.

    python src/price/price_pipeline.py

SPOT, NOT FUTURES. The outcome is the day-ahead auction clearing price, which
is a spot price and is called that throughout. A snowmaking decision has an
eighteen-hour horizon and the day-ahead auction is the only instrument that
clears on it. No futures contract is touched here. See README section 1.

WHAT IS AND IS NOT REBUILT
    Nothing on the right-hand side is rebuilt. The wet-bulb index, the cumulative
    cold hours, the below/dist/holiday/season/dow controls are all read from the
    night panel each country's own load pipeline already wrote. This script adds
    exactly one column, the price outcome, and joins it on the night date. That
    is what makes the price coefficient and the load coefficient comparable
    rather than merely similar.

OUTCOME
    Primary   night mean price minus same-day midday mean price (the spread).
    Sensitivity   night mean price in levels.
    Night is 20:00-06:59 labelled by date(t - 7h), >= 8 valid hours, exactly as
    in src/apg_pipeline.py. Midday is 11:00-15:59 of the day the night starts on,
    so both windows clear in the same auction.

ORDER OF PRINTING
    Gates first, coefficient last. The sanity gate (holiday must be negative) and
    the power gate (minimum detectable effect against the price impact implied by
    the market's own supply slope) are both printed before any primary
    coefficient, so that a coefficient is never read before it is known whether
    it could have meant anything.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
# Scratch cache, deliberately outside the repository. Raw downloads are never
# committed; the committed artefacts are this script and the write-up.
CACHE = Path(r"C:\Users\bcris\.claude-snow\jobs\11224758\tmp\price")
CACHE.mkdir(parents=True, exist_ok=True)

EC = "https://api.energy-charts.info"
PACE = 3.5            # seconds between energy-charts calls; it rate-limits
TRIES = 4

NIGHT_HOURS = set(range(20, 24)) | set(range(0, 7))
MIDDAY_HOURS = set(range(11, 16))
MIN_NIGHT_HOURS = 8
MIN_MIDDAY_HOURS = 4
SEASON_MONTHS = (11, 12)

# (key, label, bidding zone, tz, currency, night panel, snowmaking increment MW)
# The increment is the fleet draw estimated in section 2 of the root README and
# in each replication's own write-up. It is what the power gate is measured
# against; it is an input to this script, not an output of it.
MARKETS = [
    ("AT", "Austria",     "AT",       "Europe/Vienna", "EUR",
     "data/night_panel.csv",                    427),
    ("IT", "Italy-North", "IT-North", "Europe/Rome",   "EUR",
     "src/it_north/night_panel_it.csv",         463),
    ("CH", "Switzerland", "CH",       "Europe/Zurich", "EUR",
     "src/swiss/ch_night_panel.csv",            200),
]

# ISO-NE is handled separately: its price is an LMP in USD, its hours arrive as
# published ordinals rather than timestamps, and its panel is a share panel.
ISONE = [
    ("VT", "ISO-NE Vermont",      "src/vermont/night_panel_vermont.csv",
     "lmp_vermont.csv",      100),
    ("RI", "ISO-NE Rhode Island", "src/vermont/night_panel_rhodeisland.csv",
     "lmp_rhodeisland.csv",    0),
]


# ------------------------------------------------------------- fetching ------
def _ec_get(path: str, **params) -> dict:
    """Paced, retried GET against energy-charts. It returns HTML or an empty
    body under load rather than a clean error, so a JSON decode failure is
    treated as a retryable rate limit rather than as missing data."""
    url = f"{EC}/{path}"
    for k in range(TRIES):
        try:
            r = requests.get(url, params=params, timeout=120)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(PACE * (k + 2))
    raise RuntimeError(f"energy-charts {path} {params} failed after {TRIES} tries")


def ec_series(path: str, key: str, year: int, tz: str, **params) -> pd.Series:
    """One Oct-Dec season of an hourly energy-charts series, indexed by LOCAL
    'YYYY-MM-DD HH'. The API returns unix seconds, so the local clock is derived
    rather than assumed."""
    f = CACHE / f"{path}_{key}_{year}.json"
    if f.exists():
        j = json.loads(f.read_text())
    else:
        j = _ec_get(path, start=f"{year}-09-25", end=f"{year}-12-31", **params)
        f.write_text(json.dumps(j))
        time.sleep(PACE)
    return j


def price_series(bzn: str, years, tz: str) -> pd.Series:
    """Hourly day-ahead spot price, local clock, currency per MWh."""
    out = []
    for y in years:
        try:
            j = ec_series("price", bzn, y, tz, bzn=bzn)
        except RuntimeError as e:
            print(f"    {bzn} {y}: {e}")
            continue
        idx = pd.to_datetime(j["unix_seconds"], unit="s", utc=True)
        s = pd.Series(j["price"], index=idx.tz_convert(tz), name="price")
        out.append(s[~s.index.duplicated()])
    if not out:
        return pd.Series(dtype=float)
    return pd.concat(out).sort_index()


def residual_load_series(country: str, years, tz: str) -> pd.Series:
    """Hourly residual load (load minus wind minus solar) in MW, local clock.
    Used only by the power gate, to estimate the local supply slope."""
    out = []
    for y in years:
        try:
            j = ec_series("public_power", country, y, tz, country=country)
        except RuntimeError as e:
            print(f"    {country} residual load {y}: {e}")
            continue
        types = {d["name"]: d["data"] for d in j["production_types"]}
        name = next((n for n in types if n.lower() == "residual load"), None)
        if name is None:
            continue
        idx = pd.to_datetime(j["unix_seconds"], unit="s", utc=True)
        s = pd.Series(types[name], index=idx.tz_convert(tz))
        out.append(s[~s.index.duplicated()])
    if not out:
        return pd.Series(dtype=float)
    return pd.concat(out).sort_index().resample("1h").mean()


# ------------------------------------------------------ outcome building -----
def night_and_midday(px: pd.Series) -> pd.DataFrame:
    """Collapse an hourly local-clock price series to one row per night.

    The night label is date(t - 7h), so 20:00 on D through 06:59 on D+1 all
    carry the label D. This is character for character the rule in
    src/apg_pipeline.py; it is repeated rather than imported because the four
    pipelines each carry their own copy and diverging here would be silent.
    """
    if not len(px):
        return pd.DataFrame()
    d = pd.DataFrame({"price": px.values}, index=px.index)
    d["H"] = d.index.hour
    d["cal"] = d.index.normalize()

    nights = d[d.H.isin(NIGHT_HOURS)].copy()
    nights["night_date"] = (nights.index - pd.Timedelta(hours=7)).normalize()
    gn = nights.groupby("night_date")["price"]
    night = pd.DataFrame({"p_night": gn.mean(), "n_night": gn.size()})
    night = night[night.n_night >= MIN_NIGHT_HOURS]

    mid = d[d.H.isin(MIDDAY_HOURS)].copy()
    gm = mid.groupby("cal")["price"]
    midday = pd.DataFrame({"p_mid": gm.mean(), "n_mid": gm.size()})
    midday = midday[midday.n_mid >= MIN_MIDDAY_HOURS]
    midday.index.name = "night_date"      # midday of D belongs to night D

    out = night.join(midday, how="inner")
    out["spread"] = out.p_night - out.p_mid
    return out.reset_index()


def join_panel(panel_path: str, out: pd.DataFrame) -> pd.DataFrame:
    """Attach the price outcome to a night panel written by a load pipeline."""
    p = pd.read_csv(ROOT / panel_path, parse_dates=["night_date"])
    p = p.rename(columns={"err": "err_load"})
    j = p.merge(out, on="night_date", how="inner")
    return j[j.month.isin(SEASON_MONTHS)].reset_index(drop=True)


# ---------------------------------------------------------- estimation -------
FORMULA = ("{y} ~ below * cum100 + dist + below:dist + holiday "
           "+ doy_c + I(doy_c**2) + C(season) + C(dow)")


def estimate(p: pd.DataFrame, y: str, label: str, quiet: bool = False):
    """The load test's specification, outcome swapped for a price. HC1."""
    import statsmodels.formula.api as smf
    if len(p) < 40 or p.below.nunique() < 2:
        if not quiet:
            print(f"\n=== {label}: too few observations (n={len(p)}), skipped ===")
        return None
    d = p.copy()
    d["cum100"] = (d.cum_cold_h - d.cum_cold_h.median()) / 100.0
    d["doy_c"] = (d.doy - d.doy.mean()) / 10.0
    m = smf.ols(FORMULA.format(y=y), data=d).fit(cov_type="HC1")
    if not quiet:
        keep = [t for t in m.params.index
                if any(k in t for k in ("below", "cum100", "dist", "holiday"))]
        tab = pd.DataFrame({"Coef.": m.params, "Std.Err.": m.bse,
                            "z": m.tvalues, "P>|z|": m.pvalues}).loc[keep]
        print(f"\n=== {label}  (n={int(m.nobs)}, "
              f"seasons {sorted(d.season.unique())}) ===")
        print(tab.round(4).to_string())
        k = "below:cum100"
        if k in m.params.index:
            print(f"  PRIMARY {k} = {m.params[k]:+.4f} per 100 cold hours "
                  f"(HC1 s.e. {m.bse[k]:.4f}, z {m.tvalues[k]:+.2f}, "
                  f"p = {m.pvalues[k]:.3f})")
    return m


def sanity_gate(p: pd.DataFrame, y: str, label: str) -> bool:
    """Christmas must lower the price. See README section 6 for why this gate
    transfers to Italy where the load test's Christmas gate did not."""
    m = estimate(p, y, label, quiet=True)
    if m is None or "holiday" not in m.params.index:
        print(f"  GATE holiday: not estimable")
        return False
    c, s = m.params["holiday"], m.bse["holiday"]
    ok = c < 0 and abs(c / s) > 2
    print(f"  GATE holiday = {c:+.2f} (HC1 s.e. {s:.2f}, t {c/s:+.2f})  "
          f"-> {'PASS' if ok else 'FAIL'}  "
          f"(required: negative and |t| > 2)")
    return ok


def power_gate(p: pd.DataFrame, y: str, rl: pd.Series, tz: str,
               increment_mw: float, unit: str) -> None:
    """Print, before any primary coefficient, what this test could have found.

    Step 1 estimates the local supply slope from the market's own data by
    regressing the night mean price on the night mean residual load with season
    fixed effects. Step 2 turns the country's snowmaking increment into a price
    impact. Step 3 compares it with the minimum detectable effect.
    """
    import statsmodels.formula.api as smf
    print("\n  POWER GATE (printed before the coefficient, by design)")
    if not len(rl):
        print("    residual load unavailable; supply slope not estimated")
        slope = np.nan
    else:
        n = rl[rl.index.hour.isin(NIGHT_HOURS)]
        nd = pd.DataFrame({"rl": n.values}, index=n.index)
        nd["night_date"] = (nd.index - pd.Timedelta(hours=7)).normalize()
        g = nd.groupby("night_date")["rl"].mean().rename("rl_gw") / 1000.0
        q = p.merge(g.reset_index(), on="night_date", how="inner")
        if len(q) < 40:
            print("    too few matched nights to estimate the supply slope")
            slope = np.nan
        else:
            ms = smf.ols("p_night ~ rl_gw + C(season)",
                         data=q).fit(cov_type="HC1")
            slope = ms.params["rl_gw"]
            print(f"    supply slope dP/dQ = {slope:+.2f} {unit}/MWh per GW "
                  f"(HC1 s.e. {ms.bse['rl_gw']:.2f}, n={int(ms.nobs)} nights)")
    impact = slope * increment_mw / 1000.0
    print(f"    snowmaking increment {increment_mw:,} MW "
          f"-> implied price impact {impact:+.3f} {unit}/MWh")

    m = estimate(p, y, "power", quiet=True)
    if m is None or "below:cum100" not in m.params.index:
        print("    minimum detectable effect: not estimable")
        return
    se = m.bse["below:cum100"]
    end = (p.cum_cold_h.max() - p.cum_cold_h.median()) / 100.0
    mde = 1.96 * se * end
    print(f"    s.e. {se:.4f} {unit}/MWh per 100 h; at end-of-season "
          f"cum100 = {end:.1f} the minimum detectable effect is "
          f"{mde:.3f} {unit}/MWh")
    if np.isnan(impact):
        verdict = "UNKNOWN (no supply slope)"
    elif mde > abs(impact):
        verdict = (f"UNDERPOWERED: MDE {mde:.3f} exceeds the implied impact "
                   f"{abs(impact):.3f}. Read the coefficient as uninformative.")
    else:
        verdict = (f"POWERED: MDE {mde:.3f} is below the implied impact "
                   f"{abs(impact):.3f}.")
    print(f"    VERDICT: {verdict}")


# ----------------------------------------------------------------- main ------
def describe(px: pd.Series, label: str, unit: str) -> None:
    """Verification block. energy-charts has served this project a fabricated
    series before (root README section 8.9), so every price series states its
    own shape before it is used."""
    if not len(px):
        print(f"  {label}: EMPTY")
        return
    y = px.groupby(px.index.year)
    t = pd.DataFrame({"hours": y.size(), "min": y.min(), "mean": y.mean(),
                      "max": y.max(), "sd": y.std(),
                      "neg_h": y.apply(lambda s: int((s < 0).sum())),
                      "over300_h": y.apply(lambda s: int((s > 300).sum()))})
    print(f"  {label} ({unit}/MWh), Oct-Dec by year")
    print(t.round(2).to_string())


def run_market(key, label, bzn, tz, unit, panel, increment) -> None:
    print("\n" + "=" * 74)
    print(f"{label}  ({bzn}, day-ahead SPOT price, {unit}/MWh)")
    print("=" * 74)
    panel_all = pd.read_csv(ROOT / panel, parse_dates=["night_date"])
    years = sorted(panel_all.season.unique())
    px = price_series(bzn, years, tz)
    describe(px, f"{bzn} day-ahead spot", unit)
    out = night_and_midday(px)
    if not len(out):
        print("  no usable price nights"); return
    p = join_panel(panel, out)
    print(f"\n  matched {len(p)} nights, seasons {sorted(p.season.unique())}")
    print(f"  night mean {p.p_night.mean():.2f}, midday mean {p.p_mid.mean():.2f}, "
          f"spread mean {p.spread.mean():+.2f} (sd {p.spread.std():.2f}) {unit}/MWh")

    if not sanity_gate(p, "spread", f"{label} gate"):
        print("  SANITY GATE FAILED -- coefficients below are not interpretable")
    rl = residual_load_series(bzn.split("-")[0].lower(), years, tz)
    power_gate(p, "spread", rl, tz, increment, unit)

    estimate(p, "spread", f"{label}: PRIMARY, night-minus-midday spread")
    estimate(p, "p_night", f"{label}: SENSITIVITY, night level")


def main() -> None:
    print("DAY-AHEAD SPOT PRICE vs SNOWMAKING WEATHER")
    print("Pre-registered in src/price/README.md. Spot, not futures.")
    print("Gates print before coefficients, by design.")
    for m in MARKETS:
        run_market(*m)
    print("\nISO New England: see run_isone() once the LMP archive is in cache.")


if __name__ == "__main__":
    main()
