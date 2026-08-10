#!/usr/bin/env python3
"""
fetch_entsoe.py -- ENTSO-E imbalance acquisition for the Austrian control area.

Acquisition and provenance only. This script downloads, caches, parses and
describes. It estimates nothing. No coefficient, standard error or p-value is
produced here or by anything it imports.

Why imbalance
-------------
Root README section 9 lists imbalance as the one untried instrument. APG
publishes its day-ahead load forecast at 08:00 on D-1 and the day-ahead auction
clears around noon. Information arriving after those two gates cannot be in
either the forecast or the day-ahead price, and it has nowhere to land except
imbalance. At PT15M this is the finest-grained outcome available anywhere in
this project.

Series
------
  A85  Imbalance prices              [17.1.F]   controlArea_Domain
  A86  Total imbalance volumes       [17.1.G]   controlArea_Domain

Both are confirmed continuous for AT from 2014 to 2025 by probing 1 December of
each year. Twelve seasons, against six for the load panel and ten for Vermont.

Four format facts found by inspection rather than assumed
--------------------------------------------------------
Each of these produces a wrong answer silently. None of them raises.

1. **A85 and A86 return a ZIP, not XML.** The body starts with `PK`. A parser
   that regexes the response text for a tag finds nothing and reports the series
   as empty when the data is there. The archive holds one member,
   `001-IMBALANCE_PRICES_R3_<start>-<end>.xml` or
   `001-TOTAL_IMBALANCE_VOLUMES_R3_...`. The load (A65) and price (A44)
   endpoints return plain XML, so one code path does not serve both.

2. **A85 carries no `<quantity>` tag at all.** Its values are
   `<imbalance_Price.amount>`, alongside an `<imbalance_Price.category>`. A
   probe written against `<quantity>` reports zero points for every year of a
   complete archive. That is how this file's first draft "established" that A85
   was unavailable 2014-2025. It is available; the regex was wrong.

3. **`position` restarts at 1 inside every `<Period>`, and A86 uses many
   Periods.** On 2023-12-01 the AT document splits the day into 23 Period blocks
   across two TimeSeries, one per contiguous run of a single flow direction:
   00:00-05:45 in one, 05:45-06:00 in the next, and so on. They tile the day
   exactly, 96 quarter-hours in total. The timestamp of a point is therefore

       Period.start + (position - 1) * resolution

   and NOT an offset from the requested `periodStart`. A parser that assumes one
   Period per TimeSeries and indexes from the document start still emits exactly
   96 values with plausible magnitudes, in scrambled order. This is the most
   dangerous of the four because the output passes every count check.

4. **`curveType` is A03, so a missing position is not missing data.** A03 is
   "variable sized block": a point holds its value until the next given
   position. A85 on 2023-12-01 carries 95 points for 96 slots. Dropping the gap
   loses a quarter-hour; forward-filling to the next stated position recovers
   it. Treating the gap as absent, or as zero, would be an error in the outcome
   variable itself.

5. **A44 publishes the same December at two resolutions.** For AT in December
   2023 the day-ahead price document carries 2,970 PT15M points and 760 PT60M
   points side by side. A parser that does not filter on `resolution` interleaves
   quarter-hourly and hourly prices into one series and then silently keeps
   whichever `drop_duplicates` happens to see first. Pick a resolution
   explicitly.

6. **Season 2014 carries no directional information, and the direction codes are
   not stable across the sample.** Counting points by `flowDirection.direction`:

       2014-10   A01 2,973   A03 1                  (of 2,976 quarter-hours)
       2014-11   A01 2,878                          (of 2,880)
       2014-12   A01 2,970   A02 3   A03 3
       2015-10   A01 1,865   A02 1,111
       2016-10   A01 1,922   A02 1,052   A03 1

   A control area is short roughly half the time, so 2015 onward is the credible
   pattern and 2014 is not. The obvious hypothesis is that 2014 signs the value
   inside a single direction, and it is wrong: every 2014 quantity is
   non-negative (minimum 0.0 across all three months). The 2014 series is an
   unsigned magnitude with a constant direction label, and a signed outcome built
   from it reads as permanently short.

   **The usable panel therefore starts in season 2015: eleven seasons, not
   twelve.** A rare third code `A03` also appears, one to three points a month;
   those quarter-hours are kept and flagged rather than assigned a sign.

   This is the trap that would have cost the most. Nothing raises, the row counts
   are correct, and 2014 contributes a season of always-short nights to whichever
   side of the interaction it happens to load on.

Sign convention, established from the data
------------------------------------------
A86 splits on `flowDirection.direction`, A01 and A02, and the mapping to short
and long is NOT assumed here. `--check-sign` reads it off the data. The decisive
test is within the quarter-hour: when the control area is short the TSO is
buying, so the imbalance price must sit above the day-ahead price, and that
comparison does not depend on which direction happens to fall in expensive hours.

Over December 2023, imbalance price minus day-ahead price, 2,976 quarter-hours:

    A01   mean +54.78   median +30.92   positive in 86.4% of intervals
    A02   mean -51.84   median -39.06   positive in  6.4% of intervals

**A01 is system SHORT (deficit). A02 is system LONG (surplus).** Recorded here
before any signed aggregate is built, because this project has already published
one pre-registered sign backwards and the correction cost more than the check.

Austria settles on a single imbalance price: categories A04 and A05 carry
identical values, so the long and short prices are the same number and either
one may be used.

Token
-----
Read from `ENTSOE_TOKEN` in the environment, or from `.env` at the repository
root, which `.gitignore` covers. The token is never written to the cache, never
included in a cached filename, and never printed.

    python fetch_entsoe.py --probe        # which zones and years serve
    python fetch_entsoe.py --check-sign   # establish the A86 sign convention
    python fetch_entsoe.py                # fetch + cache + write tidy CSVs
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

API = "https://web-api.tp.entsoe.eu/api"

# The cache holds raw archive members. It sits outside the repository: these are
# bulk third-party files and the repository is public.
CACHE = Path(r"C:\Users\bcris\snow\entsoe-cache")
OUT = Path(__file__).resolve().parent

# Control-area EICs. AT is the subject; the rest are controls and are probed
# rather than assumed to serve, because control-area and bidding-zone EICs are
# not interchangeable for the 17.1 series.
ZONES = {
    "AT": "10YAT-APG------L",
    "CH": "10YCH-SWISSGRIDZ",
    "NL": "10YNL----------L",
    "DK1": "10YDK-1--------W",
}

# Season runs 1 October to 31 December, matching `season = year if month >= 10`
# in src/apg_pipeline.py and the 1 October origin of cum_cold_h.
SEASONS = range(2014, 2026)
PACE = 1.0


# ----------------------------------------------------------------------------
# token
# ----------------------------------------------------------------------------
def token() -> str:
    t = os.environ.get("ENTSOE_TOKEN")
    if t:
        return t.strip()
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ENTSOE_TOKEN"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("Set ENTSOE_TOKEN in the environment or in .env at the repo root.")


# ----------------------------------------------------------------------------
# transport
# ----------------------------------------------------------------------------
def _body(r: requests.Response) -> str:
    """Return the XML, unwrapping the ZIP that the 17.1 endpoints answer with."""
    if r.content[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        if len(names) != 1:
            # Not fatal, but the shape assumed everywhere below is one member.
            print(f"    note: archive holds {len(names)} members, reading all")
        return "\n".join(z.read(n).decode("utf-8", "replace") for n in names)
    return r.content.decode("utf-8", "replace")


def fetch(doc: str, eic: str, start: str, end: str, tok: str) -> str | None:
    params = {"securityToken": tok, "documentType": doc,
              "controlArea_Domain": eic, "periodStart": start, "periodEnd": end}
    for k in range(4):
        try:
            r = requests.get(API, params=params, timeout=180)
        except Exception:
            time.sleep(3 * (k + 1))
            continue
        if r.status_code == 200:
            return _body(r)
        if r.status_code == 429:
            time.sleep(20 * (k + 1))
            continue
        # 400 with an Acknowledgement is a real "no data", not a transport fault
        if r.status_code == 400:
            return _body(r)
        time.sleep(3 * (k + 1))
    return None


# ----------------------------------------------------------------------------
# parsing
# ----------------------------------------------------------------------------
def _f(block: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    return m.group(1).strip() if m else None


_STEP = {"PT15M": pd.Timedelta(minutes=15), "PT30M": pd.Timedelta(minutes=30),
         "PT60M": pd.Timedelta(hours=1), "P1D": pd.Timedelta(days=1)}


def parse(xml: str) -> pd.DataFrame:
    """One row per quarter-hour per TimeSeries, timestamps in UTC.

    Handles fact 3 (position is relative to its own Period) and fact 4 (A03
    means a value holds until the next stated position).
    """
    rows: list[dict] = []
    for ts in re.findall(r"<TimeSeries>(.*?)</TimeSeries>", xml, re.S):
        flow = _f(ts, "flowDirection.direction")
        curve = _f(ts, "curveType")
        btype = _f(ts, "businessType")
        for per in re.findall(r"<Period>(.*?)</Period>", ts, re.S):
            p_start = pd.Timestamp(_f(per, "start"))
            p_end = pd.Timestamp(_f(per, "end"))
            res = _f(per, "resolution")
            step = _STEP.get(res)
            if step is None:
                raise ValueError(f"unhandled resolution {res!r}")
            slots = int((p_end - p_start) / step)
            pts = []
            for pt in re.findall(r"<Point>(.*?)</Point>", per, re.S):
                # Three documents, three value tags, and none of them share a
                # name: A86 uses <quantity>, A85 <imbalance_Price.amount>, A44
                # <price.amount>. Fact 2 above is this same trap; it is listed
                # once but it bites once per document type.
                val = (_f(pt, "quantity") or _f(pt, "imbalance_Price.amount")
                       or _f(pt, "price.amount"))
                if val is None:
                    raise ValueError(
                        "no recognised value tag in Point: "
                        + re.sub(r"\s+", " ", pt)[:120])
                pts.append((int(_f(pt, "position")), float(val),
                            _f(pt, "imbalance_Price.category")))
            pts.sort()
            for i, (pos, val, cat) in enumerate(pts):
                # A03: hold this value until the next stated position, or to the
                # end of the Period for the last point. For A01 (contiguous)
                # this loop runs exactly once per point, so one code path serves.
                stop = pts[i + 1][0] if i + 1 < len(pts) else slots + 1
                if curve != "A03":
                    stop = pos + 1
                for q in range(pos, stop):
                    rows.append({"ts_utc": p_start + (q - 1) * step,
                                 "value": val, "flow": flow, "category": cat,
                                 "business": btype, "resolution": res,
                                 "filled": q != pos})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# modes
# ----------------------------------------------------------------------------
def probe(tok: str) -> None:
    """Which control areas serve 17.1.F and 17.1.G, and how far back."""
    for name, eic in ZONES.items():
        for doc in ("A85", "A86"):
            hits = []
            for y in (2014, 2018, 2022, 2025):
                xml = fetch(doc, eic, f"{y}12010000", f"{y}12020000", tok)
                n = 0 if xml is None else len(parse(xml)) if "<Point>" in xml else 0
                hits.append(f"{y}:{n}")
                time.sleep(PACE)
            print(f"  {name:4s} {doc}  " + "  ".join(hits))


def check_sign(tok: str) -> None:
    """Read the A86 flow-direction convention off the data.

    Prints, for one December week, the mean day-ahead price in quarter-hours
    labelled A01 against those labelled A02. The direction that coincides with
    the higher price is the system-short direction. Nothing downstream assumes
    which that is.
    """
    eic = ZONES["AT"]
    xml = fetch("A86", eic, "202312010000", "202312080000", tok)
    if xml is None:
        print("  A86 fetch failed"); return
    v = parse(xml)
    print(f"  {len(v)} quarter-hours, "
          f"{v['ts_utc'].min()} .. {v['ts_utc'].max()}")
    print(f"  filled by A03 hold: {int(v['filled'].sum())}")
    print("\n  volume by flow direction (MWh per quarter-hour):")
    print(v.groupby("flow")["value"].agg(["size", "mean", "max"]).round(1)
           .to_string())

    time.sleep(PACE)
    # day-ahead price for the same week, A44, plain XML on in_Domain/out_Domain
    p = {"securityToken": tok, "documentType": "A44",
         "in_Domain": "10YAT-APG------L", "out_Domain": "10YAT-APG------L",
         "periodStart": "202312010000", "periodEnd": "202312080000"}
    r = requests.get(API, params=p, timeout=180)
    price = parse(_body(r))
    if price.empty:
        print("\n  day-ahead price returned no points; sign left unresolved")
        return
    # A44 is hourly and the imbalance series is quarter-hourly. An inner join on
    # the timestamp would silently keep only the :00 quarter-hours and throw
    # away three quarters of the sample, so the hourly price is held across its
    # own hour instead.
    price = (price.rename(columns={"value": "eur_mwh"})[["ts_utc", "eur_mwh"]]
                  .drop_duplicates("ts_utc").set_index("ts_utc").sort_index())
    v = v.copy()
    v["hour"] = v["ts_utc"].dt.floor("h")
    m = v.merge(price, left_on="hour", right_index=True, how="inner")
    print(f"\n  merged on {len(m)} quarter-hours "
          f"({price.index.size} hourly prices held across their hour)")
    print(m.groupby("flow")["eur_mwh"].agg(["size", "mean"]).round(2).to_string())
    print("\n  The direction with the HIGHER mean day-ahead price is the")
    print("  system-short direction. Record it in the README before any")
    print("  signed aggregate is built.")


def collect(tok: str) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    frames = {"A85": [], "A86": []}
    for y in SEASONS:
        for doc in ("A85", "A86"):
            for m0 in (10, 11, 12):
                m1, y1 = (m0 + 1, y) if m0 < 12 else (1, y + 1)
                s = f"{y}{m0:02d}010000"
                e = f"{y1}{m1:02d}010000"
                f = CACHE / f"{doc}_AT_{y}{m0:02d}.xml"
                if not f.exists():
                    xml = fetch(doc, ZONES["AT"], s, e, tok)
                    if xml is None:
                        print(f"  {doc} {y}-{m0:02d}: fetch failed")
                        continue
                    f.write_text(xml, encoding="utf-8")
                    time.sleep(PACE)
                d = parse(f.read_text(encoding="utf-8"))
                if d.empty:
                    print(f"  {doc} {y}-{m0:02d}: no points")
                    continue
                frames[doc].append(d)
                print(f"  {doc} {y}-{m0:02d}: {len(d):,} quarter-hours")
    for doc, fr in frames.items():
        if not fr:
            continue
        d = pd.concat(fr, ignore_index=True).sort_values("ts_utc")
        path = OUT / f"at_{'prices' if doc == 'A85' else 'volumes'}.csv"
        d.to_csv(path, index=False)
        print(f"wrote {path}  ({len(d):,} rows, "
              f"{d['ts_utc'].min()} .. {d['ts_utc'].max()})")
        if doc == "A86":
            # Season 2014 is written out with everything else because this
            # script acquires and does not judge, but it must not be used. See
            # fact 6: its direction label is constant and its values are all
            # non-negative, so a signed outcome built from it reads as
            # permanently short. The share below is printed every run so the
            # defect cannot be missed by someone reading only the CSV.
            y = d["ts_utc"].dt.year
            for season in sorted(y.unique()):
                s = d[y == season]
                top = s["flow"].value_counts(normalize=True)
                if len(top) and top.iloc[0] > 0.95:
                    print(f"  WARNING season {season}: {100*top.iloc[0]:.1f}% of "
                          f"quarter-hours carry direction {top.index[0]}. "
                          f"No directional information. Drop this season.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--check-sign", action="store_true")
    a = ap.parse_args()
    tok = token()
    if a.probe:
        probe(tok)
    elif a.check_sign:
        check_sign(tok)
    else:
        collect(tok)


if __name__ == "__main__":
    main()
