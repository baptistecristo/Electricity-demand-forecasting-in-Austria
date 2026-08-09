#!/usr/bin/env python3
"""
fetch_lmp.py -- ISO New England DAY-AHEAD hourly zonal LMP acquisition.

Companion to src/vermont/vt_pipeline.py. Acquisition and provenance only: this
script downloads, caches, reshapes and describes. It estimates nothing.

Source report
-------------
ISO Express > Pricing > "Day-Ahead Energy Market Hourly LMP Report"
  report tree page (also the required Referer):
    https://www.iso-ne.com/isoexpress/web/reports/pricing/-/tree/lmps-da-hourly
  one static CSV per operating day:
    https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/WW_DALMP_ISO_YYYYMMDD.csv

Every file opens with the two lines that identify the market and the fields:

    "C","Day-Ahead Energy Market Hourly LMP Report"
    "H","Date","Hour Ending","Location ID","Location Name","Location Type",
        "Locational Marginal Price","Energy Component","Congestion Component",
        "Marginal Loss Component"

so the series is the DAY-AHEAD market by the report's own title, and the price
field is the settled day-ahead LMP with its three published components. The
real-time equivalents are separate reports (lmps-rt-hourly-final /
lmps-rt-five-minute-final) and are not touched here.

Access notes, inherited from vt_pipeline.py's `_iso_get()`
---------------------------------------------------------
  * The per-day CSV endpoints on iso-ne.com want a session cookie obtained from
    the report tree page AND a `Referer` header naming that page. Either one
    alone can answer 403. One session is opened on the tree page and reused for
    the whole run, with the Referer set on every request.
  * Pace ~9-11 s between requests. A 403 wall means back off hard (20 s, 40 s,
    60 s), never hammer.
  * Some ISO-NE endpoints answer 200 with a well-formed but empty CSV. A day is
    only accepted here if it carries LOAD ZONE D-rows for both target zones.

Caching
-------
The raw daily file is ~2.5 MB (every network node). Only the comment/header
lines and the eight LOAD ZONE D-rows are written to cache (~25 KB/day), which
is what the panel needs and keeps the cache inspectable.

    python fetch_lmp.py            # fetch (resumable) + build CSVs + provenance
    python fetch_lmp.py --no-fetch # rebuild outputs from cache only
"""
from __future__ import annotations

import io
import json
import random
import sys
import time
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# --------------------------------------------------------------- settings ---
OUT = Path(r"C:\Users\bcris\.claude-snow\jobs\11224758\tmp\price\isone")
CACHE = OUT / "cache"

SEASONS = range(2019, 2026)      # winter 2019-20 .. 2025-26
PANEL_MONTHS = (11, 12)          # required window
EXTRA_MONTHS = (10,)             # October, fetched after the required window
TZ = "America/New_York"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
REF_DALMP = ("https://www.iso-ne.com/isoexpress/web/reports/pricing/-/tree/"
             "lmps-da-hourly")
URL_DALMP = ("https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/"
             "WW_DALMP_ISO_{}.csv")

VT, RI = ".Z.VERMONT", ".Z.RHODEISLAND"
ZONES = {"4001": ".Z.MAINE", "4002": ".Z.NEWHAMPSHIRE", "4003": ".Z.VERMONT",
         "4004": ".Z.CONNECTICUT", "4005": ".Z.RHODEISLAND",
         "4006": ".Z.SEMASS", "4007": ".Z.WCMASS", "4008": ".Z.NEMASSBOST"}

COLS = ["date_s", "he", "loc_id", "loc_name", "loc_type",
        "lmp_usd_mwh", "energy", "congestion", "loss"]

_SESSION: requests.Session | None = None


# ------------------------------------------------------------- fetching -----
def _session() -> requests.Session:
    """One session for the run. The cookie set by the report tree page is what
    the CSV endpoint checks; the Referer must name the same page."""
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Referer": REF_DALMP})
        s.get(REF_DALMP, timeout=60)
        time.sleep(1.0 + random.random())
        _SESSION = s
    return _SESSION


def _reset_session() -> None:
    global _SESSION
    if _SESSION is not None:
        _SESSION.close()
    _SESSION = None


def fetch_day(day: str, tries: int = 4) -> str | None:
    """Raw text of one day's Day-Ahead Hourly LMP report, or None."""
    for k in range(tries):
        try:
            r = _session().get(URL_DALMP.format(day), timeout=300)
            if r.status_code == 200 and r.text.startswith('"C"'):
                return r.text
            if r.status_code == 404:
                return None            # genuinely not in the archive
        except Exception:
            pass
        _reset_session()               # 403 wall: new cookie, and back off
        time.sleep(20 * (k + 1))
    return None


def _zone_slice(text: str) -> str | None:
    """Keep the C/H provenance lines and the LOAD ZONE D-rows only."""
    lines = text.splitlines()
    head = [L for L in lines if L.startswith('"C"') or L.startswith('"H"')]
    zrows = [L for L in lines if L.startswith('"D"') and '"LOAD ZONE"' in L]
    if len(zrows) < 8 * 23:            # 8 zones x >=23 hours
        return None
    return "\n".join(head + zrows) + "\n"


def target_dates(months=PANEL_MONTHS) -> list[str]:
    out = []
    for y in SEASONS:
        for m in months:
            d = dt.date(y, m, 1)
            while d.month == m:
                out.append(d.strftime("%Y%m%d"))
                d += dt.timedelta(days=1)
    return sorted(out)


def ensure_cache(dates: list[str], pace: float = 9.0) -> tuple[int, list[str]]:
    """Resumable paced download. Returns (n_fetched, failures)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    todo = [d for d in dates if not (CACHE / f"{d}.csv").exists()]
    fails: list[str] = []
    if not todo:
        return 0, fails
    print(f"fetching {len(todo)} days (~{len(todo)*(pace+3)/60:.0f} min) ...",
          flush=True)
    for i, day in enumerate(todo):
        txt = fetch_day(day)
        z = _zone_slice(txt) if txt else None
        if z is None:
            fails.append(day)
            print(f"  MISS {day}", flush=True)
        else:
            (CACHE / f"{day}.csv").write_text(z, encoding="utf-8")
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(todo)}", flush=True)
        time.sleep(pace + random.random() * 2)
    return len(todo) - len(fails), fails


# -------------------------------------------------------------- parsing -----
def _parse(text: str) -> pd.DataFrame:
    rows = [L for L in text.splitlines() if L.startswith('"D"')]
    if not rows:
        return pd.DataFrame(columns=COLS)
    # date_s / he / loc_id must stay strings: '01' is an hour label, not the
    # integer 1, and the fall-back Sunday's repeated hour is labelled '02X'.
    f = pd.read_csv(io.StringIO("\n".join(rows)), header=None,
                    names=["tag"] + COLS,
                    dtype={"date_s": str, "he": str, "loc_id": str,
                           "loc_name": str, "loc_type": str})
    return f.drop(columns="tag")


def hour_begin(ord_h: pd.Series, n_ord: pd.Series) -> pd.Series:
    """Chronological slot -> local hour-beginning. Normal day: slot k covers
    [k-1, k). Fall-back Sunday has 25 slots and the 01:00 hour twice, so slots
    2 and 3 both begin at 01:00 and everything after shifts by one.

    Verbatim from src/vermont/vt_pipeline.py -- do not re-derive."""
    hb = ord_h - 1
    dst = n_ord == 25
    hb = hb.where(~dst | (ord_h <= 2), ord_h - 2)
    return hb


def load_panel() -> pd.DataFrame:
    """All cached days, LOAD ZONE rows, with the chronological hour ordinal.

    The published Hour Ending label is '02X' for the repeated hour on the
    November fall-back Sunday. Sorting on (numeric part, X flag) puts it
    straight after '02', so the running count within (date, zone) is the
    chronological slot in the day -- the same construction load_forecast()
    uses in vt_pipeline.py, and the input hour_begin() expects."""
    frames = []
    for p in sorted(CACHE.glob("*.csv")):
        f = _parse(p.read_text(encoding="utf-8"))
        if len(f):
            frames.append(f)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df.date_s, format="%m/%d/%Y")
    df["he"] = df.he.astype(str).str.strip()
    df["he_n"] = df.he.str.extract(r"(\d+)").astype(int)
    df["he_x"] = df.he.str.contains("X").astype(int)
    df = df.sort_values(["date", "loc_name", "he_n", "he_x"])
    df["ord_h"] = df.groupby(["date", "loc_name"]).cumcount() + 1
    n_ord = df.groupby(["date", "loc_name"])["ord_h"].transform("max")
    df["hb"] = hour_begin(df.ord_h, n_ord)
    for c in ("lmp_usd_mwh", "energy", "congestion", "loss"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def zone_csv(df: pd.DataFrame, zone: str, path: Path) -> pd.DataFrame:
    z = df[df.loc_name == zone].copy()
    z["date"] = z.date.dt.strftime("%Y-%m-%d")
    out = z[["date", "ord_h", "he", "hb", "lmp_usd_mwh",
             "energy", "congestion", "loss"]].rename(
        columns={"he": "he_published", "energy": "energy_usd_mwh",
                 "congestion": "congestion_usd_mwh", "loss": "loss_usd_mwh"})
    out = out.sort_values(["date", "ord_h"]).reset_index(drop=True)
    out.to_csv(path, index=False)
    return out


# ----------------------------------------------------------- provenance -----
def season_of(d: pd.Series) -> pd.Series:
    return np.where(d.dt.month >= 10, d.dt.year, d.dt.year - 1)


def expected_hours(season: int, months) -> int:
    """Complete local clock for the months kept, counting the extra hour of the
    November fall-back Sunday."""
    n = 0
    for m in months:
        y = season
        days = (dt.date(y, m % 12 + 1, 1) if m < 12 else dt.date(y + 1, 1, 1)) \
            - dt.date(y, m, 1)
        n += days.days * 24
        if m == 11:
            n += 1                      # 25-hour Sunday
    return n


def main(do_fetch: bool = True, with_october: bool = True) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fails: list[str] = []
    if do_fetch:
        n1, f1 = ensure_cache(target_dates(PANEL_MONTHS))
        fails += f1
        print(f"Nov-Dec: {n1} newly cached, {len(f1)} misses", flush=True)
        if with_october:
            n2, f2 = ensure_cache(target_dates(EXTRA_MONTHS))
            fails += f2
            print(f"October: {n2} newly cached, {len(f2)} misses", flush=True)
        (OUT / "fetch_failures.json").write_text(json.dumps(fails, indent=1),
                                                encoding="utf-8")

    df = load_panel()
    if not len(df):
        print("no cached data")
        return
    vt = zone_csv(df, VT, OUT / "lmp_vermont.csv")
    ri = zone_csv(df, RI, OUT / "lmp_rhodeisland.csv")
    print(f"wrote lmp_vermont.csv ({len(vt):,} rows), "
          f"lmp_rhodeisland.csv ({len(ri):,} rows)")
    print(f"dates {df.date.min().date()} .. {df.date.max().date()}, "
          f"{df.date.nunique()} days cached")


if __name__ == "__main__":
    main(do_fetch="--no-fetch" not in sys.argv)
