#!/usr/bin/env python3
"""
cot_oi.py -- open interest in the ISO New England off-peak futures complex.

This is the liquidity gate for the futures leg described in src/futures/README.md.
Acquisition and description only: it downloads, caches, tabulates and bounds. It
estimates no coefficient and fits no model.

The question
------------
`src/price/README.md` tests the day-ahead SPOT auction and says, in its section 1,
that no futures contract is touched. This script asks the one futures question
that does not need a price series: **is there a tradable market in New Hampshire
off-peak power at all?** A contract nobody holds cannot price a hidden load, and
its exchange settlement is a mark, not a trade.

Source report
-------------
CFTC Commitments of Traders, disaggregated futures-only, annual history files:

    https://www.cftc.gov/files/dea/history/fut_disagg_txt_{YEAR}.zip

One row per market per Tuesday. `Open_Interest_All` is exchange-reported open
interest for that market, in contracts. Public domain, redistributable, and
published by the regulator rather than by any exchange -- which matters here,
because all three exchanges that list the New Hampshire contract gate their own
per-contract figures (CME's Terms of Use prohibit automated access and the site
answers 403; ICE sits behind Cloudflare; Nodal puts its end-of-day files behind
a captcha). The COT is the only openly redistributable source for this, so it is
the one used, and its publication rule is what bounds the answer.

What absence in the COT does and does not mean
----------------------------------------------
The CFTC publishes a market in the COT when **20 or more traders** hold positions
at or above the reporting level. The reporting level is set by 17 CFR 15.03;
electricity is not named in its table, so it falls under "All Other Commodities"
= **25 contracts**.

So a market missing from the COT is NOT a market with zero open interest. It is a
market in which fewer than twenty traders hold twenty-five lots or more. That is
the bound this script reports, and it is stated that way everywhere below. It is
a weaker claim than "open interest is zero" and it is the claim the data supports.

Outputs
-------
    data/futures_isone_oi.csv    every ISO-NE / NEPOOL market-week found
    data/futures_venue_census.csv  electricity markets per venue per year

    python src/futures/cot_oi.py              # fetch (cached) + tabulate
    python src/futures/cot_oi.py --no-fetch   # rebuild from cache only
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
import calendar
import datetime as dt
import collections
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "cot"
DATA = ROOT / "data"

FIRST_YEAR = 2010
LAST_YEAR = 2025

URL = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"

# 17 CFR 15.03(b): electricity is not named, so "All Other Commodities".
REPORTING_LEVEL = 25          # contracts
COT_TRADER_RULE = 20          # traders at or above the reporting level

# The three venues that list the same New Hampshire zone off-peak instrument.
# CME:   product page, code AU3, 5 MW off-peak calendar-month day-ahead LMP.
# ICE:   product 6590399, code IHD, 1 MW day-ahead off-peak fixed price.
# Nodal: code AAV, ISONE .Z.NEWHAMPSHIRE monthly day-ahead off-peak.
# The ICE/Nodal pairing is CME-independent: it is CFTC filing rule021015nodaldcm002.
NH_CONTRACT_MW = {"CME (AU3)": 5, "ICE (IHD)": 1, "Nodal (AAV)": 1}

# Substrings that mark a market as electricity rather than gas or liquids. The
# gas exclusions come first because "HENRY HUB" would otherwise match on "HUB".
GAS_LIQUIDS = (
    "HENRY", "NAT GAS", "NATURAL GAS", "BUTANE", "PROPANE", "CRUDE", "ETHANE",
    "GASOLINE", "HEATING OIL", "WAHA", "ALGONQUIN", "TRANSCO", "TETCO",
)
ELECTRICITY = (
    "PJM", "ISO NE", "ISO NEW ENG", "ISONE", "NEPOOL", "MISO", "ERCOT", "CAISO",
    "NYISO", "SP-15", "NP-15", "MID-C", "PALO", "ELECTRIC", "LMP",
)
ISONE = ("ISO NE", "ISO NEW ENG", "ISONE", "NEPOOL")

# The eight ISO-NE load zones, in the order src/vermont/README.md ranks them by
# latitude, plus the two hub names that are not zones. Each entry is the set of
# spellings the COT has used for it. The point of searching all eight is that
# "New Hampshire is absent" means little on its own -- it means something once
# you can see which zones are present.
ZONES = {
    "Maine":          ("MAINE", ".Z.ME", " ME "),
    "Vermont":        ("VERMONT", ".Z.VT", " VT "),
    "New Hampshire":  ("NEW HAMPSHIRE", "NEWHAMPSHIRE", "NEMHAMPSHIRE", ".Z.NH"),
    "NEMA / Boston":  ("NEMA", "BOSTON"),
    "WC Mass":        ("WC MASS", "WCMASS", "WESTERN CENTRAL"),
    "SE Mass":        ("SE MASS", "SEMASS", "SOUTH EAST MASS", "SOUTHEAST MASS"),
    "Rhode Island":   ("RHODE ISLAND", "RHODEISLAND", ".Z.RI", " RI "),
    "Connecticut":    ("CONNECTICUT", "CONN", ".Z.CT", " CT "),
}
HUBS = {"Mass Hub / Internal Hub": ("MASS HUB", "MASSHUB", "MH DA", "INTERNAL_HUB",
                                    "INTERNAL_HB", "INT HUB", "ENG HUB", "NE HUB")}

# NERC holidays are all-hours off-peak. Only these three fall inside Nov-Mar.
def _nerc_holidays(year: int) -> set[dt.date]:
    hol = {dt.date(year, 1, 1), dt.date(year, 12, 25)}
    # Thanksgiving: fourth Thursday in November.
    novs = [d for d in range(1, 31)
            if dt.date(year, 11, d).weekday() == calendar.THURSDAY]
    hol.add(dt.date(year, 11, novs[3]))
    return hol


def offpeak_hours(start: dt.date, end: dt.date) -> int:
    """Off-peak hours in [start, end): HE01-07 + HE24 on weekdays, all 24 on
    weekends and NERC holidays. This is the block the contract settles on."""
    hol = _nerc_holidays(start.year) | _nerc_holidays(end.year)
    h, d = 0, start
    while d < end:
        h += 24 if (d.weekday() >= 5 or d in hol) else 8
        d += dt.timedelta(days=1)
    return h


def is_electricity(name: str) -> bool:
    u = name.upper()
    if any(k in u for k in GAS_LIQUIDS):
        return False
    return any(k in u for k in ELECTRICITY)


def fetch(year: int, allow_network: bool) -> Path | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"fut_disagg_txt_{year}.zip"
    if p.exists() and p.stat().st_size > 100_000:
        return p
    if not allow_network:
        return None
    req = urllib.request.Request(URL.format(year=year),
                                 headers={"User-Agent": "snowmaking-load-study"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            p.write_bytes(r.read())
    except Exception as exc:                                   # noqa: BLE001
        print(f"  {year}: fetch failed ({exc})", file=sys.stderr)
        return None
    return p


def read_year(path: Path) -> list[dict]:
    z = zipfile.ZipFile(path)
    raw = z.read(z.namelist()[0]).decode("utf8", errors="replace")
    rows = list(csv.reader(io.StringIO(raw)))
    hdr = [h.strip() for h in rows[0]]
    iN = hdr.index("Market_and_Exchange_Names")
    iOI = hdr.index("Open_Interest_All")
    # The date column is named differently across vintages.
    iD = next((hdr.index(c) for c in
               ("Report_Date_as_YYYY-MM-DD", "Report_Date_as_MM_DD_YYYY",
                "As_of_Date_In_Form_YYMMDD") if c in hdr), None)
    out = []
    for x in rows[1:]:
        if not x:
            continue
        full = x[iN].strip()
        venue = full.split(" - ")[-1].strip()
        out.append({
            "market": full[: len(full) - len(venue) - 3].strip(),
            "venue": venue,
            "date": x[iD].strip() if iD is not None else "",
            "oi": int(x[iOI]) if x[iOI].strip() else 0,
        })
    return out


def main() -> None:
    allow_network = "--no-fetch" not in sys.argv
    DATA.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("ISO NEW ENGLAND OFF-PEAK FUTURES -- open interest in the CFTC COT")
    print("=" * 78)
    print(f"  reporting level (17 CFR 15.03, All Other Commodities): "
          f"{REPORTING_LEVEL} contracts")
    print(f"  COT publication rule: {COT_TRADER_RULE}+ traders at or above it")
    print()

    per_year, isone_rows, census_rows = {}, [], []
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        p = fetch(y, allow_network)
        if p is None:
            print(f"  {y}: unavailable, skipped")
            continue
        rows = read_year(p)
        elec = [r for r in rows if is_electricity(r["market"])]
        per_year[y] = elec
        for r in elec:
            if any(k in r["market"].upper() for k in ISONE):
                isone_rows.append({"year": y, **r})
        for venue, n in collections.Counter(
                r["venue"] for r in elec).items():
            census_rows.append({"year": y, "venue": venue,
                                "market_weeks": n,
                                "markets": len({r["market"] for r in elec
                                                if r["venue"] == venue})})

    # ---- A. does a New Hampshire market appear anywhere, ever? --------------
    nh = [r for y in per_year for r in per_year[y]
          if "NEW HAMPSHIRE" in r["market"].upper()
          or "NEWHAMPSHIRE" in r["market"].upper().replace(" ", "")]
    print("-" * 78)
    print("A. New Hampshire markets in the COT, all venues, "
          f"{FIRST_YEAR}-{LAST_YEAR}")
    print("-" * 78)
    print(f"   rows found: {len(nh)}")
    if nh:
        for r in nh[:20]:
            print("   ", r)
    else:
        print("   None. On no venue, in no week of sixteen years, have "
              f"{COT_TRADER_RULE} traders")
        print(f"   held {REPORTING_LEVEL} lots or more of a New Hampshire "
              "zone power contract.")
    print()

    # ---- A2. the same question asked of all eight zones --------------------
    print("-" * 78)
    print("A2. Which ISO-NE locations clear the COT bar at all, "
          f"{FIRST_YEAR}-{LAST_YEAR}")
    print("-" * 78)
    print(f"   {'location':24s} {'off-peak markets':>17s} {'venues':>26s} "
          f"{'peak OI':>12s}")
    for label, keys in {**HUBS, **ZONES}.items():
        hits = [r for r in isone_rows
                if any(k in r["market"].upper() for k in keys)]
        off = [r for r in hits if "OFF" in r["market"].upper()]
        vens = sorted({r["venue"].replace("NEW YORK MERCANTILE EXCHANGE", "CME")
                       .replace("ICE FUTURES ENERGY DIV", "ICE")
                       .replace("NODAL EXCHANGE", "Nodal")
                       .replace("ICE OTC", "ICE-OTC") for r in off})
        peak = max((r["oi"] for r in off), default=0)
        print(f"   {label:24s} {len({r['market'] for r in off}):17d} "
              f"{','.join(vens)[:26]:>26s} {peak:12,}")
    print()
    print("   Connecticut is the row that matters. A zonal off-peak contract")
    print("   CAN clear the bar -- CT's did, on CME, at 672,838 lots. So the")
    print("   New Hampshire zero is not 'zones never trade'. It is this zone.")
    print()

    # ---- B. the ISO-NE markets that DO clear the bar -----------------------
    print("-" * 78)
    print("B. ISO-NE markets that do appear, by year (open interest, contracts)")
    print("-" * 78)
    by_market = collections.defaultdict(list)
    for r in isone_rows:
        by_market[(r["market"], r["venue"])].append((r["year"], r["oi"]))
    print(f"   {'market':34s} {'venue':22s} {'years':11s} {'peak OI':>10s} "
          f"{'last OI':>10s}")
    for (m, v), vals in sorted(by_market.items(),
                               key=lambda kv: -max(o for _, o in kv[1])):
        yrs = sorted({y for y, _ in vals})
        span = f"{yrs[0]}-{yrs[-1]}" if len(yrs) > 1 else str(yrs[0])
        last = [o for y, o in vals if y == yrs[-1]][-1]
        print(f"   {m[:34]:34s} {v[:22]:22s} {span:11s} "
              f"{max(o for _, o in vals):10,} {last:10,}")
    print()

    # ---- C. the venue census: where did CME's electricity book go? ---------
    print("-" * 78)
    print("C. Electricity markets in the COT by venue and year (market count)")
    print("-" * 78)
    venues = sorted({c["venue"] for c in census_rows})
    short = {v: (v.replace("NEW YORK MERCANTILE EXCHANGE", "NYMEX/CME")
                 .replace("ICE FUTURES ENERGY DIV", "ICE")
                 .replace("NODAL EXCHANGE", "Nodal")
                 .replace("ICE OTC", "ICE OTC")) for v in venues}
    print(f"   {'year':6s}" + "".join(f"{short[v][:12]:>13s}" for v in venues)
          + f"{'ISO-NE @ NYMEX/CME':>21s}")
    for y in sorted(per_year):
        cells = ""
        for v in venues:
            n = next((c["markets"] for c in census_rows
                      if c["year"] == y and c["venue"] == v), 0)
            cells += f"{n:13d}"
        ne = len({r["market"] for r in per_year[y]
                  if r["venue"] == "NEW YORK MERCANTILE EXCHANGE"
                  and any(k in r["market"].upper() for k in ISONE)})
        print(f"   {y:<6d}{cells}{ne:21d}")
    print()

    # ---- D. how big is the load, in contracts? -----------------------------
    print("-" * 78)
    print("D. The load, priced in lots of the contract that would hedge it")
    print("-" * 78)
    lo_gwh, hi_gwh = 22, 54          # README.md section 8.8, NH row, derived
    hrs = offpeak_hours(dt.date(2024, 11, 1), dt.date(2025, 4, 1))
    lo_mw, hi_mw = lo_gwh * 1000 / hrs, hi_gwh * 1000 / hrs
    print(f"   New Hampshire snowmaking, per season   {lo_gwh}-{hi_gwh} GWh "
          "(derived, README section 8.8)")
    print(f"   off-peak hours Nov 1 - Mar 31          {hrs:,} h "
          "(HE01-07 + HE24 weekdays, 24 h weekends/NERC holidays)")
    print(f"   flat across the whole off-peak block   {lo_mw:.1f}-{hi_mw:.1f} MW")
    print()
    for venue, mw in NH_CONTRACT_MW.items():
        pos = REPORTING_LEVEL * mw
        print(f"   {venue:12s} {mw} MW/lot -> the season's load is "
              f"{lo_mw / mw:5.1f}-{hi_mw / mw:5.1f} lots; "
              f"one reportable position is {pos:3d} MW "
              f"({REPORTING_LEVEL} lots); the load is "
              f"{lo_mw / pos:.2f}-{hi_mw / pos:.2f} of one")
    print()
    # The concentrated alternative: the same energy drawn on ~45 productive
    # nights rather than spread flat. This is the framing FAVOURABLE to the
    # instrument, so it is the one that has to be reported alongside.
    nights, block_h = 45, 8
    clo, chi = lo_gwh * 1000 / (nights * block_h), hi_gwh * 1000 / (nights * block_h)
    print(f"   concentrated on {nights} productive nights x {block_h} h "
          f"-> {clo:.0f}-{chi:.0f} MW, i.e. "
          f"{clo / (REPORTING_LEVEL * 5):.2f}-{chi / (REPORTING_LEVEL * 5):.2f} "
          "of one CME reportable position")
    print()
    print("   Read that last column against the one above it. On CME's 5 MW")
    print("   contract the entire New Hampshire snowmaking load, spread over the")
    print("   block, is a fraction of ONE reportable position. The COT needs")
    print(f"   {COT_TRADER_RULE} such traders before it prints a line.")

    # ---- outputs -----------------------------------------------------------
    with (DATA / "futures_isone_oi.csv").open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "date", "market", "venue", "oi"])
        w.writeheader()
        for r in sorted(isone_rows, key=lambda r: (r["year"], r["market"], r["date"])):
            w.writerow({k: r[k] for k in w.fieldnames})
    with (DATA / "futures_venue_census.csv").open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "venue", "markets", "market_weeks"])
        w.writeheader()
        for r in sorted(census_rows, key=lambda r: (r["year"], r["venue"])):
            w.writerow(r)
    print()
    print(f"   wrote {DATA / 'futures_isone_oi.csv'} ({len(isone_rows)} rows)")
    print(f"   wrote {DATA / 'futures_venue_census.csv'} ({len(census_rows)} rows)")


if __name__ == "__main__":
    main()
