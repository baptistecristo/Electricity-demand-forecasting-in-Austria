# Data

Nothing here is committed. Everything below is free and reproducible.

## 1. Austrian load and day-ahead forecast

### Option A — ENTSO-E Transparency Platform (full history, needs a free token)

Series: `A65` day-ahead total load forecast, `A16` actual total load, bidding
zone `AT`. Available from 2015; the clean bidding-zone-consistent window starts
1 Oct 2018.

Getting the token, free, roughly three working days:

1. Register at <https://transparency.entsoe.eu/>
2. Email <transparency@entsoe.eu>, subject line **`RESTful API access`**, with
   your registered email address in the body
3. On approval, log in → **My Account** → generate a security token
4. `export ENTSOE_TOKEN=...`

`src/snowload.py` pulls both series via `entsoe-py` and caches them under
`cache/`.

### Option B — APG direct download (2024 onward, no registration)

APG publishes the same two series at 15-minute resolution as ZIP archives, with
no login:

- Actual total load: <https://markt.apg.at/en/transparency/load/actual-total-load/> → `Gesamtlast.zip`
- Day-ahead forecast: <https://markt.apg.at/en/transparency/load/total-load-forecast/> → `Prognose über die Gesamtlast.zip`

History on the web view starts January 2024, so this covers two seasons. Not
enough for the interaction test in §5 of the README, but enough to measure the
forecast error standard deviation and run the campaign-start event study.

Note that APG's published load excludes a corridor in Vorarlberg. See README §2.

## 2. Alpine weather

GeoSphere Austria Dataset API, no key required.

- Docs: <https://dataset.api.hub.geosphere.at/v1/docs/>
- Dataset: `station/historical/klima-v2-1h`
- Parameters: `tl` (air temperature, °C), `rf` (relative humidity, %)
- Station metadata: `GET /v1/station/historical/klima-v2-1h/metadata`

`src/snowload.py` selects stations automatically at 900–2,600 m in the ski
states, so no station list needs to be maintained by hand.

Example request:

```
https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-1h
  ?parameters=tl,rf
  &start=2023-11-01T00:00
  &end=2024-03-31T23:00
  &station_ids=11803,11804
  &output_format=csv
```

## 3. Resort opening dates

Manual. Roughly 30 resorts cover most of Austrian equipped capacity. Sources are
resort websites plus the Wayback Machine for historical seasons. Recorded as
`resort,season,opening_date` in `data/opening_dates.csv` when collected.

## 4. Placebo countries

Same ENTSO-E series, bidding zones `NL` and `DK_1`. Cold, flat, no snowmaking.
Run through the identical pipeline.
