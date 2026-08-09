"""Fetch hourly day-ahead spot electricity prices from the energy-charts.info API.

Downloads the day-ahead auction clearing price (EUR/MWh) for a set of European
bidding zones, restricted to the Oct 1 - Dec 31 window of each requested year,
and writes one tidy CSV per zone.

Source
------
https://api.energy-charts.info/price?bzn={BZN}&start=YYYY-MM-DD&end=YYYY-MM-DD

The endpoint returns JSON with keys ``unix_seconds`` (true UTC epoch seconds),
``price`` (may contain nulls), and ``unit``. The ``start``/``end`` query
parameters are interpreted by the server in the bidding zone's *local* market
time and ``end`` is inclusive of the whole day.

Conventions
-----------
* The analysis window is defined in local market time (all zones handled here
  are CET/CEST): Oct 1 00:00 local through Dec 31 23:00 local. Because the
  DST fall-back happens in late October, a complete window is 92 * 24 + 1 =
  2209 hours, not 2208.
* Output timestamps are ISO 8601 UTC, so they are unambiguous across the DST
  fold.
* Nulls in the ``price`` array are dropped, never interpolated or zero-filled.
  They are reported as missing hours.

Behaviour
---------
* Requests are paced (>= PACE_SECONDS apart) because the API rate-limits
  bursts with errors that look like missing data.
* Every successful raw response is cached to disk immediately; a cached year
  is never refetched.
* A failed request is retried RETRIES times with exponential backoff. A year
  is only declared unavailable after all attempts fail.

Usage
-----
    python fetch_prices.py

Only ``CACHE_DIR`` needs to be adapted to a new machine.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# --- the one path constant -------------------------------------------------
CACHE_DIR = Path(r"C:\Users\bcris\.claude-snow\jobs\11224758\tmp\price")

RAW_DIR = CACHE_DIR / "cache"
LOG_PATH = CACHE_DIR / "fetch_log.txt"

API = "https://api.energy-charts.info/price"
PACE_SECONDS = 3.5
RETRIES = 4
BACKOFF_BASE = 5.0
TIMEOUT = 90

YEARS = range(2015, 2026)

# zone -> (api bidding zone code, output csv basename or None to fetch only)
ZONES = {
    "AT": ("AT", "price_at.csv"),
    "CH": ("CH", "price_ch.csv"),
    "IT-North": ("IT-North", "price_itnorth.csv"),
    # DE-LU is fetched purely as a reference series to date the moment the
    # Austrian bidding zone stopped being part of the common DE-AT-LU zone.
    "DE-LU": ("DE-LU", None),
}

MARKET_TZ = ZoneInfo("Europe/Vienna")  # CET/CEST; same clock for CH and IT.

_last_request_at = 0.0


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _paced_get(url: str) -> bytes:
    """GET the url, never faster than PACE_SECONDS after the previous call."""
    global _last_request_at
    wait = PACE_SECONDS - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "research-fetch/1.0"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    finally:
        _last_request_at = time.monotonic()


def fetch_year(bzn: str, year: int) -> dict | None:
    """Return the raw JSON payload for one zone-year, using the disk cache."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = RAW_DIR / f"{bzn}_{year}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    # A few days of lead-in so the local-time window is fully covered whatever
    # the server does at the boundary; the surplus is trimmed later.
    url = f"{API}?bzn={bzn}&start={year}-09-25&end={year}-12-31"

    for attempt in range(1, RETRIES + 1):
        try:
            payload = json.loads(_paced_get(url))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
            log(f"FAIL  {bzn} {year} attempt {attempt}/{RETRIES}: {type(exc).__name__}: {exc}")
        else:
            if not payload.get("unix_seconds"):
                log(f"EMPTY {bzn} {year} attempt {attempt}/{RETRIES}: no unix_seconds in response")
            else:
                unit = payload.get("unit")
                if unit != "EUR / MWh":
                    raise SystemExit(f"unexpected unit for {bzn} {year}: {unit!r}")
                cache_file.write_text(json.dumps(payload), encoding="utf-8")
                log(f"OK    {bzn} {year}: {len(payload['unix_seconds'])} points cached")
                return payload
        if attempt < RETRIES:
            time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))

    log(f"GIVEUP {bzn} {year}: unavailable after {RETRIES} paced attempts")
    return None


def window_bounds(year: int) -> tuple[int, int]:
    """UTC epoch seconds for Oct 1 00:00 and Dec 31 23:00 local market time."""
    start = datetime(year, 10, 1, 0, tzinfo=MARKET_TZ)
    end = datetime(year, 12, 31, 23, tzinfo=MARKET_TZ)
    return int(start.timestamp()), int(end.timestamp())


def expected_hours(year: int) -> int:
    """Number of distinct local hours in the Oct 1 - Dec 31 window."""
    lo, hi = window_bounds(year)
    return (hi - lo) // 3600 + 1


def extract(payload: dict, year: int) -> tuple[list[tuple[int, float]], int, list[int]]:
    """Trim a payload to the window.

    Returns (rows, null_count, raw_step_seconds_observed).
    """
    lo, hi = window_bounds(year)
    ts = payload["unix_seconds"]
    px = payload["price"]
    steps = sorted({b - a for a, b in zip(ts, ts[1:])})

    rows: list[tuple[int, float]] = []
    nulls = 0
    # hi is the *start* of the final hour; keep sub-hourly points inside it too.
    for t, p in zip(ts, px):
        if t < lo or t > hi + 3599:
            continue
        if p is None:
            nulls += 1
            continue
        rows.append((int(t), float(p)))
    rows.sort()
    return rows, nulls, steps


def to_hourly(rows: list[tuple[int, float]]) -> tuple[dict[int, float], list[int]]:
    """Collapse raw points onto hour-starting timestamps.

    From 2025-10-01 the European day-ahead auction clears on a 15-minute MTU,
    so the API returns four points per hour for that period. Those four are
    averaged into the hour (an unweighted arithmetic mean of the four MTU
    clearing prices). Genuinely hourly periods pass through untouched. Nothing
    is interpolated: an hour with no data stays absent.
    """
    groups: dict[int, list[float]] = {}
    for t, p in rows:
        groups.setdefault(t - (t % 3600), []).append(p)
    hourly = {h: statistics.fmean(v) for h, v in groups.items()}
    return hourly, [len(v) for v in groups.values()]


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_price(p: float) -> str:
    """Cent precision for natively hourly values, 4 dp for averaged MTU hours."""
    return f"{p:.4f}".rstrip("0").rstrip(".")


def summarise(rows: list[tuple[int, float]]) -> dict:
    vals = [p for _, p in rows]
    if not vals:
        return {}
    return {
        "n": len(vals),
        "min": min(vals),
        "mean": statistics.fmean(vals),
        "max": max(vals),
        "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
        "n_negative": sum(1 for v in vals if v < 0),
        "n_gt300": sum(1 for v in vals if v > 300),
    }


def main() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stats: dict[str, dict] = {}
    series: dict[str, dict[int, dict[int, float]]] = {}

    for zone, (bzn, out_name) in ZONES.items():
        stats[zone] = {}
        series[zone] = {}
        csv_rows: list[tuple[int, float]] = []

        for year in YEARS:
            payload = fetch_year(bzn, year)
            if payload is None:
                stats[zone][year] = {"status": "unavailable"}
                continue
            rows, nulls, steps = extract(payload, year)
            if not rows:
                stats[zone][year] = {"status": "empty_in_window"}
                log(f"NOTE  {zone} {year}: response held no data inside the Oct-Dec window")
                continue

            exp = expected_hours(year)
            hourly, per_hour = to_hourly(rows)

            s = summarise(sorted(hourly.items()))
            s.update(
                status="ok",
                expected_hours=exp,
                missing_hours=exp - len(hourly),
                nulls_in_window=nulls,
                raw_points_in_window=len(rows),
                raw_step_seconds=steps[:5],
                native_resolution="15-min MTU" if max(per_hour) > 1 else "hourly",
                points_per_hour=sorted(set(per_hour)),
            )
            stats[zone][year] = s
            series[zone][year] = hourly
            csv_rows.extend(sorted(hourly.items()))
            log(
                f"STAT  {zone} {year}: {len(hourly)}/{exp} h, "
                f"mean {s['mean']:.2f}, max {s['max']:.2f}, neg {s['n_negative']}, >300 {s['n_gt300']}"
            )

        if out_name:
            path = CACHE_DIR / out_name
            with path.open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["ts_utc", "price_eur_mwh"])
                for t, p in sorted(csv_rows):
                    w.writerow([iso(t), fmt_price(p)])
            log(f"WROTE {path} ({len(csv_rows)} rows)")

    (CACHE_DIR / "stats.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    (CACHE_DIR / "series.json").write_text(
        json.dumps({z: {str(y): {str(t): p for t, p in d.items()} for y, d in ys.items()}
                    for z, ys in series.items()}),
        encoding="utf-8",
    )
    log("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
