#!/usr/bin/env python
"""Does the day-ahead spot price move with a snowfall-FORECAST REVISION?

The design, the three anchors, the outcome, the predicted sign, the kill
criteria and the power gate are all fixed in src/revision/README.md, which was
committed before this file produced a single coefficient.

    python src/revision/revision_pipeline.py

WHAT IS BEING TESTED
    Not "is tonight cold" -- every other arm of this project tests that and each
    one runs into the same heating confound. Here the treatment is the CHANGE in
    the National Weather Service's overnight snowfall forecast for one specific
    night, between two specific issuances, holding the wet-bulb revision over
    the same period in the same zone fixed.

    rev_pre  = S(B) - S(A)   news that arrived BEFORE the auction closed
    rev_post = S(C) - S(B)   news that arrived AFTER it closed

    A = last issuance at or before 12 hours before that gate
    B = last issuance at or before the gate that priced this night
    C = last issuance before 19:00 ET, when the guns start

    A is 12 hours before the gate and not 24, because `Snow 12hr` reaches about
    40 hours and a 24-hour anchor needs 44.5. README section 7 carries the
    measurement and the amendment; it was made before any coefficient existed.

ORDER OF PRINTING
    Power gate first, then kill criterion 1 on rev_post, then the primary
    coefficient. README section 10 makes criterion 1 decisive: the day-ahead
    auction closed before rev_post existed, so a price that responds to it is
    responding to something rev_post merely proxies, and rev_pre is then
    uninterpretable whatever it does. That verdict is printed before rev_pre so
    it cannot be read around.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fetch_afm import CACHE                                  # noqa: E402
from parse_afm import CORE_ZONES, RESORT_ZONES               # noqa: E402

AFM = CACHE.parent / "afm_snow.csv"
ISONE = Path(r"C:\Users\bcris\.claude-snow\jobs\11224758\tmp\price\isone")
LMP = {"Vermont": ISONE / "lmp_vermont.csv",
       "RhodeIsland": ISONE / "lmp_rhodeisland.csv"}

TZ = "America/New_York"
GATE_PRIMARY = (10, 30)          # README section 7: 10:30 ET primary ...
GATE_ALT = (10, 0)               # ... 10:00 ET sensitivity (FERC ER20-2511)
GUNS_ON = 19                     # last issuance before 19:00 ET is anchor C
# README section 7, amended: `Snow 12hr` reaches ~40 h and a 24 h anchor needs
# 44.5 h, which exists on 0.0% of night-zones. 12 h needs 32.5 and exists on 98%.
LAG_A_H = 12

NIGHT_HB = range(0, 7)           # hours beginning 00:00 .. 06:00 of D+1
MIDDAY_HB = range(11, 16)        # hours beginning 11:00 .. 15:00 of D+1
MIN_NIGHT_HB, MIN_MIDDAY_HB = 6, 4
MIN_ZONES = 3                    # of the four core zones

# README section 11. Price README section 10.3 measured both halves of this
# product on this market: +23.9 USD/MWh per GW overnight supply slope, 70 MW
# Vermont fleet. A revision cannot switch off more than the whole fleet, so this
# is an upper bound on any effect this design could be looking for.
FLEET_MW = 70.0
SLOPE_USD_PER_GW = 23.9
IMPLIED_BOUND = FLEET_MW / 1000.0 * SLOPE_USD_PER_GW          # 1.673 USD/MWh

FORMULA = ("{y} ~ rev_pre + rev_post + wbrev_pre + wbrev_post"
           " + snow_gate + wb_gate"
           " + holiday + doy_c + I(doy_c**2) + C(season) + C(dow)")


# ------------------------------------------------------------- treatment ----
def load_afm() -> pd.DataFrame:
    if not AFM.exists():
        sys.exit(f"missing {AFM}; run parse_afm.py first")
    d = pd.read_csv(AFM, parse_dates=["valid_end_utc", "issued_utc"])
    for c in ("valid_end_utc", "issued_utc"):
        d[c] = pd.to_datetime(d[c], utc=True)
    # The overnight 12-hour period is the one ending 12Z. In EST that is
    # 19:00-07:00 local, which is the snowmaking night this project has used
    # since apg_pipeline.py, to within one hour.
    d = d[d.valid_end_utc.dt.hour == 12].copy()
    d["night"] = (d.valid_end_utc - pd.Timedelta(days=1)).dt.date
    return d


def gate_utc(nights: pd.Series, hh_mm: tuple[int, int]) -> pd.Series:
    """The bid deadline on night-date D, as an instant. Built in local time and
    converted per date, so the November fall-back needs no special case."""
    h, m = hh_mm
    naive = pd.to_datetime(pd.Series(list(nights))) + pd.Timedelta(hours=h,
                                                                  minutes=m)
    return naive.dt.tz_localize(TZ, nonexistent="shift_forward",
                                ambiguous=True).dt.tz_convert("UTC")


def local_utc(nights: pd.Series, hour: int) -> pd.Series:
    naive = pd.to_datetime(pd.Series(list(nights))) + pd.Timedelta(hours=hour)
    return naive.dt.tz_localize(TZ, nonexistent="shift_forward",
                                ambiguous=True).dt.tz_convert("UTC")


def _pick(d: pd.DataFrame, deadline: pd.Series, tag: str) -> pd.DataFrame:
    """Latest issuance at or before `deadline`, per (night, zone)."""
    x = d.merge(deadline.rename("cut"), left_on="night", right_index=True)
    x = x[x.issued_utc <= x.cut]
    if not len(x):
        return pd.DataFrame(columns=["night", "zone", f"S_{tag}", f"wb_{tag}"])
    k = x.groupby(["night", "zone"])["issued_utc"].idxmax()
    x = x.loc[k, ["night", "zone", "snow_in", "wb_c", "issued_utc"]]
    return x.rename(columns={"snow_in": f"S_{tag}", "wb_c": f"wb_{tag}",
                             "issued_utc": f"t_{tag}"})


def treatment(d: pd.DataFrame, gate=GATE_PRIMARY,
              zones=CORE_ZONES) -> pd.DataFrame:
    z = d[d.zone.isin(zones)].copy()
    nights = pd.Index(sorted(z.night.unique()), name="night")
    g = pd.Series(gate_utc(nights, gate).values, index=nights)
    anchors = {"A": g - pd.Timedelta(hours=LAG_A_H),
               "B": g,
               "C": pd.Series(local_utc(nights, GUNS_ON).values, index=nights)
               - pd.Timedelta(seconds=1)}
    out = None
    for tag, cut in anchors.items():
        part = _pick(z, cut, tag)
        out = part if out is None else out.merge(part, on=["night", "zone"],
                                                 how="inner")
    if out is None or not len(out):
        return pd.DataFrame()

    out = out.dropna(subset=["S_A", "S_B", "S_C", "wb_A", "wb_B", "wb_C"])
    out["rev_pre"] = out.S_B - out.S_A
    out["rev_post"] = out.S_C - out.S_B
    out["wbrev_pre"] = out.wb_B - out.wb_A
    out["wbrev_post"] = out.wb_C - out.wb_B

    # Anchor C must genuinely postdate the gate, or rev_post is not post-gate
    # news. It is identically zero when B and C are the same issuance.
    out["post_is_new"] = out.t_C > out.t_B

    agg = out.groupby("night").agg(
        n_zones=("zone", "nunique"),
        rev_pre=("rev_pre", "mean"), rev_post=("rev_post", "mean"),
        wbrev_pre=("wbrev_pre", "mean"), wbrev_post=("wbrev_post", "mean"),
        snow_gate=("S_B", "mean"), wb_gate=("wb_B", "mean"),
        post_is_new=("post_is_new", "any")).reset_index()
    return agg[agg.n_zones >= MIN_ZONES]


# --------------------------------------------------------------- outcome ----
def spread(zone_file: Path) -> pd.DataFrame:
    """Night-minus-midday day-ahead LMP spread, both windows inside operating
    day D+1 so both clear in the auction that closed at the gate on D."""
    p = pd.read_csv(zone_file, parse_dates=["date"])
    p = p[p.hb.notna()]
    nt = p[p.hb.isin(NIGHT_HB)].groupby("date")["lmp_usd_mwh"].agg(["mean",
                                                                    "size"])
    md = p[p.hb.isin(MIDDAY_HB)].groupby("date")["lmp_usd_mwh"].agg(["mean",
                                                                     "size"])
    j = nt.join(md, lsuffix="_n", rsuffix="_m", how="inner")
    j = j[(j["size_n"] >= MIN_NIGHT_HB) & (j["size_m"] >= MIN_MIDDAY_HB)]
    out = pd.DataFrame({"spread": j["mean_n"] - j["mean_m"],
                        "night_level": j["mean_n"]})
    out.index = pd.to_datetime(out.index)
    # The outcome sits in operating day D+1; label it by the night D.
    out["night"] = (out.index - pd.Timedelta(days=1)).date
    return out.reset_index(drop=True)


# -------------------------------------------------------------- controls ----
def controls(panel: pd.DataFrame) -> pd.DataFrame:
    d = pd.to_datetime(pd.Series(list(panel.night)))
    panel = panel.copy()
    panel["month"] = d.dt.month.values
    panel["season"] = np.where(d.dt.month.values >= 10, d.dt.year.values,
                               d.dt.year.values - 1)
    panel["doy"] = d.dt.dayofyear.values
    panel["dow"] = d.dt.dayofweek.values
    # Identical to src/apg_pipeline.py; copied, not re-derived.
    panel["holiday"] = ((panel.month == 12) & (d.dt.day.values >= 21)).astype(int)
    panel["doy_c"] = (panel.doy - panel.doy.mean()) / 10.0
    return panel


def build(gate=GATE_PRIMARY, zones=CORE_ZONES) -> dict[str, pd.DataFrame]:
    afm = load_afm()
    tr = treatment(afm, gate=gate, zones=zones)
    out = {}
    for name, f in LMP.items():
        if not f.exists():
            print(f"  ! missing {f}")
            continue
        p = controls(tr.merge(spread(f), on="night", how="inner"))
        # Nights labelled 1 Nov .. 30 Dec: the outcome then sits wholly inside
        # operating day D+1, which is still in December.
        out[name] = p[p.month.isin((11, 12))].reset_index(drop=True)
    if len(out) == 2:
        a, b = out["Vermont"], out["RhodeIsland"]
        diff = a.merge(b[["night", "spread", "night_level"]], on="night",
                       suffixes=("", "_ri"))
        diff["spread"] = diff.spread - diff.spread_ri
        diff["night_level"] = diff.night_level - diff.night_level_ri
        out["VT-RI"] = diff
    return out


# ----------------------------------------------------------------- report ---
def fit(panel: pd.DataFrame, y: str = "spread", hac: int | None = None):
    f = FORMULA.format(y=y)
    m = smf.ols(f, data=panel)
    if hac:
        return m.fit(cov_type="HAC", cov_kwds={"maxlags": hac, "use_correction": True})
    return m.fit(cov_type="HC1")


def line(r, term: str) -> str:
    if term not in r.params:
        return f"  {term:<12} absent"
    return (f"  {term:<12} {r.params[term]:+9.4f}  ({r.bse[term]:.4f})  "
            f"t={r.tvalues[term]:+6.2f}  p={r.pvalues[term]:.4f}")


def report(panels: dict[str, pd.DataFrame]) -> None:
    vt = panels.get("Vermont")
    if vt is None or len(vt) < 50:
        print("not enough nights to estimate"); return

    print("=" * 74)
    print("PANEL")
    print("=" * 74)
    for k, p in panels.items():
        print(f"  {k:<12} {len(p):4d} nights, seasons "
              f"{p.season.min()}-{p.season.max()}, "
              f"{p.season.nunique()} of them")
    print(f"\n  rev_pre  sd={vt.rev_pre.std():.3f} in, "
          f"range {vt.rev_pre.min():+.2f} .. {vt.rev_pre.max():+.2f}, "
          f"{100*(vt.rev_pre != 0).mean():.1f}% non-zero")
    print(f"  rev_post sd={vt.rev_post.std():.3f} in, "
          f"range {vt.rev_post.min():+.2f} .. {vt.rev_post.max():+.2f}, "
          f"{100*(vt.rev_post != 0).mean():.1f}% non-zero")
    print(f"  a genuinely later anchor C exists on "
          f"{100*vt.post_is_new.mean():.1f}% of nights")
    print(f"  spread   sd={vt.spread.std():.2f} USD/MWh")

    r = fit(vt)

    print("\n" + "=" * 74)
    print("GATE 1  POWER, printed before any coefficient (README section 11)")
    print("=" * 74)
    se = r.bse["rev_pre"]
    for label, scale in (("one sd of rev_pre", vt.rev_pre.std()),
                         ("full observed range",
                          vt.rev_pre.max() - vt.rev_pre.min())):
        mde = 1.96 * se * scale
        verdict = "CANNOT SEE IT" if mde > IMPLIED_BOUND else "could see it"
        print(f"  scaled to {label:<20} {scale:6.3f} in -> "
              f"MDE {mde:7.3f} USD/MWh  vs bound {IMPLIED_BOUND:.3f}  "
              f"{verdict}")
    print(f"\n  The bound is the WHOLE Vermont fleet ({FLEET_MW:.0f} MW) against "
          f"this market's\n  own overnight supply slope "
          f"(+{SLOPE_USD_PER_GW} USD/MWh per GW, price README 10.3).")
    print("  No forecast revision switches off more than the whole fleet, so a")
    print("  verdict of CANNOT SEE IT here needs no behavioural assumption.")

    print("\n" + "=" * 74)
    print("GATE 2  KILL CRITERION 1: rev_post must be zero (README section 10)")
    print("=" * 74)
    print(line(r, "rev_post"))
    invalid = r.pvalues["rev_post"] < 0.05
    if invalid:
        print("\n  *** INVALID. The auction closed before this news existed. A")
        print("  *** price that responds to it is responding to something")
        print("  *** rev_post proxies, and rev_pre proxies it too. No claim is")
        print("  *** made from rev_pre below, whatever it does.")
    else:
        print("\n  Passes: the day-ahead price does not respond to news that")
        print("  postdates it. rev_pre may be read, subject to gate 1.")

    print("\n" + "=" * 74)
    print("PRIMARY COEFFICIENT  rev_pre, USD/MWh per inch")
    print("=" * 74)
    for k, p in panels.items():
        rr = fit(p)
        print(f"{k}:")
        print(line(rr, "rev_pre"))
        print(line(rr, "rev_post"))
        print(line(rr, "wbrev_pre"))
        print(line(rr, "holiday"))
        print()

    print("=" * 74)
    print("SENSITIVITIES")
    print("=" * 74)
    for lbl, kw in (("night level, not spread", dict(y="night_level")),
                    ("HAC(7) standard errors", dict(hac=7))):
        rr = fit(vt, **kw)
        print(f"{lbl}:")
        print(line(rr, "rev_pre"))
        print(line(rr, "rev_post"))
        print()


def main() -> None:
    print(f"reading {AFM}")
    panels = build()
    if not panels:
        sys.exit("no panel built")
    report(panels)

    print("=" * 74)
    print("GATE SENSITIVITY  10:00 ET instead of 10:30 (README section 7)")
    print("=" * 74)
    alt = build(gate=GATE_ALT)
    if "Vermont" in alt:
        a, b = panels["Vermont"], alt["Vermont"]
        j = a[["night", "rev_pre"]].merge(b[["night", "rev_pre"]], on="night",
                                          suffixes=("_1030", "_1000"))
        moved = (j.rev_pre_1030 != j.rev_pre_1000).sum()
        print(f"  {moved} of {len(j)} nights change rev_pre between the two "
              f"gate definitions ({100*moved/max(len(j),1):.1f}%)")
        print(line(fit(b), "rev_pre"))
        print(line(fit(b), "rev_post"))


if __name__ == "__main__":
    main()
