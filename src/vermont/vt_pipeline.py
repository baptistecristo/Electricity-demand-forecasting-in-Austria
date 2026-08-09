#!/usr/bin/env python3
"""
vt_pipeline.py -- ISO-NE VERMONT snowmaking-in-load-forecast test.

Companion to src/apg_pipeline.py (Austria). The wet-bulb solver, the station
pressure correction, the night definition, the threshold, the running
`cum_cold_h` variable and the control set are reused unchanged. What changes is
the OUTCOME VARIABLE.

The reason is structural. ISO-NE's Three-Day Reliability Region Demand Forecast
is a hybrid product: the regional PERCENTAGE is the primitive and regional MW is
that percentage times a separately published system total. GATE 1 re-proves that
from the downloaded files -- every hourly eight-zone total lands on a multiple
of 10 MW, MW equals per cent times total to a rounding error, and shares and
totals refresh on separate cycles. Vermont MW error therefore mixes a New
England system-forecast error with a Vermont share error, and only the second
can carry a Vermont-specific blind spot.

We test option (a): the day-ahead Vermont SHARE against the realised Vermont
share, in percentage points. GATE 2 reports the variance split behind that
choice from the data rather than assuming it; note that the split it finds runs
opposite to the direction anticipated before actuals were in hand, and README
section 1 says so explicitly.

    pip install pandas numpy requests statsmodels
    python src/vermont/vt_pipeline.py

Data sources, all keyless:
  * forecast : iso-ne.com /transform/csv/reliabilityregionloadforecast, one CSV
               per target date. Needs a session cookie from the report page plus
               a matching Referer, and it rate-limits, so fetches are paced and
               cached. ~427 dates, ~75 min cold; instant from cache.
  * actual   : EIA-930 six-month SUBREGION files, balancing authority ISNE.
               Subregion codes 4001..4008 are ISO-NE's own load-zone IDs; the
               pipeline verifies that mapping against ISO-NE's five-minute
               estimated zonal load report rather than assuming it.
  * weather  : Iowa Environmental Mesonet archive of the VTrans RWIS network --
               elevated (462-721 m) roadside stations sitting at the access
               roads of the major Vermont ski areas. NOAA's own hosts
               (ncei.noaa.gov, www1.ncdc.noaa.gov) reset the TLS connection from
               this machine, so IEM's archive of the same NWS/state observations
               is used instead. Mount Washington ASOS (1910 m) is a secondary,
               true-summit robustness index.

Everything the script prints is computed from the data it fetched. Nothing is
quoted from a prior pass.
"""
from __future__ import annotations

import io
import random
import sys
import time
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# --------------------------------------------------------------- settings ---
# Scratch cache. Kept outside the repository on purpose.
CACHE = Path(r"C:\Users\bcris\.claude-snow\jobs\11224758\tmp\vt\cache")
OUTDIR = Path(__file__).resolve().parent

SEASONS = range(2019, 2026)          # winter 2019-20 .. 2025-26
PANEL_MONTHS = (11, 12)              # Nov-Dec, as in Austria
WB_THRESHOLD = -2.0                  # deg C wet bulb, as in Austria
NIGHT_HOURS = set(range(20, 24)) | set(range(0, 7))   # 20:00-06:59 local
MIN_NIGHT_HOURS = 8
DAM_CUTOFF = dt.time(10, 30)         # ISO-NE day-ahead market bid deadline, ET
TZ = "America/New_York"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
TREE = "https://www.iso-ne.com/isoexpress/web/reports/load-and-demand/-/tree/"
REF_FCST = TREE + "three-day-reliability-region-demand-forecast"
REF_ZONAL = TREE + "estimated-zonal-load"

# ISO-NE load zones. The EIA-930 ISNE subregion codes are these same zone IDs;
# verify_zone_codes() checks that against ISO-NE's own report before use.
ZONES = {"4001": ".Z.MAINE", "4002": ".Z.NEWHAMPSHIRE", "4003": ".Z.VERMONT",
         "4004": ".Z.CONNECTICUT", "4005": ".Z.RHODEISLAND",
         "4006": ".Z.SEMASS", "4007": ".Z.WCMASS", "4008": ".Z.NEMASSBOST"}
VT, RI = ".Z.VERMONT", ".Z.RHODEISLAND"

# Elevated VTrans RWIS stations, one or more per major snowmaking resort.
# (id, name, elevation m, resort served)
RWIS = [
    ("VT028", "Rt 17 Buels Gore",    721.4, "Sugarbush / Mad River Glen"),
    ("VT040", "Rt 242 Westfield",    685.0, "Jay Peak"),
    ("VT023", "Rt 11 Winhall",       678.7, "Stratton / Bromley"),
    ("VT014", "Woodford",            663.8, "Mount Snow / Prospect"),
    ("VT035", "Rt 4 Mendon Mountain",652.0, "Killington / Pico"),
    ("VT022", "Rt 105 Jay",          581.7, "Jay Peak (lower)"),
    ("VT001", "Brookfield",          492.0, "central Green Mountains"),
    ("VT021", "Mount Holly Rt 103",  462.0, "Okemo"),
]
MWN = ("MWN", "Mount Washington", 1910.0, "NH_ASOS")   # robustness index

IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request"
EIA = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/"


# ------------------------------------------------------------- wet bulb ------
# Verbatim from src/apg_pipeline.py. Do not substitute the Stull closed form:
# it errs 0.7-1.0 C below freezing, larger than the effect being tested.
def _es_water(t):
    """Saturation vapour pressure over water, hPa (WMO Magnus). Snowmakers'
    wet bulb uses a supercooled-water wick below 0 C, so stay over water."""
    return 6.112 * np.exp(17.62 * t / (243.12 + t))


def pressure_from_altitude(alt_m):
    """ISA pressure, hPa. At 700 m this moves wet bulb by ~0.1-0.2 C versus a
    sea-level assumption. Do not skip it."""
    return 1013.25 * (1 - 2.25577e-5 * np.asarray(alt_m, float)) ** 5.25588


def wet_bulb(t_c, rh_pct, p_hpa, iters: int = 50):
    """Bisection on es(Tw) - A*P*(T-Tw) - e = 0, A = 6.53e-4 (1 + 9.44e-4 Tw).
    Matches psychrometric tables to ~0.2 C."""
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


# ------------------------------------------------------- ISO-NE fetching -----
def _iso_get(endpoint: str, ref: str, qs: str, tries: int = 4):
    """One paced ISO-NE CSV. Fresh session per request (the cookie is what the
    endpoint checks) plus a matching Referer; without both it answers 403."""
    for k in range(tries):
        s = requests.Session()
        s.headers.update({"User-Agent": UA})
        try:
            s.get(ref, timeout=60)
            time.sleep(1.0 + random.random())
            r = s.get(f"https://www.iso-ne.com/transform/csv/{endpoint}?{qs}",
                      timeout=240, headers={"Referer": ref})
            if r.status_code == 200 and r.text.startswith('"C"'):
                return r.text
        except Exception:
            pass
        finally:
            s.close()
        time.sleep(20 * (k + 1))      # 403 wall: back off, do not hammer
    return None


def target_dates() -> list[str]:
    out = []
    for y in SEASONS:
        d = dt.date(y, PANEL_MONTHS[0], 1)
        while d <= dt.date(y, PANEL_MONTHS[-1], 31):
            out.append(d.strftime("%Y%m%d"))
            d += dt.timedelta(days=1)
    return out


def ensure_forecast_cache(pace: float = 9.0) -> Path:
    d = CACHE / "forecast"
    d.mkdir(parents=True, exist_ok=True)
    todo = [x for x in target_dates() if not (d / f"{x}.csv").exists()]
    if todo:
        print(f"fetching {len(todo)} forecast days from ISO-NE "
              f"(~{len(todo)*(pace+2)/60:.0f} min, cached thereafter) ...")
        for i, day in enumerate(todo):
            txt = _iso_get("reliabilityregionloadforecast", REF_FCST,
                           f"start={day}")
            if txt is not None:
                (d / f"{day}.csv").write_text(txt, encoding="utf-8")
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{len(todo)}", flush=True)
            time.sleep(pace + random.random() * 2)
    return d


def _parse_iso_csv(text: str, names: list[str]) -> pd.DataFrame:
    """ISO-NE CSVs interleave comment/header/data/trailer rows tagged in the
    first field. Keep only the 'D' rows."""
    rows = [L for L in text.splitlines() if L.startswith('"D"')]
    if not rows:
        return pd.DataFrame(columns=names)
    return pd.read_csv(io.StringIO("\n".join(rows)), header=None,
                       names=["tag"] + names).drop(columns="tag")


def load_forecast() -> pd.DataFrame:
    """All publications, all regions, all cached target dates."""
    d = ensure_forecast_cache()
    frames = []
    for p in sorted(d.glob("*.csv")):
        f = _parse_iso_csv(p.read_text(encoding="utf-8"),
                           ["fdate", "he", "region", "mw", "pct", "pub"])
        if len(f):
            frames.append(f)
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df.fdate, format="%m/%d/%Y")
    df["pub"] = pd.to_datetime(df.pub, format="%m/%d/%Y %H:%M:%S")
    df["he"] = df.he.astype(str).str.strip()
    # '02X' is the repeated hour on the November fall-back Sunday. Sort key puts
    # it straight after '02'; ord_h is then the chronological slot in the day.
    df["he_n"] = df.he.str.extract(r"(\d+)").astype(int)
    df["he_x"] = df.he.str.contains("X").astype(int)
    df = df.sort_values(["date", "pub", "he_n", "he_x"])
    df["ord_h"] = df.groupby(["date", "pub", "region"]).cumcount() + 1
    return df


def day_ahead_vintage(fc: pd.DataFrame) -> pd.DataFrame:
    """For each target date keep the LATEST publication timestamped at or before
    10:30 on D-1 -- the ISO-NE day-ahead market bid deadline. In this archive
    that selects the ~09:30 morning run, not the afternoon re-publications."""
    pub_date = fc.pub.dt.normalize()
    cutoff = fc.date - pd.Timedelta(days=1)
    elig = fc[(pub_date == cutoff) &
              (fc.pub.dt.time <= DAM_CUTOFF)].copy()
    best = elig.groupby("date")["pub"].max().rename("chosen")
    elig = elig.merge(best, on="date")
    return elig[elig.pub == elig.chosen].drop(columns="chosen")


# --------------------------------------------------------- EIA-930 actuals ---
def ensure_eia_cache() -> Path:
    d = CACHE / "eia"
    d.mkdir(parents=True, exist_ok=True)
    for y in range(min(SEASONS), max(SEASONS) + 2):
        for half in ("Jan_Jun", "Jul_Dec"):
            name = f"EIA930_SUBREGION_{y}_{half}.csv"
            dst = d / name.replace(".csv", "_ISNE.csv")
            if dst.exists():
                continue
            r = requests.get(EIA + name, timeout=900,
                             headers={"User-Agent": UA})
            if not r.ok or len(r.content) < 10000:
                continue
            f = pd.read_csv(io.BytesIO(r.content), dtype=str)
            f.columns = [c.strip() for c in f.columns]
            f[f["Balancing Authority"] == "ISNE"].to_csv(dst, index=False)
            print(f"  EIA {name}")
    return d


def load_actual() -> pd.DataFrame:
    d = ensure_eia_cache()
    f = pd.concat([pd.read_csv(x, dtype=str) for x in sorted(d.glob("*_ISNE.csv"))],
                  ignore_index=True)
    f["date"] = pd.to_datetime(f["Data Date"], format="%m/%d/%Y")
    f["ord_h"] = pd.to_numeric(f["Hour Number"])
    f["mw"] = pd.to_numeric(f["Demand (MW)"], errors="coerce")
    f["region"] = f["Sub-Region"].map(ZONES)
    f = f.dropna(subset=["mw", "region"])
    return f[["date", "ord_h", "region", "mw"]]


def ensure_zonal_cache(pace: float = 9.0, dates=None) -> Path:
    """ISO-NE's own five-minute estimated zonal load, one CSV per date.

    Two traps, both found the hard way and both silent -- the endpoint answers
    200 with a well-formed CSV containing zero data rows either way:
      * BOTH start and end must be supplied. `?start=YYYYMMDD` alone yields
        nothing, and the filename in the header ends `_null.csv` when it does.
      * The archive is shallow. Probing 2024-06-01, 2024-11-01, 2024-12-15 and
        2025-01-01 returned zero rows; 2025-06-01, 2025-12-15, 2026-03-15,
        2026-06-15 and 2026-08-01 all returned the full 2,304 rows. So this
        report cannot supply actuals for the seven-season panel. It is used as a
        same-publisher cross-check on the one season it covers, and EIA-930 is
        the actual series throughout.
    """
    d = CACHE / "zonal"
    d.mkdir(parents=True, exist_ok=True)
    todo = [x for x in (dates or target_dates()) if not (d / f"{x}.csv").exists()]
    for i, day in enumerate(todo):
        txt = _iso_get("fiveminuteestimatedzonalload", REF_ZONAL,
                       f"start={day}&end={day}")
        if txt is not None:
            (d / f"{day}.csv").write_text(txt, encoding="utf-8")
        time.sleep(pace + random.random() * 2)
    return d


def load_actual_iso() -> pd.DataFrame:
    """Cached ISO-NE five-minute zonal load aggregated to the hour.

    Interval stamps repeat on the November fall-back Sunday, so the hour slot is
    taken from position in the day (the file is chronological) rather than from
    the clock: twelve 5-minute intervals per slot.
    """
    d = CACHE / "zonal"
    frames = []
    for p in sorted(d.glob("*.csv")):
        z = _parse_iso_csv(p.read_text(encoding="utf-8"),
                           ["ts", "zid", "zname", "mw", "btm"])
        if not len(z):
            continue
        z["mw"] = pd.to_numeric(z.mw, errors="coerce")
        z["date"] = pd.to_datetime(p.stem, format="%Y%m%d")
        z["slot"] = z.groupby("zid").cumcount()
        z["ord_h"] = z.slot // 12 + 1
        g = (z.groupby(["date", "ord_h", "zname"])
               .agg(mw=("mw", "mean"), n=("mw", "size")).reset_index())
        frames.append(g[g.n == 12].drop(columns="n"))
    if not frames:
        return pd.DataFrame(columns=["date", "ord_h", "region", "mw"])
    a = pd.concat(frames, ignore_index=True).rename(columns={"zname": "region"})
    return a.dropna(subset=["mw"])


def verify_zone_codes(sample_dates=("20251215", "20251110")) -> None:
    """The EIA subregion codes are asserted to be ISO-NE load-zone IDs. Check it
    against ISO-NE's own five-minute estimated zonal load report, which prints
    the ID and the zone name side by side."""
    print("\nGATE 0 -- EIA-930 subregion code <-> ISO-NE load zone")
    d = CACHE / "zonal"
    d.mkdir(parents=True, exist_ok=True)
    seen = {}
    for day in sample_dates:
        p = d / f"{day}.csv"
        if not p.exists():
            txt = _iso_get("fiveminuteestimatedzonalload", REF_ZONAL,
                           f"start={day}&end={day}")
            if txt is None:
                print(f"  {day}: ISO-NE zonal report unreachable, skipped")
                continue
            p.write_text(txt, encoding="utf-8")
        z = _parse_iso_csv(p.read_text(encoding="utf-8"),
                           ["ts", "zid", "zname", "mw", "btm"])
        for zid, zname in z[["zid", "zname"]].drop_duplicates().values:
            seen[str(zid)] = zname
    if not seen:
        print("  no ISO-NE zonal sample available; mapping UNVERIFIED")
        return
    bad = [(k, v, ZONES.get(k)) for k, v in sorted(seen.items())
           if ZONES.get(k) != v]
    for k, v in sorted(seen.items()):
        print(f"  {k} -> {v}" + ("" if ZONES.get(k) == v else "  *** MISMATCH"))
    print("  verdict:", "codes match" if not bad else f"MISMATCH {bad}")


def cross_check_actuals(act: pd.DataFrame, h: pd.DataFrame,
                        wb: pd.Series | None = None) -> None:
    """EIA-930 ISNE demand vs ISO-NE's own estimated native load -- as SHARES.

    The outcome variable is a share, so what matters is not whether the two
    sources agree on megawatts but whether they agree on Vermont's fraction of
    New England. Decision rule stated in the output: if the sd of the share gap
    is small next to the sd of the share error being modelled, and the gap does
    not line up with cold nights, EIA-930 stands as the primary actual.
    """
    iso = load_actual_iso()
    if not len(iso):
        print("\nGATE 0b -- no ISO-NE zonal days cached, share cross-check skipped")
        return
    tot_i = iso.groupby(["date", "ord_h"])["mw"].transform("sum")
    n_i = iso.groupby(["date", "ord_h"])["mw"].transform("size")
    iso = iso[n_i == 8].copy()
    iso["s_iso"] = 100.0 * iso.mw / tot_i

    a = act.copy()
    tot_e = a.groupby(["date", "ord_h"])["mw"].transform("sum")
    n_e = a.groupby(["date", "ord_h"])["mw"].transform("size")
    a = a[n_e == 8].copy()
    a["s_eia"] = 100.0 * a.mw / tot_e

    j = iso.merge(a[["date", "ord_h", "region", "s_eia"]],
                  on=["date", "ord_h", "region"], how="inner")
    j["gap"] = j.s_eia - j.s_iso
    print(f"\nGATE 0b -- EIA-930 vs ISO-NE zonal SHARE, "
          f"{j.date.nunique()} sampled days, n={len(j):,} zone-hours")
    for zone in (VT, RI):
        z = j[j.region == zone]
        if not len(z):
            continue
        sd_err = h[(h.region == zone) & h.hb.isin(NIGHT_HOURS)].err_share.std()
        print(f"  {zone}: gap mean {z.gap.mean():+.4f} pp, sd {z.gap.std():.4f} pp"
              f"   |  sd(err_share) {sd_err:.4f} pp"
              f"   -> gap sd is {100*z.gap.std()/sd_err:.0f}% of it")
    if wb is not None and len(wb):
        v = j[j.region == VT].copy()
        v["hb"] = hour_begin(v.ord_h, v.groupby("date")["ord_h"].transform("max"))
        v["ts"] = v.date + pd.to_timedelta(v.hb, unit="h")
        v = v.merge(wb.rename("wb").to_frame(), left_on="ts", right_index=True,
                    how="inner")
        v = v[v.hb.isin(NIGHT_HOURS)]
        if len(v) > 20:
            cold = v.wb < WB_THRESHOLD
            print(f"  Vermont night hours n={len(v):,}: gap on cold hours "
                  f"{v.gap[cold].mean():+.4f} pp vs mild "
                  f"{v.gap[~cold].mean():+.4f} pp "
                  f"(corr with wet bulb {v.gap.corr(v.wb):+.3f})")


# ------------------------------------------------------------- weather -------
def _iem_rwis(station: str, y0: int, y1: int) -> pd.DataFrame:
    p = [("stations", station), ("sts", f"{y0}-10-01T00:00Z"),
         ("ets", f"{y1}-01-01T12:00Z"), ("format", "comma"), ("tz", "UTC")]
    r = requests.get(f"{IEM}/rwis.py", params=p, timeout=600,
                     headers={"User-Agent": "snowmaking-study"})
    if r.status_code != 200 or len(r.text) < 150:
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(r.text), low_memory=False)


def _iem_asos(station: str, network: str, y0: int, y1: int) -> pd.DataFrame:
    p = dict(station=station, data="tmpf,relh", tz="UTC", format="onlycomma",
             latlon="no", missing="empty", trace="empty", direct="no",
             network=network, year1=y0, month1=10, day1=1,
             year2=y1, month2=1, day2=1)
    r = requests.get(f"{IEM}/asos.py", params=p, timeout=600,
                     headers={"User-Agent": "snowmaking-study"})
    if r.status_code != 200 or len(r.text) < 150:
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(r.text), low_memory=False)


def wetbulb_index(which: str = "rwis") -> tuple[pd.Series, pd.DataFrame]:
    """Hourly wet-bulb index, 1 Oct - 31 Dec of each season, local Eastern time.

    Station wet bulbs are computed at that station's own pressure, averaged to
    the hour, then averaged across stations with equal weight. Equal weights,
    not load weights: this is a physical snowmaking-conditions index, and every
    resort makes snow off its own hill.
    """
    d = CACHE / "weather"
    d.mkdir(parents=True, exist_ok=True)
    stations = RWIS if which == "rwis" else [MWN[:3] + ("summit",)]
    per_station = []
    cover = []
    for st in stations:
        sid, name, elev = st[0], st[1], st[2]
        # Cached as CSV rather than pickle: this pipeline is the only writer,
        # but a CSV cache is inspectable and carries no deserialisation risk.
        p = d / f"{which}_{sid}.csv"
        if p.exists():
            raw = pd.read_csv(p, low_memory=False)
        else:
            frames = []
            for y in SEASONS:
                f = (_iem_rwis(sid, y, y + 1) if which == "rwis"
                     else _iem_asos(MWN[0], MWN[3], y, y + 1))
                if len(f):
                    frames.append(f)
                time.sleep(1)
            raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            raw.to_csv(p, index=False)
        if not len(raw):
            cover.append((sid, name, elev, 0, 0))
            continue
        tcol = "tmpf" if "tmpf" in raw else "air_tmp_F"
        rcol = "relh" if "relh" in raw else "relh_%"
        vcol = "obtime" if "obtime" in raw else "valid"
        t_f = pd.to_numeric(raw[tcol], errors="coerce")
        rh = pd.to_numeric(raw[rcol], errors="coerce")
        ts = pd.to_datetime(raw[vcol], errors="coerce", utc=True)
        ok = t_f.notna() & rh.notna() & ts.notna() & rh.between(1, 100)
        t_c = (t_f[ok] - 32.0) * 5.0 / 9.0
        wb = wet_bulb(t_c.to_numpy(), rh[ok].to_numpy(),
                      pressure_from_altitude(elev))
        # Floor in UTC (never ambiguous), then convert and drop the tz to get a
        # naive local wall-clock hour. On the November fall-back Sunday the
        # 01:00 hour then appears twice under the same label and the groupby
        # averages the two, exactly as the Austrian pipeline does.
        loc = ts[ok].dt.floor("h").dt.tz_convert(TZ).dt.tz_localize(None)
        s = pd.Series(wb, index=loc.values).groupby(level=0).mean()
        s.name = sid
        per_station.append(s)
        cover.append((sid, name, elev, int(ok.sum()), s.index.year.nunique()))
    cov = pd.DataFrame(cover, columns=["id", "name", "elev_m", "n_obs", "n_years"])
    if not per_station:
        return pd.Series(dtype=float, name="wb"), cov
    m = pd.concat(per_station, axis=1).sort_index()
    idx = m.mean(axis=1).rename("wb")
    n_st = m.notna().sum(axis=1).rename("n_st")
    idx = idx[n_st >= 1]
    idx = idx[idx.index.month.isin([10, 11, 12])]
    return idx, cov


# ------------------------------------------------------------ share panel ----
def hour_begin(ord_h: pd.Series, n_ord: pd.Series) -> pd.Series:
    """Chronological slot -> local hour-beginning. Normal day: slot k covers
    [k-1, k). Fall-back Sunday has 25 slots and the 01:00 hour twice, so slots
    2 and 3 both begin at 01:00 and everything after shifts by one."""
    hb = ord_h - 1
    dst = n_ord == 25
    hb = hb.where(~dst | (ord_h <= 2), ord_h - 2)
    return hb


def build_hourly(fc_da: pd.DataFrame, act: pd.DataFrame) -> pd.DataFrame:
    """Hourly forecast share and realised share for every zone."""
    f = fc_da.copy()
    f["pct"] = pd.to_numeric(f["pct"], errors="coerce")
    f["mw"] = pd.to_numeric(f["mw"], errors="coerce")
    # integrity: the eight regional shares must sum to 100
    ssum = f.groupby(["date", "ord_h"])["pct"].sum()
    nreg = f.groupby(["date", "ord_h"])["region"].nunique()
    bad = ssum[(ssum - 100).abs() > 0.05].index.union(nreg[nreg != 8].index)
    if len(bad):
        f = f.set_index(["date", "ord_h"]).drop(index=bad, errors="ignore").reset_index()
    f = f.rename(columns={"pct": "f_share", "mw": "f_mw"})

    a = act.copy()
    tot = a.groupby(["date", "ord_h"])["mw"].transform("sum")
    ncnt = a.groupby(["date", "ord_h"])["mw"].transform("size")
    a = a[ncnt == 8].copy()
    a["a_share"] = 100.0 * a.mw / tot
    a = a.rename(columns={"mw": "a_mw"})
    a["a_tot"] = tot

    ft = f.groupby(["date", "ord_h"])["f_mw"].sum().rename("f_tot").reset_index()
    f = f.merge(ft, on=["date", "ord_h"])

    j = f.merge(a[["date", "ord_h", "region", "a_mw", "a_share", "a_tot"]],
                on=["date", "ord_h", "region"], how="inner")
    n_ord = j.groupby("date")["ord_h"].transform("max")
    j["hb"] = hour_begin(j.ord_h, n_ord)
    j["err_share"] = j.a_share - j.f_share            # pp, >0 = share under-forecast
    j["err_mw"] = j.a_mw - j.f_mw
    j["dow"] = j.date.dt.dayofweek
    j["month"] = j.date.dt.month
    j["Y"] = j.date.dt.year
    return j.dropna(subset=["err_share"])


def screen_outliers(h: pd.DataFrame, zone: str, k: float = 5.0) -> pd.DataFrame:
    """Within-night robust screen on the forecast share. The 26 Jan 2026 HE02
    Vermont value (3.927 against ~4.6 neighbours) is the known instance of this
    artifact; the rule finds that shape generically."""
    z = h[h.region == zone].copy()
    z["night_date"] = np.where(z.hb <= 6, z.date - pd.Timedelta(days=1), z.date)
    z = z[z.hb.isin(NIGHT_HOURS)]
    g = z.groupby("night_date")["f_share"]
    med = g.transform("median")
    mad = g.transform(lambda s: (s - s.median()).abs().median())
    keep = ((z.f_share - med).abs() <= k * 1.4826 * mad) | (mad <= 0)
    dropped = int((~keep).sum())
    print(f"  {zone}: outlier screen dropped {dropped} of {len(z)} night-hours "
          f"({100*dropped/max(len(z),1):.2f}%)")
    return z[keep]


# ----------------------------------------------------------------- gate ------
def gate(fc: pd.DataFrame, fc_da: pd.DataFrame, h: pd.DataFrame) -> None:
    print("\n" + "=" * 72)
    print("GATE 1 -- is the regional forecast a rescaled system forecast?")
    print("=" * 72)
    f = fc.copy()
    f["mw"] = pd.to_numeric(f["mw"], errors="coerce")
    f["pct"] = pd.to_numeric(f["pct"], errors="coerce")
    g = f.groupby(["date", "he", "pub"]).agg(tot=("mw", "sum"),
                                             psum=("pct", "sum"),
                                             n=("region", "nunique"))
    g = g[g.n == 8]
    r = (g.tot.round(3) % 10)
    r = np.minimum(r, 10 - r)
    print(f"  (i) hourly 8-zone MW totals, n={len(g):,}")
    print(f"      distance to nearest multiple of 10 MW: "
          f"mean {r.mean():.4f}, p99 {r.quantile(0.99):.4f}, max {r.max():.4f}")
    print(f"      share within 0.01 MW of a multiple of 10: "
          f"{100*(r < 0.01).mean():.2f}%")
    print(f"      (regional shares sum to 100 +- {(g.psum-100).abs().max():.3f})")

    f2 = f.merge(g[["tot"]], left_on=["date", "he", "pub"], right_index=True)
    f2["implied"] = f2.pct / 100.0 * f2.tot
    d = (f2.mw - f2.implied).abs()
    print(f"  (ii) |MW - pct x total|: mean {d.mean():.4f} MW, "
          f"p99 {d.quantile(0.99):.4f}, max {d.max():.3f} MW  "
          f"(n={len(f2):,} zone-hours)")

    # (iii) same target hour, consecutive publications: does the share move?
    v = f[f.region == VT].sort_values(["date", "he", "pub"])
    v["d_pct"] = v.groupby(["date", "he"])["pct"].diff()
    v["d_tot"] = v.groupby(["date", "he"])["mw"].diff()
    rev = v.dropna(subset=["d_pct"])
    same = (rev.d_pct.abs() < 1e-9)
    moved_tot = (rev.d_tot.abs() > 0.5)
    print(f"  (iii) consecutive revisions of the same Vermont target hour, "
          f"n={len(rev):,}")
    print(f"      share byte-identical to 3 dp: {100*same.mean():.1f}%")
    print(f"      of those, MW nonetheless revised >0.5 MW: "
          f"{100*(same & moved_tot).sum()/max(same.sum(),1):.1f}%")
    print("      -> totals and shares refresh on separate cycles")

    # (iv) the share is not static
    for zone in (VT, RI):
        z = fc_da[fc_da.region == zone].copy()
        z["pct"] = pd.to_numeric(z["pct"], errors="coerce")
        w = z[z.date.dt.month.isin(PANEL_MONTHS)]
        print(f"  (iv) {zone} day-ahead share, Nov-Dec: "
              f"min {w.pct.min():.3f}  max {w.pct.max():.3f}  "
              f"mean {w.pct.mean():.3f}  sd {w.pct.std():.3f}")

    # (v) the consequence: decomposition of Vermont MW error
    print("\nGATE 2 -- decomposition of Vermont MW forecast error")
    print("  identity: dMW = s_f*(T_a - T_f) + T_a*(s_a - s_f)/1, i.e.")
    print("            VT MW error = system component + share component.")
    print("  Caveat: T_a and s_a come from EIA-930, T_f and s_f from ISO-NE, so")
    print("  a constant definitional gap between the sources would sit in the")
    print("  system component. The de-meaned line below removes any such gap.")
    v = h[(h.region == VT) & h.hb.isin(NIGHT_HOURS)].copy()
    v["season"] = np.where(v.month >= 10, v.Y, v.Y - 1)
    v["sysc"] = v.f_share / 100.0 * (v.a_tot - v.f_tot)
    v["shrc"] = v.a_tot * (v.a_share - v.f_share) / 100.0
    print(f"\n  night hours n={len(v):,}   identity residual "
          f"{(v.err_mw - v.sysc - v.shrc).abs().max():.6f} MW")
    for lbl, cols in (("raw", ("sysc", "shrc", "err_mw")),
                      ("de-meaned by season x hour", None)):
        if cols is None:
            g = v.groupby(["season", "ord_h"])
            a = v.sysc - g["sysc"].transform("mean")
            b = v.shrc - g["shrc"].transform("mean")
            e = v.err_mw - g["err_mw"].transform("mean")
        else:
            a, b, e = v.sysc, v.shrc, v.err_mw
        print(f"  {lbl:26s}: var(system) {a.var():8.1f}  "
              f"var(share) {b.var():8.1f}  "
              f"-> system {100*a.var()/e.var():5.1f}% / "
              f"share {100*b.var()/e.var():5.1f}% of var(VT MW error)")
    print(f"  corr(VT MW error, system component) = {v.err_mw.corr(v.sysc):.3f}")
    print(f"  corr(VT MW error, share  component) = {v.err_mw.corr(v.shrc):.3f}")


def persistence_baseline(h: pd.DataFrame) -> None:
    """Day-ahead share vs lag-1 realised share.

    A raw MAE comparison would be unfair to the forecast: the realised share
    comes from EIA-930 and the forecast share from ISO-NE, so any constant
    definitional gap between the two sources penalises the forecast while
    cancelling out of persistence, which is EIA-versus-EIA. Both error series
    are therefore also reported after removing their own season x hour-of-day
    mean, which strips exactly that gap and leaves the forecasting question.
    """
    print("\n" + "=" * 72)
    print("BASELINE -- does the day-ahead share beat naive persistence?")
    print("=" * 72)
    for zone in (VT, RI):
        z = h[(h.region == zone) & h.hb.isin(NIGHT_HOURS)].copy()
        z = z.sort_values(["ord_h", "date"])
        z["lag1"] = z.groupby("ord_h")["a_share"].shift(1)
        z["lag2"] = z.groupby("ord_h")["a_share"].shift(2)
        gap = z.groupby("ord_h")["date"].diff().dt.days
        gap2 = z.groupby("ord_h")["date"].diff(2).dt.days
        # Feasible persistence. The chosen vintage publishes ~09:30 on D-1, so
        # for target hours ending at or before 09:00 the same hour of D-1 has
        # already happened and is available; for the evening hours it has not,
        # and the freshest same-hour actual a forecaster could use is from D-2.
        z["feas"] = np.where(z.ord_h <= 9, z.lag1, z.lag2)
        z["feas_ok"] = np.where(z.ord_h <= 9, gap == 1, gap2 == 2)
        z = z[(gap == 1)].dropna(subset=["lag1"]).copy()
        z["season"] = np.where(z.month >= 10, z.Y, z.Y - 1)
        z["e_f"] = z.a_share - z.f_share
        z["e_p"] = z.a_share - z.lag1
        z["e_q"] = np.where(z.feas_ok, z.a_share - z.feas, np.nan)
        key = ["season", "ord_h"]
        for c in ("e_f", "e_p", "e_q"):
            z[c + "_c"] = z[c] - z.groupby(key)[c].transform("mean")

        def skill(a, b):
            return 100 * (1 - a.abs().mean() / b.abs().mean())

        q = z.dropna(subset=["e_q"])
        print(f"\n  {zone}  (n={len(z):,} night-hours with a valid D-1 actual)")
        print(f"    raw       MAE forecast {z.e_f.abs().mean():.4f} pp | "
              f"lag-1 persistence {z.e_p.abs().mean():.4f} pp | "
              f"skill {skill(z.e_f, z.e_p):+.1f}%")
        print(f"    de-biased MAE forecast {z.e_f_c.abs().mean():.4f} pp | "
              f"lag-1 persistence {z.e_p_c.abs().mean():.4f} pp | "
              f"skill {skill(z.e_f_c, z.e_p_c):+.1f}%")
        print(f"    de-biased vs FEASIBLE persistence (D-1 for HE<=9, D-2 for "
              f"evening; n={len(q):,})")
        print(f"              MAE forecast {q.e_f_c.abs().mean():.4f} pp | "
              f"feasible persistence {q.e_q_c.abs().mean():.4f} pp | "
              f"skill {skill(q.e_f_c, q.e_q_c):+.1f}%")
        print(f"    (level gap EIA minus ISO-NE share: "
              f"{z.e_f.mean():+.4f} pp)")
        print(f"    corr(forecast share, lag-1 actual share) = "
              f"{z.f_share.corr(z.lag1):.4f}")
        print(f"    corr(forecast share, same-day actual)    = "
              f"{z.f_share.corr(z.a_share):.4f}")
        # Fri -> Sat: persistence carries Friday's share by construction, so a
        # forecast with any day-type model should beat it here if anywhere.
        # dow 5 = Saturday.
        sat = z[z.dow == 5]
        if len(sat):
            d_act = (sat.a_share - sat.lag1).mean()
            d_fc = (sat.f_share - sat.lag1).mean()
            frac = f"{100*d_fc/d_act:.0f}%" if abs(d_act) > 1e-9 else "n/a"
            print(f"    Fri->Sat transition (n={len(sat):,}):")
            print(f"      actual share moves   {d_act:+.4f} pp off Friday")
            print(f"      forecast share moves {d_fc:+.4f} pp off Friday "
                  f"({frac} of the true move)")
            print(f"      de-biased MAE forecast {sat.e_f_c.abs().mean():.4f} "
                  f"vs persistence {sat.e_p_c.abs().mean():.4f} pp -> skill "
                  f"{100*(1-sat.e_f_c.abs().mean()/sat.e_p_c.abs().mean()):+.1f}%")


# ------------------------------------------------------------ night panel ----
def season_clock() -> pd.DatetimeIndex:
    """Every local hour from 1 Oct 00:00 to 31 Dec 23:00 of each season."""
    parts = [pd.date_range(f"{y}-10-01", f"{y}-12-31 23:00", freq="h")
             for y in SEASONS]
    return pd.DatetimeIndex(np.concatenate([p.values for p in parts]))


MIN_COVERAGE = 90.0     # % of the 1 Oct - 31 Dec hourly clock a season needs


def weather_frame(wb: pd.Series, adjust_coverage: bool = False) -> pd.DataFrame:
    """Wet-bulb series on the complete season clock, with `cum_cold_h`.

    cum_cold_h runs over EVERY hour of the season from 1 Oct, not only night
    hours, and is lagged so the current hour never enters its own regressor.
    This is the raw Austrian count, and the primary sample is restricted to
    seasons whose weather coverage is at least MIN_COVERAGE per cent so that the
    count means the same thing in every season it is used.

    adjust_coverage=True rescales the count by the inverse observation rate. It
    is reported only as a sensitivity: in this dataset the missing hours are not
    missing at random -- the one badly covered season, 2022-23, is missing its
    warm October and November and keeps its cold December -- so the rescaling
    overstates that season rather than repairing it. Restriction, not
    imputation, is the primary treatment.
    """
    w = pd.DataFrame(index=season_clock())
    w["wb"] = wb.reindex(w.index)
    w["season"] = np.where(w.index.month >= 10, w.index.year, w.index.year - 1)
    g = w.groupby("season")
    obs = g["wb"].transform(lambda s: s.notna().shift(1).fillna(False).cumsum())
    cold = g["wb"].transform(
        lambda s: (s < WB_THRESHOLD).shift(1).fillna(False).cumsum())
    elapsed = g.cumcount()
    if adjust_coverage:
        scaled = cold.to_numpy(float) * elapsed.to_numpy(float) / np.where(
            obs.to_numpy(float) > 0, obs.to_numpy(float), np.nan)
        w["cum_cold_h"] = np.nan_to_num(scaled, nan=0.0)
    else:
        w["cum_cold_h"] = cold.to_numpy(float)
    # Must stay float: an object-dtype column would be read as categorical by
    # the formula interface and silently turn cum100 into a set of dummies.
    w["cum_cold_h"] = w["cum_cold_h"].astype(float)
    return w


def weather_coverage(wb: pd.Series) -> pd.DataFrame:
    w = weather_frame(wb)
    r = w.groupby("season").agg(hours=("wb", "size"), observed=("wb", "count"))
    r["coverage"] = (100 * r.observed / r.hours).round(1)
    r["pct_below"] = (100 * w.assign(b=w.wb < WB_THRESHOLD)
                      .groupby("season")["b"].mean()).round(1)
    r["end_cum_cold_h"] = w.groupby("season")["cum_cold_h"].max().round(0)
    return r


def night_panel(h_zone: pd.DataFrame, wb: pd.Series,
                adjust_coverage: bool = False) -> pd.DataFrame:
    """Night-level panel for one zone. Identical construction to Austria: night
    = 20:00-06:59 local labelled by its 20:00 date, >= 8 valid hours, estimation
    at night level so the standard errors count nights not autocorrelated hours.
    """
    w = weather_frame(wb, adjust_coverage)

    z = h_zone.copy()
    z["ts"] = z.date + pd.to_timedelta(z.hb, unit="h")
    z = z.merge(w[["wb", "cum_cold_h", "season"]].dropna(subset=["wb"]),
                left_on="ts", right_index=True, how="inner")
    g = z.groupby("night_date")
    p = pd.DataFrame({
        "n_hours": g.size(),
        "err": g["err_share"].mean(),
        "err_mw": g["err_mw"].mean(),
        "a_share": g["a_share"].mean(),
        "f_share": g["f_share"].mean(),
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
    return p[p.month.isin(PANEL_MONTHS)].reset_index(drop=True)


def estimate(p: pd.DataFrame, label: str, extra: str = "", quiet: bool = False):
    """Austrian specification, HC1 standard errors. Outcome is the night-mean
    share error in percentage points."""
    import statsmodels.formula.api as smf
    if len(p) < 40 or p.below.nunique() < 2 or len(p) == 0:
        if not quiet:
            print(f"\n=== {label} -- too few observations (n={len(p)}), skipped ===")
        return None
    d = p.copy()
    d["cum100"] = (d.cum_cold_h - d.cum_cold_h.median()) / 100.0
    d["doy_c"] = (d.doy - d.doy.mean()) / 10.0
    f = ("err ~ below * cum100 + dist + below:dist + holiday "
         "+ doy_c + I(doy_c**2) + C(season) + C(dow)" + extra)
    m = smf.ols(f, data=d).fit(cov_type="HC1")
    keep = [t for t in m.params.index
            if any(k in t for k in ("below", "cum100", "dist", "holiday",
                                    "campaign"))]
    # Built by hand rather than via summary2(), which computes an F statistic
    # that raises under HC1 when the design is thin.
    if not quiet:
        tab = pd.DataFrame({"Coef.": m.params, "Std.Err.": m.bse,
                            "z": m.tvalues, "P>|z|": m.pvalues}).loc[keep]
        print(f"\n=== {label}  (n={int(m.nobs)}, "
              f"seasons {sorted(d.season.unique())}) ===")
        print(tab.round(4).to_string())
        k = "below:cum100"
        if k in m.params.index:
            print(f"  PRIMARY {k} = {m.params[k]:+.4f} pp per 100 h  "
                  f"(HC1 s.e. {m.bse[k]:.4f}, z {m.tvalues[k]:+.2f}, "
                  f"p = {m.pvalues[k]:.3f})")
    return m


# ------------------------------------------------------------------ main -----
def main() -> None:
    print("ISO-NE VERMONT snowmaking test -- outcome variable is the SHARE")
    print(f"seasons {min(SEASONS)}-{max(SEASONS)+1}, months {PANEL_MONTHS}, "
          f"night 20:00-06:59 local, wet-bulb threshold {WB_THRESHOLD} C")

    verify_zone_codes()

    print("\nloading ISO-NE reliability-region forecast ...")
    fc = load_forecast()
    print(f"  {len(fc):,} rows, {fc.date.nunique()} target dates, "
          f"{fc.date.min().date()} .. {fc.date.max().date()}")
    fc_da = day_ahead_vintage(fc)
    got = set(fc_da.date.unique())
    print(f"  day-ahead vintage (latest publication <= {DAM_CUTOFF} on D-1): "
          f"{len(got)} dates kept, {fc.date.nunique()-len(got)} dropped")
    print("  chosen publication time of day: "
          + fc_da.pub.dt.strftime("%H:%M").value_counts().head(4).to_dict().__str__())

    print("\nloading EIA-930 ISNE actuals ...")
    act = load_actual()
    print(f"  {len(act):,} zone-hours, {act.date.min().date()} .. "
          f"{act.date.max().date()}")

    h = build_hourly(fc_da, act)
    print(f"\nmatched hourly panel: {len(h):,} zone-hours over "
          f"{h.date.nunique()} dates")

    print("\n" + "=" * 72)
    print("WEATHER -- elevated Vermont wet-bulb index")
    print("=" * 72)
    wb, cov = wetbulb_index("rwis")
    print(cov.to_string(index=False))
    print(f"  hourly index: {len(wb):,} hours, "
          f"{100*(wb < WB_THRESHOLD).mean():.1f}% below {WB_THRESHOLD} C")
    print("\n  season coverage of the complete 1 Oct - 31 Dec hourly clock:")
    wcov = weather_coverage(wb)
    print(wcov.to_string())
    good_seasons = wcov.index[wcov.coverage >= MIN_COVERAGE].tolist()
    dropped = [s for s in SEASONS if s not in good_seasons]
    print(f"  primary sample keeps seasons {good_seasons}; "
          f"drops {dropped} for weather coverage below {MIN_COVERAGE:.0f}%")

    cross_check_actuals(act, h, wb)
    gate(fc, fc_da, h)
    persistence_baseline(h)

    for zone in (VT, RI):
        tag = "MAIN -- VERMONT" if zone == VT else "PLACEBO -- RHODE ISLAND"
        print("\n" + "=" * 72)
        print(f"{tag}   (outcome: realised share - day-ahead share, pp)")
        print("=" * 72)
        z = screen_outliers(h, zone)
        allp = night_panel(z, wb)
        if not len(allp):
            print("  empty panel"); continue
        p = allp[allp.season.isin(good_seasons)].reset_index(drop=True)
        print(f"  primary sample: {len(p)} nights, seasons {good_seasons}, "
              f"{int(p.below.sum())} below-threshold nights, "
              f"{int(p.campaign_start.sum())} campaign starts")
        print(f"  ({len(allp)} nights before the weather-coverage restriction)")
        print(f"  mean share error {p.err.mean():+.4f} pp "
              f"(sd {p.err.std():.4f}); mean realised share {p.a_share.mean():.3f}%")
        # Anchor so coefficients in pp can be read as megawatts.
        zn = h[(h.region == zone) & h.hb.isin(NIGHT_HOURS)]
        mw_per_pp = zn.a_tot.mean() / 100.0
        print(f"  scale: mean night system load {zn.a_tot.mean():,.0f} MW, "
              f"so 1 pp of share = {mw_per_pp:,.0f} MW; "
              f"sd of the night share error = {p.err.std()*mw_per_pp:,.1f} MW")
        allp.to_csv(OUTDIR / f"night_panel_{zone.replace('.Z.','').lower()}.csv",
                    index=False)
        estimate(p, f"{tag}: PRIMARY, Nov-Dec all nights")
        estimate(p[p.dist.abs() <= 3], f"{tag}: bandwidth |wb+2| <= 3 C")
        estimate(p, f"{tag}: with campaign-start dummy",
                 extra=" + campaign_start")
        estimate(p, f"{tag}: campaign start + second night",
                 extra=" + campaign_start + campaign_night2")
        estimate(allp, f"{tag}: sensitivity, all seasons incl. low-coverage")
        estimate(night_panel(z, wb, adjust_coverage=True),
                 f"{tag}: sensitivity, coverage-rescaled cum_cold_h")

    # All eight zones on the identical specification. Shares are compositional --
    # the eight share errors sum to zero by construction -- so a real Vermont
    # effect must mechanically push the other seven the other way. Spread in
    # proportion to zone size that back-reaction is small in any one zone, so the
    # diagnostic question is whether Vermont stands out from the field or is one
    # half of a two-zone see-saw. The placebo is only interpretable next to this.
    print("\n" + "=" * 72)
    print("ALL EIGHT ZONES -- same specification, primary sample")
    print("=" * 72)
    rows = []
    for zone in sorted(set(ZONES.values())):
        pz = night_panel(screen_outliers(h, zone), wb)
        pz = pz[pz.season.isin(good_seasons)]
        m = estimate(pz, f"zone {zone}", quiet=True)
        if m is not None and "below:cum100" in m.params.index:
            rows.append((zone, m.params["below:cum100"], m.bse["below:cum100"],
                         m.pvalues["below:cum100"], pz.a_share.mean()))
    if rows:
        t = pd.DataFrame(rows, columns=["zone", "below:cum100", "HC1 s.e.",
                                        "p", "mean share %"])
        t["|z|"] = (t["below:cum100"] / t["HC1 s.e."]).abs()
        print("\n  below:cum100 across all eight reliability regions "
              "(pp per 100 cold hours)")
        print(t.sort_values("below:cum100", ascending=False)
              .round(4).to_string(index=False))
        print(f"  sum of the eight coefficients: "
              f"{t['below:cum100'].sum():+.4f} pp "
              f"(compositional constraint puts this near zero)")

    # robustness: swap the actual series for ISO-NE's own zonal load on the one
    # season its report still archives, so forecast and outcome share a
    # publisher and no cross-source definition can be doing the work.
    iso_act = load_actual_iso()
    if len(iso_act) > 1000:
        print("\n" + "=" * 72)
        print("ROBUSTNESS -- ISO-NE's own zonal actuals (same publisher)")
        print("=" * 72)
        h_iso = build_hourly(fc_da, iso_act)
        seas = sorted(set(np.where(h_iso.month >= 10, h_iso.Y, h_iso.Y - 1)))
        print(f"  {len(h_iso):,} zone-hours over {h_iso.date.nunique()} dates, "
              f"season(s) {seas}")
        for zone in (VT, RI):
            p_iso = night_panel(screen_outliers(h_iso, zone), wb)
            keep = set(p_iso.night_date)
            p_eia = night_panel(screen_outliers(h, zone), wb)
            p_eia = p_eia[p_eia.night_date.isin(keep)]
            print(f"\n  {zone}: mean share error, ISO actuals "
                  f"{p_iso.err.mean():+.4f} pp vs EIA actuals "
                  f"{p_eia.err.mean():+.4f} pp on the same "
                  f"{len(p_iso)} nights")
            estimate(p_iso, f"ISO-NE own actuals -- {zone}")
            estimate(p_eia, f"EIA-930 actuals, same nights -- {zone}")

    # robustness: true summit station, covers every season including the one
    # the VTrans RWIS archive is missing.
    print("\n" + "=" * 72)
    print("ROBUSTNESS -- Mount Washington (1910 m) wet-bulb index")
    print("=" * 72)
    wb2, cov2 = wetbulb_index("mwn")
    print(cov2.to_string(index=False))
    if len(wb2):
        print(f"  hourly index: {len(wb2):,} hours, "
              f"{100*(wb2 < WB_THRESHOLD).mean():.1f}% below {WB_THRESHOLD} C")
        print("\n  season coverage:")
        print(weather_coverage(wb2).to_string())
        for zone in (VT, RI):
            p = night_panel(screen_outliers(h, zone), wb2)
            estimate(p, f"MWN index -- {zone} (all seasons)")


if __name__ == "__main__":
    main()
