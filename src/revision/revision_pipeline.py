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


def _local_instant(nights: pd.Index, hours: float) -> pd.Series:
    """A local wall-clock time on each night-date D, as a UTC instant, indexed
    by the night.

    Built in local time and converted per date, so the November fall-back needs
    no special case. Do NOT round-trip this through `.values`: that strips the
    timezone and the comparison against `issued_utc` then raises, or worse,
    silently compares a UTC instant to a naive Eastern one.
    """
    naive = pd.DatetimeIndex(pd.to_datetime(pd.Index(list(nights)))) \
        + pd.Timedelta(hours=hours)
    aware = naive.tz_localize(TZ, nonexistent="shift_forward",
                              ambiguous=True).tz_convert("UTC")
    return pd.Series(aware, index=pd.Index(list(nights), name="night"))


def gate_utc(nights: pd.Index, hh_mm: tuple[int, int]) -> pd.Series:
    """The day-ahead bid deadline on night-date D."""
    h, m = hh_mm
    return _local_instant(nights, h + m / 60.0)


def _pick(d: pd.DataFrame, deadline: pd.Series, tag: str,
          snow_col: str = "snow_in") -> pd.DataFrame:
    """Latest issuance at or before `deadline`, per (night, zone)."""
    x = d.merge(deadline.rename("cut"), left_on="night", right_index=True)
    x = x[x.issued_utc <= x.cut]
    if not len(x):
        return pd.DataFrame(columns=["night", "zone", f"S_{tag}", f"wb_{tag}"])
    k = x.groupby(["night", "zone"])["issued_utc"].idxmax()
    x = x.loc[k, ["night", "zone", snow_col, "wb_c", "issued_utc"]]
    return x.rename(columns={snow_col: f"S_{tag}", "wb_c": f"wb_{tag}",
                             "issued_utc": f"t_{tag}"})


def treatment(d: pd.DataFrame, gate=GATE_PRIMARY, zones=CORE_ZONES,
              snow_col: str = "snow_in") -> pd.DataFrame:
    """`snow_col` is "snow_in" (range midpoint, trace 0.05) for the primary and
    "snow_in_lo" (range lower bound, trace exactly 0) for the README section 12
    coarseness sensitivity."""
    z = d[d.zone.isin(zones)].copy()
    nights = pd.Index(sorted(z.night.unique()), name="night")
    g = gate_utc(nights, gate)
    anchors = {"A": g - pd.Timedelta(hours=LAG_A_H),
               "B": g,
               "C": _local_instant(nights, GUNS_ON) - pd.Timedelta(seconds=1)}
    out = None
    for tag, cut in anchors.items():
        part = _pick(z, cut, tag, snow_col=snow_col)
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


def spread_straddle(zone_file: Path) -> pd.DataFrame:
    """README section 8, sensitivity (i): the price test's OWN outcome.

    The 11-hour night block 20:00 D .. 06:59 D+1 against midday 11:00-15:59 of
    D. Reported for comparability with src/price/README.md and labelled for what
    it is: the night hours straddle two auctions, so no single gate prices them
    and the pre/post split is only clean for the seven hours after midnight.
    """
    p = pd.read_csv(zone_file, parse_dates=["date"])
    p = p[p.hb.notna()].copy()
    t = p.date + pd.to_timedelta(p.hb, unit="h")
    p["night"] = (t - pd.Timedelta(hours=7)).dt.date
    nt = p[p.hb.isin(list(range(20, 24)) + list(range(0, 7)))]
    nt = nt.groupby("night")["lmp_usd_mwh"].agg(["mean", "size"])
    nt = nt[nt["size"] >= 8]["mean"]
    md = p[p.hb.isin(MIDDAY_HB)].copy()
    md["night"] = md.date.dt.date                 # midday of D, not D+1
    md = md.groupby("night")["lmp_usd_mwh"].agg(["mean", "size"])
    md = md[md["size"] >= MIN_MIDDAY_HB]["mean"]
    j = pd.concat([nt.rename("n"), md.rename("m")], axis=1, join="inner")
    return pd.DataFrame({"night": j.index, "spread": (j.n - j.m).values,
                         "night_level": j.n.values})


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


def build(gate=GATE_PRIMARY, zones=CORE_ZONES, snow_col="snow_in",
          outcome=spread, afm: pd.DataFrame | None = None
          ) -> dict[str, pd.DataFrame]:
    afm = load_afm() if afm is None else afm
    tr = treatment(afm, gate=gate, zones=zones, snow_col=snow_col)
    out = {}
    for name, f in LMP.items():
        if not f.exists():
            print(f"  ! missing {f}")
            continue
        p = controls(tr.merge(outcome(f), on="night", how="inner"))
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


# ------------------------------------------------------------ power gate ----
def supply_slope(zone_file: Path = LMP["Vermont"]) -> dict | None:
    """Overnight supply slope, USD/MWh per GW, re-estimated on this arm's own
    seasons. README section 11, item 4.

    Night mean price on night mean ISO-NE demand, with season fixed effects, on
    exactly the hours the outcome uses. Total demand rather than residual: EIA-930
    publishes no wind or solar split for ISNE, which price README 10.3 recorded
    as a deviation biasing the slope toward zero.
    """
    try:
        from fetch_isne_load import load as load_isne
        ld = load_isne()
    except Exception as e:                                   # noqa: BLE001
        print(f"  (no ISNE load series: {e})")
        return None
    if not len(ld):
        return None
    ld = ld.assign(date=ld.t_begin.dt.normalize(), hb=ld.t_begin.dt.hour)
    dem = (ld[ld.hb.isin(NIGHT_HB)].groupby("date")["demand_mw"]
           .agg(["mean", "size"]))
    dem = dem[dem["size"] >= MIN_NIGHT_HB]["mean"].rename("demand_mw")

    p = pd.read_csv(zone_file, parse_dates=["date"])
    pr = (p[p.hb.isin(NIGHT_HB)].groupby("date")["lmp_usd_mwh"]
          .agg(["mean", "size"]))
    pr = pr[pr["size"] >= MIN_NIGHT_HB]["mean"].rename("price")

    j = pd.concat([dem, pr], axis=1, join="inner").dropna().reset_index()
    if len(j) < 100:
        return None
    j["demand_gw"] = j.demand_mw / 1000.0
    j["season"] = np.where(j.date.dt.month >= 10, j.date.dt.year,
                           j.date.dt.year - 1)
    r = smf.ols("price ~ demand_gw + C(season)", data=j).fit(cov_type="HC1")
    return {"slope": float(r.params["demand_gw"]),
            "se": float(r.bse["demand_gw"]), "n": len(j),
            "seasons": int(j.season.nunique())}


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
    # Anchor availability was measured on four seasons. If older vintages carry
    # fewer forward snow periods the attrition concentrates by season, so show
    # the per-season counts rather than only the total.
    print("\n  nights per season:")
    print("   " + "  ".join(f"{s}:{n}" for s, n
                            in vt.season.value_counts().sort_index().items()))

    r = fit(vt)

    print("\n" + "=" * 74)
    print("GATE 1  POWER, printed before any coefficient (README section 11)")
    print("=" * 74)
    se = r.bse["rev_pre"]
    for label, scale in (("one sd of rev_pre", vt.rev_pre.std()),
                         ("full observed range",
                          vt.rev_pre.max() - vt.rev_pre.min())):
        mde = 1.96 * se * scale
        verdict = ("UNINFORMATIVE, outcome 4" if mde > IMPLIED_BOUND
                   else "not ruled out by the bound")
        print(f"  scaled to {label:<20} {scale:6.3f} in -> "
              f"MDE {mde:7.3f} USD/MWh  vs bound {IMPLIED_BOUND:.3f}  "
              f"{verdict}")
    print(f"\n  The bound is the WHOLE Vermont fleet ({FLEET_MW:.0f} MW) against "
          f"this market's\n  own overnight supply slope "
          f"(+{SLOPE_USD_PER_GW} USD/MWh per GW, price README 10.3).")
    print("  It is an UPPER bound and the asymmetry matters. MDE above it means")
    print("  the test could not have seen the effect even if a revision shut")
    print("  down every gun in Vermont, and that verdict needs no behavioural")
    print("  assumption. MDE below it certifies nothing: a revision of one")
    print("  standard deviation plainly does not shut down the whole fleet, and")
    print("  this gate has no way to say what fraction it does shut down.")

    ss = supply_slope()
    if ss:
        own = FLEET_MW / 1000.0 * ss["slope"]
        print(f"\n  Re-estimated on this arm's own {ss['seasons']} seasons "
              f"({ss['n']:,} nights): slope "
              f"{ss['slope']:+.1f} ({ss['se']:.1f}) USD/MWh per GW, "
              f"so the bound is {own:.3f} USD/MWh.")
        print(f"  Inherited from price README 10.3: "
              f"+{SLOPE_USD_PER_GW} per GW, bound {IMPLIED_BOUND:.3f}. Both are "
              f"printed because\n  section 11 item 4 registered both; the "
              f"verdicts above use the inherited one.")

    print("\n" + "=" * 74)
    print("GATE 2  KILL CRITERION 1: rev_post must be zero (README section 10)")
    print("=" * 74)
    print(line(r, "rev_post"))
    mde_post = 1.96 * r.bse["rev_post"] * vt.rev_post.std()
    print(f"\n  Its own MDE, scaled to one sd of rev_post "
          f"({vt.rev_post.std():.3f} in): {mde_post:.3f} USD/MWh.")
    print("  Read the verdict below against that number. rev_post carries less")
    print("  variance than rev_pre, so a pass here is a weak pass: the design")
    print("  survives the falsification without being certified by it.")
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
    print("SENSITIVITIES  (every one registered in the README before the run)")
    print("=" * 74)
    for lbl, kw in (("s8ii  night level, not spread", dict(y="night_level")),
                    ("s9    HAC(7) standard errors", dict(hac=7))):
        rr = fit(vt, **kw)
        print(f"{lbl}:")
        print(line(rr, "rev_pre"))
        print(line(rr, "rev_post"))
        print()


def six_season_nights() -> set | None:
    """The Vermont load panel's own nights, for the README section 9
    comparability sensitivity."""
    f = HERE.parents[0] / "vermont" / "night_panel_vermont.csv"
    if not f.exists():
        return None
    return set(pd.to_datetime(pd.read_csv(f)["night_date"]).dt.date)


def main() -> None:
    print(f"reading {AFM}")
    afm = load_afm()
    panels = build(afm=afm)
    if not panels:
        sys.exit("no panel built")
    report(panels)

    print("=" * 74)
    print("REGISTERED VARIANTS  (README sections 6, 7, 8, 9, 12)")
    print("=" * 74)

    print("s7    gate at 10:00 ET instead of 10:30")
    alt = build(gate=GATE_ALT, afm=afm)
    if "Vermont" in alt:
        b = alt["Vermont"]
        j = panels["Vermont"][["night", "rev_pre"]].merge(
            b[["night", "rev_pre"]], on="night", suffixes=("_1030", "_1000"))
        moved = int((j.rev_pre_1030 != j.rev_pre_1000).sum())
        print(f"      {moved} of {len(j)} nights change rev_pre between the "
              f"two gate definitions ({100*moved/max(len(j),1):.1f}%)")
        print(line(fit(b), "rev_pre"))
        print(line(fit(b), "rev_post"))

    for lbl, kw in (
            ("s6    all eight resort zones, not the four core",
             dict(zones=tuple(RESORT_ZONES))),
            ("s12   range lower bound, trace exactly zero",
             dict(snow_col="snow_in_lo")),
            ("s8i   11-hour night block vs midday of D (straddles two "
             "auctions)", dict(outcome=spread_straddle))):
        v = build(afm=afm, **kw)
        print(f"\n{lbl}")
        if "Vermont" not in v or len(v["Vermont"]) < 50:
            print("      too few nights"); continue
        print(f"      {len(v['Vermont'])} nights")
        print(line(fit(v["Vermont"]), "rev_pre"))
        print(line(fit(v["Vermont"]), "rev_post"))
        if "VT-RI" in v:
            print("      VT-RI differential:")
            print(line(fit(v["VT-RI"]), "rev_pre"))

    keep = six_season_nights()
    print("\ns9    restricted to the Vermont load panel's own nights")
    if keep is None:
        print("      night_panel_vermont.csv not found")
    else:
        sub = panels["Vermont"][panels["Vermont"].night.isin(keep)]
        print(f"      {len(sub)} nights, {sub.season.nunique()} seasons")
        if len(sub) >= 50:
            print(line(fit(sub), "rev_pre"))
            print(line(fit(sub), "rev_post"))


if __name__ == "__main__":
    main()
