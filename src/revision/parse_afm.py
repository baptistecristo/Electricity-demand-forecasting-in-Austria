#!/usr/bin/env python
"""Parse cached AFMBTV products into one row per (issuance, zone, valid period).

The Area Forecast Matrix is fixed-width. Each zone block carries a header trio

    Date             Sat 12/05/20            Sun 12/06/20            Mon 12/07/20
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

WHAT THIS EMITS, AND WHY IT IS MORE THAN SNOW
---------------------------------------------
src/revision/README.md section 9 conditions the snowfall revision on the
*temperature* revision measured over the same period, in the same zone, from the
same product. Without that column the design does not separate a snow forecast
from the cold front carrying it. So every row also carries a wet-bulb built from
the 3-hourly `Temp` and `RH` rows of the same block, via the bisection solver in
src/apg_pipeline.py -- imported rather than copied, so it stays verbatim.

The 12-hour temperature row is NOT used. It is `MIN/MAX` on an evening issuance
and `MAX/MIN` on a morning one, because the label names the two periods in the
order they arrive, so a parser keyed on a fixed order silently swaps minima for
maxima on half the archive. `Temp` and `RH` carry no such ordering.

Wet bulb needs a station pressure and a forecast zone has no elevation. A
nominal 600 m is used. The design consumes wb only as a *difference* between two
issuances at the same nominal elevation, so the assumption very nearly cancels;
it would matter if wb were the treatment, and it is not.

ABSOLUTE TIME, WHICH CANNOT BE TAKEN FROM THE ISSUANCE STAMP
------------------------------------------------------------
The matrix begins at a 3-hour boundary *before* the issuance, and not at a fixed
offset from it: a product issued 01:39Z opens at 21Z the previous day (4h39m
earlier) and one issued 10:55Z opens at 09Z the same day (1h55m earlier). Walking
forward from the issuance time therefore misdates the whole grid.

Instead the grid is anchored on the first date in the `Date` row and the local
hours in the `EST/EDT 3hrly` row, incrementing the day whenever the hour wraps.
The row's own label supplies the UTC offset, so the November fall-back needs no
timezone database and no guessing. The reconstruction is then checked against the
`UTC 3hrly` row on every product, and a product whose two headers disagree is
dropped and counted rather than trusted.

    python parse_afm.py            # writes afm_snow.csv
    python parse_afm.py --audit    # show the column alignment on one product
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from apg_pipeline import pressure_from_altitude, wet_bulb   # noqa: E402

sys.path.insert(0, str(HERE))
from fetch_afm import CACHE                                 # noqa: E402

# CACHE is imported rather than re-declared. The two scripts used to name the
# cache separately -- the fetcher an absolute scratch path, the parser
# `src/revision/afm` -- so running the pair from the repository root wrote
# thousands of products to one directory and then reported "0 cached products"
# from another, without either script raising.
# Beside the cache, not in the repository. Raw and intermediate data are never
# committed here; the committed artefacts are this script and the write-up.
OUT = CACHE.parent / "afm_snow.csv"

# A forecast zone has no elevation; see the docstring. Only differences of wb
# are consumed downstream, so this cancels to first order.
NOMINAL_ALT_M = 600.0
P_HPA = float(pressure_from_altitude(NOMINAL_ALT_M))

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
# README section 6: the primary treatment averages these four.
CORE_ZONES = ("Eastern Rutland", "Eastern Addison",
              "Eastern Franklin", "Lamoille")

ZONE_RE = re.compile(r"^[A-Z]{2}Z\d")
DATE_RE = re.compile(r"^date\s", re.I)
LOCAL_RE = re.compile(r"^(E[SD]T)\s+(\d+)hrly\s", re.I)
UTC_RE = re.compile(r"^UTC\s+(\d+)hrly\s", re.I)
SNOW_RE = re.compile(r"^snow\s+12hr", re.I)
TEMP_RE = re.compile(r"^temp\s", re.I)
RH_RE = re.compile(r"^rh\s", re.I)
MDY_RE = re.compile(r"(\d{2})/(\d{2})/(\d{2})")

BODY = 10                       # fixed-width label field; data starts here
OFFSET = {"EST": 5, "EDT": 4}   # hours to ADD to local to get UTC


def utc_columns(line: str) -> list[tuple[int, int]]:
    """(column index of the token's last char, hour) for a 3hrly header row."""
    return [(m.end() - 1 + BODY, int(m.group(0)))
            for m in re.finditer(r"\d{2}", line[BODY:])]


def snow_tokens(line: str) -> list[tuple[int, str]]:
    """(column index of the token's last char, token) for any value row."""
    return [(m.end() - 1 + BODY, m.group(0))
            for m in re.finditer(r"\S+", line[BODY:])]


def at_columns(line: str | None, cols: list[tuple[int, int]]) -> list[str | None]:
    """Values of a WIDE row (the 12-hour rows) aligned to each header column.

    Safe for `Snow 12hr` because those values sit twelve columns apart with runs
    of blanks between them.
    """
    out: list[str | None] = [None] * len(cols)
    if line is None:
        return out
    for pos, tok in snow_tokens(line):
        k = min(range(len(cols)), key=lambda j: abs(cols[j][0] - pos))
        if abs(cols[k][0] - pos) <= 2:
            out[k] = tok
    return out


def at_columns_narrow(line: str | None,
                      cols: list[tuple[int, int]]) -> list[str | None]:
    """Values of a 3-HOURLY row, read by fixed-width slice rather than by
    splitting on whitespace.

    `RH` is the reason. Its fields are two characters right-aligned on the
    header column, so a reading of 100 needs three and swallows the space that
    separates it from its neighbour:

        RH            92 96100 92

    Splitting on whitespace turns `96100` into one token, drops a step, and does
    it precisely on saturated air -- the humid nights this design is about. The
    three-character window ending on the header column recovers both readings,
    and also handles a three-character negative temperature like `-12`.
    """
    out: list[str | None] = [None] * len(cols)
    if line is None:
        return out
    for k, (c, _) in enumerate(cols):
        tok = line[max(c - 2, 0):c + 1].strip()
        out[k] = tok or None
    return out


def grid_times(first_date: dt.date, local_hours: list[int],
               tzlabel: str) -> list[dt.datetime]:
    """Absolute UTC time of each header column. See the docstring: anchored on
    the Date row and the local-hour row, never on the issuance stamp."""
    add = OFFSET[tzlabel.upper()]
    out, day, prev = [], first_date, None
    for h in local_hours:
        if prev is not None and h <= prev:
            day += dt.timedelta(days=1)
        out.append(dt.datetime.combine(day, dt.time(h))
                   + dt.timedelta(hours=add))
        prev = h
    return out


def to_f(tok: str | None) -> float | None:
    if not tok:
        return None
    m = re.fullmatch(r"-?\d+", tok.strip())
    return float(m.group(0)) if m else None


def to_inches(tok: str | None, lower: bool = False) -> float | None:
    """Midpoint of an inch range, or its lower bound when `lower`."""
    if tok is None:
        return None
    tok = tok.strip()
    if not tok:
        return None
    if tok.upper() == "T":
        return 0.0 if lower else 0.05          # trace, nominal
    m = re.fullmatch(r"(\d+)-(\d+)", tok)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return float(lo) if lower else (lo + hi) / 2.0
    m = re.fullmatch(r"(\d+)", tok)
    return float(m.group(1)) if m else None


def zone_blocks(lines: list[str]):
    """Yield (zone_name, block_lines) for each zone section of a product."""
    starts = [i for i, l in enumerate(lines) if ZONE_RE.match(l)]
    for a, i in enumerate(starts):
        j = starts[a + 1] if a + 1 < len(starts) else len(lines)
        if i + 1 < len(lines):
            yield lines[i + 1].strip().rstrip("-"), lines[i:j]


def parse_block(zone: str, block: list[str]) -> tuple[list[dict], bool]:
    """Rows for one zone's 3-hourly section. Second element is False when the
    reconstructed grid disagrees with the product's own UTC header row."""
    first_date = local_hours = tzlabel = None
    cols: list[tuple[int, int]] = []
    utc_hours: list[int] = []
    temp_line = rh_line = snow_line = None

    for l in block:
        if first_date is None and DATE_RE.match(l):
            m = MDY_RE.search(l)
            if m:
                mm, dd, yy = (int(x) for x in m.groups())
                first_date = dt.date(2000 + yy, mm, dd)
            continue
        m = LOCAL_RE.match(l)
        if m and local_hours is None:
            if int(m.group(2)) != 3:        # 3-hourly section only
                break
            tzlabel = m.group(1)
            local_hours = [int(x.group(0)) for x in
                           re.finditer(r"\d{2}", l[BODY:])]
            continue
        m = UTC_RE.match(l)
        if m and not cols:
            if int(m.group(1)) != 3:
                break
            cols = utc_columns(l)
            utc_hours = [h for _, h in cols]
            continue
        if not cols:
            continue
        if TEMP_RE.match(l) and temp_line is None:
            temp_line = l
        elif RH_RE.match(l) and rh_line is None:
            rh_line = l
        elif SNOW_RE.match(l) and snow_line is None:
            snow_line = l

    if not (first_date and local_hours and cols) or snow_line is None:
        return [], True
    if len(local_hours) != len(cols):
        return [], False

    times = grid_times(first_date, local_hours, tzlabel)
    if [t.hour for t in times] != utc_hours:
        return [], False                     # headers disagree: drop, count it

    temps = [to_f(t) for t in at_columns_narrow(temp_line, cols)]
    rhs = [to_f(t) for t in at_columns_narrow(rh_line, cols)]
    snows = at_columns(snow_line, cols)

    rows = []
    for k, tok in enumerate(snows):
        if tok is None or cols[k][1] not in (0, 12):
            continue                          # 12-hour periods end 00Z / 12Z
        lo = k - 3                            # 4 x 3h = the 12-hour period
        idx = [j for j in range(max(lo, 0), k + 1)]
        ok = [j for j in idx if temps[j] is not None and rhs[j] is not None]
        tt = [temps[j] for j in ok]
        rr = [rhs[j] for j in ok]
        rows.append({
            "zone": zone,
            "valid_end_utc": times[k],
            "lead_cols": k,
            "raw": tok,
            "snow_in": to_inches(tok),
            "snow_in_lo": to_inches(tok, lower=True),
            "temp_f": float(np.mean(tt)) if tt else None,
            "n_steps": len(tt),
            # Wet bulb is solved once for the whole archive in wetbulb_column();
            # per-row solving costs 50 bisection iterations on a 4-element array
            # and turns a one-minute parse into a half-hour one.
            "_t_f": tuple(tt),
            "_rh": tuple(rr),
        })
    return rows, True


def wetbulb_column(d: pd.DataFrame) -> pd.Series:
    """Mean wet bulb over the 3-hourly steps of each 12-hour period, in C.

    Every step in the archive goes into one array and through the solver once.
    Wet bulb is not linear in temperature, so the mean is taken AFTER solving,
    never before -- averaging the temperatures first and solving once would be
    cheaper still and would be wrong.
    """
    rowid, tf, rh = [], [], []
    for i, (ts, rs) in enumerate(zip(d["_t_f"], d["_rh"])):
        for a, b in zip(ts, rs):
            rowid.append(i)
            tf.append(a)
            rh.append(b)
    if not rowid:
        return pd.Series(np.nan, index=d.index)
    tc = (np.asarray(tf, float) - 32.0) * 5.0 / 9.0
    wb = wet_bulb(tc, np.asarray(rh, float), P_HPA)
    s = pd.Series(wb).groupby(pd.Series(rowid)).mean()
    out = pd.Series(np.nan, index=range(len(d)))
    out.loc[s.index] = s.values
    out[d["n_steps"].to_numpy() < 3] = np.nan     # need 3 of the 4 steps
    out.index = d.index
    return out


def parse_product(text: str) -> tuple[list[dict], int]:
    lines = text.splitlines()
    out, bad = [], 0
    for zone, block in zone_blocks(lines):
        rows, ok = parse_block(zone, block)
        if not ok:
            bad += 1
        out += rows
    return out, bad


def audit() -> None:
    files = sorted(CACHE.glob("*.txt"))
    f = files[len(files) // 2]
    print(f"auditing {f.name}\n")
    lines = f.read_text(encoding="utf-8").splitlines()
    zone, block = next(iter(zone_blocks(lines)))
    date_l = next(l for l in block if DATE_RE.match(l))
    loc_l = next(l for l in block if LOCAL_RE.match(l))
    utc_l = next(l for l in block if UTC_RE.match(l))
    snow_l = next(l for l in block if SNOW_RE.match(l))
    print(f"zone: {zone}")
    for name, l in (("DATE", date_l), ("LOCAL", loc_l),
                    ("UTC ", utc_l), ("SNOW", snow_l)):
        print(f"{name}: {l!r}")

    cols = utc_columns(utc_l)
    print("\n  header columns:", cols[:8])
    print("  snow tokens   :", snow_tokens(snow_l)[:8])
    for pos, tok in snow_tokens(snow_l)[:6]:
        best = min(cols, key=lambda c: abs(c[0] - pos))
        print(f"    token {tok!r:>10} at col {pos:>3} -> "
              f"UTC {best[1]:02d} (col {best[0]}, off by {pos-best[0]:+d})")

    m = MDY_RE.search(date_l)
    mm, dd, yy = (int(x) for x in m.groups())
    lm = LOCAL_RE.match(loc_l)
    lh = [int(x.group(0)) for x in re.finditer(r"\d{2}", loc_l[BODY:])]
    times = grid_times(dt.date(2000 + yy, mm, dd), lh, lm.group(1))
    print(f"\n  reconstructed from the {lm.group(1)} row, first 8 columns:")
    for t, (_, h) in list(zip(times, cols))[:8]:
        flag = "ok" if t.hour == h else "MISMATCH"
        print(f"    {t:%Y-%m-%d %H:%M}Z   header says {h:02d}Z   {flag}")
    agree = [t.hour for t in times] == [h for _, h in cols]
    print(f"\n  whole grid agrees with the UTC header row: {agree}")

    rows, bad = parse_product("\n".join(lines))
    print(f"  product yields {len(rows)} rows, {bad} unusable zone blocks")
    fr = pd.DataFrame(rows)
    fr["wb_c"] = wetbulb_column(fr)
    for _, r in fr.head(4).iterrows():
        wb = "n/a" if pd.isna(r.wb_c) else f"{r.wb_c:.2f} C"
        print(f"    {r.zone:<22} {r.valid_end_utc:%Y-%m-%d %H}Z  "
              f"snow={r.raw!r:>8} -> {r.snow_in}  "
              f"wb={wb} ({r.n_steps} steps)")


def main() -> None:
    files = sorted(CACHE.glob("*.txt"))
    print(f"{len(files)} cached products")
    out, bad_blocks, bad_files = [], 0, 0
    for f in files:
        try:
            rows, bad = parse_product(f.read_text(encoding="utf-8"))
        except Exception as e:                       # noqa: BLE001
            print(f"  {f.name}: {e}")
            bad_files += 1
            continue
        bad_blocks += bad
        for r in rows:
            r["product"] = f.stem
        out += rows
    d = pd.DataFrame(out)
    if not len(d):
        print("nothing parsed")
        return
    d["wb_c"] = wetbulb_column(d)
    d = d.drop(columns=["_t_f", "_rh"])
    d["issued_utc"] = pd.to_datetime(
        d["product"].str.slice(0, 12), format="%Y%m%d%H%M", utc=True)
    d["valid_end_utc"] = pd.to_datetime(d["valid_end_utc"], utc=True)
    d["lead_h"] = ((d.valid_end_utc - d.issued_utc)
                   .dt.total_seconds() / 3600.0).round(2)

    print(f"{len(d):,} rows, {d['zone'].nunique()} zones, "
          f"{d['product'].nunique()} issuances")
    print(f"issued {d['issued_utc'].min()} .. {d['issued_utc'].max()}")
    print(f"dropped {bad_blocks} zone blocks whose two header rows disagreed, "
          f"{bad_files} unreadable files")
    print(f"lead time: {d.lead_h.min():.0f} .. {d.lead_h.max():.0f} h, "
          f"median {d.lead_h.median():.0f} h")
    print(f"wet bulb present on {100*d.wb_c.notna().mean():.1f}% of rows")

    r = d[d["zone"].isin(RESORT_ZONES)]
    print(f"\nresort zones: {len(r):,} rows over {r['zone'].nunique()} zones")
    print(r.groupby("zone").agg(
        rows=("raw", "size"),
        nonzero=("snow_in", lambda s: int((s > 0).sum())),
        ge2in=("snow_in", lambda s: int((s >= 2).sum())),
        missing=("snow_in", lambda s: int(s.isna().sum())),
        wb_mean=("wb_c", "mean")).round(2).to_string())

    c = d[d["zone"].isin(CORE_ZONES)]
    if len(c):
        print(f"\nfour core zones: {len(c):,} rows, "
              f"{100*(c.snow_in > 0).mean():.1f}% non-zero, "
              f"{100*(c.snow_in >= 2).mean():.1f}% >= 2 in, "
              f"max {c.snow_in.max()} in")
    d.to_csv(OUT, index=False)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    audit() if "--audit" in sys.argv else main()
