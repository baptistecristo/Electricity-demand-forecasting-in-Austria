#!/usr/bin/env python
"""Cache NWS Burlington Area Forecast Matrices (AFMBTV) for the Vermont panel.

The AFM is the zone-level sibling of the Point Forecast Matrix. It matters here
because its zones are split east/west along the Green Mountain spine -- Eastern
Rutland is Killington, Eastern Addison is Sugarbush and Mad River, Eastern
Franklin and Lamoille are Jay and Smugglers' -- whereas every PFM point is a
valley town between 93 and 334 m, lower than the RWIS stations the load test
already calls too low.

Each issuance carries a `Snow 12hr` row per zone, in inches, and NWS Burlington
issues 6 to 10 a day. Successive issuances for the same valid period are a
genuine forecast revision, which is the treatment variable this is being
collected for.

Two format facts found by inspection rather than assumed:
  * the row is `Snow 12hr` in modern products and `SNOW 12HR` in older ones, so
    every parser here is case-insensitive. An exact-case match silently returns
    nothing on ten years of data.
  * `retrieve.py` answers "Could not Find: AFMBTV"; the JSON API works.

    python fetch_afm.py

Products are cached one file per issuance and never refetched.
"""
from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path

import requests

CACHE = Path(r"C:\Users\bcris\.claude-snow\jobs\11224758\tmp\revision\afm")
CACHE.mkdir(parents=True, exist_ok=True)

LIST = "https://mesonet.agron.iastate.edu/api/1/nws/afos/list.json"
TEXT = "https://mesonet.agron.iastate.edu/api/1/nwstext/{}"
PIL = "AFMBTV"
PACE = 0.4                       # IEM is a research service; be polite

# Seasons 2016..2025. The panel is Nov-Dec, but a revision for the night of
# 1 November needs issuances from late October, so the window opens on 29 Oct.
SEASONS = range(2016, 2026)


def target_dates() -> list[dt.date]:
    out = []
    for y in SEASONS:
        d, end = dt.date(y, 10, 29), dt.date(y, 12, 31)
        while d <= end:
            out.append(d)
            d += dt.timedelta(days=1)
    return out


def get(url: str, **params) -> requests.Response | None:
    for k in range(4):
        try:
            r = requests.get(url, params=params or None, timeout=180)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        time.sleep(2 * (k + 1))
    return None


def main() -> None:
    dates = target_dates()
    print(f"{len(dates)} dates, seasons {min(SEASONS)}-{max(SEASONS)}", flush=True)
    n_new = n_have = n_miss = 0
    for i, d in enumerate(dates):
        day = d.strftime("%Y-%m-%d")
        marker = CACHE / f"_list_{day}.done"
        if marker.exists():
            n_have += 1
            continue
        r = get(LIST, cccc="KBTV", date=day)
        if r is None:
            n_miss += 1
            print(f"  {day}: list failed", flush=True)
            continue
        ids = [x["product_id"] for x in r.json().get("data", [])
               if x.get("pil", "").strip() == PIL]
        time.sleep(PACE)
        for pid in ids:
            f = CACHE / f"{pid}.txt"
            if f.exists():
                continue
            t = get(TEXT.format(pid))
            if t is None:
                n_miss += 1
                continue
            f.write_text(t.text, encoding="utf-8")
            n_new += 1
            time.sleep(PACE)
        marker.write_text(str(len(ids)), encoding="utf-8")
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(dates)} dates, {n_new} products cached",
                  flush=True)
    print(f"done: {n_new} new, {n_have} dates already done, {n_miss} misses",
          flush=True)
    print(f"cache holds {len(list(CACHE.glob('*.txt')))} products", flush=True)


if __name__ == "__main__":
    main()
