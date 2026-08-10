#!/usr/bin/env python
"""Cache ISO New England hourly demand for the ten-season supply slope.

src/revision/README.md section 11 registers a re-estimate of the overnight
supply slope on this arm's ten seasons rather than inheriting the six-season
figure from src/price/README.md section 10.3. That needs an ISO-NE load series
reaching 2016, and the EIA-930 SUBREGION files the Vermont pipeline caches begin
in 2019.

The BALANCE files reach further back. `EIA930_BALANCE_YYYY_Jul_Dec.csv` carries
`Demand (MW)` per balancing authority per hour, and both 2016 and 2018 were
confirmed to answer 200 with that column present before this script was written.
November and December sit entirely inside the Jul-Dec half, so one file per
season is enough.

Two things this deliberately does NOT do:
  * it does not mix sources across seasons. Price 10.3 summed the SUBREGION
    files; using BALANCE for all ten seasons keeps one definition throughout,
    and the two are compared on the overlapping seasons rather than assumed
    equal.
  * it does not subtract wind and solar. EIA-930 has no split for ISNE, which
    price 10.3 already recorded as a deviation: the slope is against total load,
    which biases it toward zero and so overstates the implied impact. That is
    the safe direction for a gate whose job is to declare the test underpowered.

Each file is ~40 MB and is discarded after the ISNE rows are kept, so the cache
holds a few thousand rows per season rather than a few hundred thousand.

    python fetch_isne_load.py
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fetch_afm import CACHE                                  # noqa: E402

OUT = CACHE.parent / "isne_load"
OUT.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/"
SEASONS = range(2016, 2026)
BA = "ISNE"


def one(year: int) -> int:
    dst = OUT / f"isne_{year}.csv"
    if dst.exists():
        return -1
    name = f"EIA930_BALANCE_{year}_Jul_Dec.csv"
    r = requests.get(BASE + name, timeout=1800, headers={"User-Agent": UA})
    if not r.ok or len(r.content) < 100_000:
        print(f"  {name}: {r.status_code}, {len(r.content)} bytes", flush=True)
        return 0
    df = pd.read_csv(io.BytesIO(r.content), dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    isne = df[df["Balancing Authority"] == BA]
    keep = [c for c in ("Balancing Authority", "Data Date", "Hour Number",
                        "Local Time at End of Hour", "UTC Time at End of Hour",
                        "Demand (MW)", "Demand Forecast (MW)",
                        "Net Generation (MW)") if c in isne.columns]
    isne[keep].to_csv(dst, index=False)
    return len(isne)


def load() -> pd.DataFrame:
    """Hourly ISNE demand on the local clock, hour-BEGINNING, Nov-Dec only.

    EIA-930 labels the hour by its END, and the day-ahead LMP panel this joins
    to is hour-beginning, so one hour is subtracted. Getting that wrong shifts
    the night window by an hour and silently changes the slope.
    """
    frames = []
    for f in sorted(OUT.glob("isne_*.csv")):
        d = pd.read_csv(f)
        t = pd.to_datetime(d["Local Time at End of Hour"], errors="coerce",
                           format="mixed")
        d = d.assign(t_end=t).dropna(subset=["t_end"])
        d["t_begin"] = d.t_end - pd.Timedelta(hours=1)
        d["demand_mw"] = pd.to_numeric(d["Demand (MW)"], errors="coerce")
        frames.append(d[["t_begin", "demand_mw"]].dropna())
    if not frames:
        return pd.DataFrame(columns=["t_begin", "demand_mw"])
    x = pd.concat(frames, ignore_index=True)
    return x[x.t_begin.dt.month.isin((11, 12))].reset_index(drop=True)


def main() -> None:
    got = skipped = 0
    for y in SEASONS:
        n = one(y)
        if n < 0:
            skipped += 1
        elif n:
            got += 1
            print(f"  {y}: {n:,} ISNE rows", flush=True)
        time.sleep(1.0)
    x = load()
    print(f"{got} downloaded, {skipped} already cached")
    if len(x):
        print(f"{len(x):,} Nov-Dec hours, "
              f"{x.t_begin.min()} .. {x.t_begin.max()}")
        print(f"demand {x.demand_mw.min():,.0f} .. {x.demand_mw.max():,.0f} MW")


if __name__ == "__main__":
    main()
