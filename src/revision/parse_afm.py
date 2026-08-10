#!/usr/bin/env python
"""Parse cached AFMBTV products into one row per (issuance, zone, valid period).

The Area Forecast Matrix is fixed-width. Each zone block carries a header pair

    EST 3hrly     04 07 10 13 16 19 22 01 ...
    UTC 3hrly     09 12 15 18 21 00 03 06 ...

and the 12-hour rows (`PoP 12hr`, `QPF 12hr`, `Snow 12hr`) place one value per
12-hour period, right-aligned on the column of the UTC hour the period ENDS at.
That alignment is not documented anywhere I could find; it is inferred from the
fact that the values land on the 00Z and 12Z columns, which are the standard
12-hourly period ends. `--audit` prints the alignment so the inference can be
checked rather than trusted.

Snow values are inch ranges like `00-00`, `01-03`, `T` for trace, or blank when
the period is beyond the quantitative range. A blank is NOT zero and is kept as
missing; treating it as zero would manufacture revisions out of the forecast
horizon rolling forward.

    python parse_afm.py            # writes afm_snow.csv
    python parse_afm.py --audit    # show the column alignment on one product
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "afm"
OUT = HERE / "afm_snow.csv"

# The Green Mountain spine runs up the eastern side of the western counties, so
# the "Eastern <county>" zones are the ones holding the resorts.
RESORT_ZONES = {
    "Eastern Rutland": "Killington / Pico",
    "Eastern Addison": "Sugarbush / Mad River Glen",
    "Eastern Franklin": "Jay Peak",
    "Eastern Chittenden": "Bolton / Stowe approach",
    "Lamoille": "Stowe / Smugglers' Notch",
    "Washington": "Sugarbush / Northfield",
    "Western Windsor": "Okemo / Killington south",
    "Orange": "central Green Mountains",
}

ZONE_RE = re.compile(r"^[A-Z]{2}Z\d")
UTC_RE = re.compile(r"^UTC\s+(\d+)hrly\s", re.I)
SNOW_RE = re.compile(r"^snow\s+12hr", re.I)
ISSUE_RE = re.compile(r"^\s*\w{6}\s+KBTV\s+(\d{6})\s*$")


def utc_columns(line: str) -> list[tuple[int, int]]:
    """(column index of the token's last char, UTC hour) for a header row."""
    return [(m.end() - 1, int(m.group(0))) for m in re.finditer(r"\d{2}", line[10:])
            ] if False else [
        (m.end() - 1 + 10, int(m.group(0))) for m in re.finditer(r"\d{2}", line[10:])]


def snow_tokens(line: str) -> list[tuple[int, str]]:
    """(column index of the token's last char, token) for a Snow 12hr row."""
    body = line[10:]
    return [(m.end() - 1 + 10, m.group(0))
            for m in re.finditer(r"\S+", body)]


def parse_product(text: str) -> list[dict]:
    lines = text.splitlines()
    stamp = None
    for l in lines[:6]:
        m = ISSUE_RE.match(l)
        if m:
            stamp = m.group(1)          # DDHHMM, UTC
            break
    rows, zone, cols, span = [], None, [], None
    for i, l in enumerate(lines):
        if ZONE_RE.match(l):
            zone = lines[i + 1].strip().rstrip("-")
            cols, span = [], None
            continue
        m = UTC_RE.match(l)
        if m:
            span = int(m.group(1))
            cols = utc_columns(l)
            continue
        if SNOW_RE.match(l) and zone and cols:
            for pos, tok in snow_tokens(l):
                # attach the value to the nearest header column at or after it
                best = min(cols, key=lambda c: abs(c[0] - pos))
                if abs(best[0] - pos) > 2:
                    continue
                rows.append({"zone": zone, "span_h": span,
                             "end_utc_hour": best[1], "col": best[0],
                             "raw": tok})
    for r in rows:
        r["ddhhmm"] = stamp
    return rows


def to_inches(tok: str) -> float | None:
    tok = tok.strip()
    if not tok:
        return None
    if tok.upper() == "T":
        return 0.05                     # trace, nominal
    m = re.fullmatch(r"(\d+)-(\d+)", tok)
    if m:
        return (int(m.group(1)) + int(m.group(2))) / 2.0
    m = re.fullmatch(r"(\d+)", tok)
    return float(m.group(1)) if m else None


def audit() -> None:
    f = sorted(CACHE.glob("*.txt"))[len(list(CACHE.glob("*.txt"))) // 2]
    print(f"auditing {f.name}\n")
    lines = f.read_text(encoding="utf-8").splitlines()
    for i, l in enumerate(lines):
        if SNOW_RE.match(l):
            # search back for the UTC header rather than assuming an offset;
            # the number of rows between them varies by product vintage.
            j = next(k for k in range(i, -1, -1) if UTC_RE.match(lines[k]))
            print("UTC :", repr(lines[j]))
            print("SNOW:", repr(l))
            cols = utc_columns(lines[j])
            toks = snow_tokens(l)
            print("\n  header columns:", cols[:8])
            print("  snow tokens   :", toks[:8])
            for pos, tok in toks[:6]:
                best = min(cols, key=lambda c: abs(c[0] - pos))
                print(f"    token {tok!r:>10} at col {pos:>3} -> "
                      f"UTC {best[1]:02d} (col {best[0]}, off by {pos-best[0]:+d})")
            return


def main() -> None:
    files = sorted(CACHE.glob("*.txt"))
    print(f"{len(files)} cached products")
    out = []
    for f in files:
        try:
            rows = parse_product(f.read_text(encoding="utf-8"))
        except Exception as e:                       # noqa: BLE001
            print(f"  {f.name}: {e}")
            continue
        for r in rows:
            r["product"] = f.stem
        out += rows
    d = pd.DataFrame(out)
    if not len(d):
        print("nothing parsed"); return
    d["inches"] = d["raw"].map(to_inches)
    d["issued_utc"] = pd.to_datetime(
        d["product"].str.slice(0, 12), format="%Y%m%d%H%M", utc=True)
    print(f"{len(d):,} rows, {d["zone"].nunique()} zones, "
          f"{d["product"].nunique()} issuances")
    print(f"issued {d["issued_utc"].min()} .. {d["issued_utc"].max()}")
    r = d[d["zone"].isin(RESORT_ZONES)]
    print(f"\nresort zones: {len(r):,} rows over {r["zone"].nunique()} zones")
    print(r.groupby("zone").agg(rows=("raw", "size"),
                                nonzero=("inches", lambda s: int((s > 0).sum())),
                                missing=("inches", lambda s: int(s.isna().sum()))
                                ).to_string())
    d.to_csv(OUT, index=False)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    audit() if "--audit" in sys.argv else main()
