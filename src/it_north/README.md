# Italy-North replication — snowmaking and the day-ahead load forecast

Replication of the Austrian test in `src/apg_pipeline.py` on the Italian
**IT-North (Nord) bidding zone**. Same question, same specification, same
estimator, same thresholds, same primary coefficient.

```
python src/it_north/it_pipeline.py
```

Everything below is what the script actually printed. The full log is reproduced
in §6.

---

## Headline

**Two things happened, and the second one limits what the first one is worth.**

**1. The primary coefficient is a null, matching Austria almost exactly.**

| | `below:cum100` | s.e. | z | p |
|---|---|---|---|---|
| Austria (13 seasons, 780 nights) | +5.08 | 11.85 | 0.43 | 0.67 |
| **Italy-North (7 seasons, 420 nights)** | **+4.33** | **10.19** | **0.42** | **0.67** |
| Italy-North, 20-station index | +8.60 | 9.63 | 0.89 | 0.37 |

The prediction was **negative** (the threshold effect should shrink as
season-to-date accumulated cold rises). The estimate is small, positive and
indistinguishable from zero — in Italy as in Austria, to two significant figures.

**2. The pre-specified sanity gate did not fire — and it is not because the
pipeline is broken.**

The Austrian design certifies its own sensitivity by recovering the Christmas
industrial shutdown out of the day-ahead forecast error: `holiday` = **−274 MW
(t = −3.3)** in Austria. In Italy-North the same coefficient on the same kind of
nights is **−28 ± 71 (p = 0.70)**. It is ≈ 0.

The reason is not a data fault. **Terna's day-ahead forecast already anticipates
the Christmas shutdown almost perfectly**, so nothing is left in the residual for
the gate to catch. §2 reproduces the proof, which the pipeline prints on every
run.

**Consequence, stated plainly: the Italian null carries no empirical sensitivity
warranty.** Austria could show its design detected a real effect of roughly the
right size. Italy cannot. §5 gives what can be said instead — a paper-power
bound, which is a weaker kind of claim.

---

## 1. The gate, as printed

```
=== PRIMARY - Nov-Dec, all nights  (n=420) ===
              Coef.  Std.Err.     z  P>|z|
below        -25.85     55.27 -0.47   0.64
cum100        42.01     43.74  0.96   0.34
below:cum100   4.33     10.19  0.42   0.67
dist         -28.69     28.31 -1.01   0.31
below:dist    15.85     28.43  0.56   0.58
holiday      -27.97     71.43 -0.39   0.70
```

`holiday` = −27.97 ± 71.43. **The gate fails.** Per the study protocol that means
"report the breakage, not the finding". §2 is that report — and its conclusion is
that there is no breakage to report.

---

## 2. Why the gate fails — the diagnostic

If the `holiday` coefficient collapses there are exactly two candidate
explanations, and they are separable:

- **(a) the pipeline is broken** — timezone shift, sign flip, decimal-comma
  corruption. Any of these destroys the *forecast* column's relationship to the
  calendar.
- **(b) the forecaster is not missing the shutdown** — in which case the actual
  load drops, the forecast drops with it, and the residual is flat.

So print the shutdown as it appears in actual load and, separately, as it appears
in the forecast. Straight from the run:

```
GATE DIAGNOSTIC - is a weak `holiday` coefficient breakage?
  Christmas shutdown, Dec 21-31 minus Dec 1-20 (MW)
  window           in ACTUAL   in FORECAST  left in error
  night 20-06         -4,482        -4,461            -20
  day 09-17           -7,583        -7,434           -148
  all hours           -6,055        -5,959            -96

  per season, night hours (MW):
  season     actual drop  forecast drop   residual
  2019            -5,445         -5,443         -1
  2020            -4,088         -4,113        +25
  2021            -3,963         -3,955         -8
  2022            -4,283         -4,169       -114
  2023            -4,937         -4,908        -29
  2024            -4,428         -4,486        +58
  2025            -4,229         -4,155        -74
```

The Christmas shutdown in IT-North is **−4,482 MW** on night hours — enormous,
roughly two thirds of Austria's entire overnight load. Terna's day-ahead forecast
predicts **−4,461 MW** of it. The residual is **−20 MW, or 0.4% of the event**,
and it is small in all seven seasons independently.

**A corrupted pipeline cannot produce that pair of numbers.** A timezone shift, a
sign error or a mangled decimal would break the forecast column's tracking of a
multi-gigawatt calendar event, not preserve it to within half a percent seven
times running. The data are intact. It is the gate's *premise* — that the
day-ahead forecaster misses Christmas — that does not hold for Terna.

Supporting evidence that the load side is sound, all verified before the
regressions were run:

- **Timezone**: verified local Europe/Rome wall clock from DST row counts (§3),
  not assumed.
- **Sign**: `err = actual − forecast`; the −196 MW Nov–Dec night bias means Terna
  over-forecasts overnight, which is consistent in sign across all seven seasons.
- **Forecast is genuinely ex-ante**: Nov–Dec night MAE is **2.17% of load** —
  the right order for a real day-ahead forecast, far too large for a backfilled
  series; and the hour-of-day error profile has the classic day-ahead signature
  (−356 MW at 00:00, +370 MW on the 07:00 morning ramp) rather than white noise.
- **Parse**: all 61,844 quarter-hour rows had exactly the expected six-field
  layout; the script raises on anything else.

### The honest reading of the gate failure

Two things are true at once and neither should be inflated:

- **It is a real loss.** Without recovering *any* reference effect, this
  replication has no demonstration that its residual can carry a signal of the
  size snowmaking would produce. The Austrian null was certified. This one is not.
- **It is not evidence that the design is blind.** The Christmas shutdown is a
  *calendar* event. Any forecaster with a holiday dummy gets it for free, and
  Terna evidently has a good one. Snowmaking is weather-triggered and is not in
  anybody's calendar, so Terna's skill at Christmas puts no direct bound on its
  skill at snowmaking.

What the gate failure does establish, and it is worth one line: **Terna's
day-ahead forecast is roughly three times more accurate than APG's in relative
terms** (2.17% vs 6.48% night MAE). Whatever residual snowmaking leaves, it is
being looked for in a much cleaner series.

---

## 3. Load data — endpoints, coverage, traps

**Source: Terna Download Center, no login, no token.**
<https://dati.terna.it/en/download-center> is a Vue front-end over a Sitecore
API. Two endpoints exist:

| Endpoint | Method | Result |
|---|---|---|
| `/api/sitecore/dati/downloadcenter/recordsv2` | POST, JSON body | the table view. Returned **HTTP 500** for every body shape tried. |
| `/api/sitecore/dati/downloadcenter/records` | GET, query string | the "Download Data" link. **Works.** `f=xlsx` is what the UI requests; `f=csv` is undocumented but served. |

The exact request this pipeline issues:

```
https://dati.terna.it/api/sitecore/dati/downloadcenter/records
    ?f=csv
    &filterDataset=TotalLoad
    &filterBiddingZone=North
    &filterYear=2023&filterMonth=12
    &orderByColumn=Date&orderByDir=asc
    &db=dati
    &pageSize=1048573
```

`pageSize=1048573` is the front-end's own `maxPageSize` constant. `filterDay` is
accepted and silently ignored, so the pipeline pages one month at a time.

### The dataset

`TotalLoad` returns **both series in one file**, per bidding zone, at 15-minute
resolution:

```
Date,Total Load [MW],Forecast Total Load [MW],Bidding Zone
2023-12-01T00:00:00,17003,081000,17812,240000,North,
```

This is the direct analogue of APG's `Gesamtlast` / `Prognose über die
Gesamtlast` pair, and better in one respect: actual and forecast come from the
same file on the same basis, so there is no cross-series join risk.

**The forecast is ex-ante D-1.** Terna's own API documentation for this dataset:
*"forecast data are processed the day before the reference day based on our best
forecast"* —
<https://developer.terna.it/docs/read/apis_catalog/load/Total_Load>. The two
empirical checks in §2 agree.

**Rejected: `MGPForecastLoad`.** Also exists, also has a `North` zone, also
hourly — but it is *market* load for the day-ahead market session, not total
system load. For 2023-12-31 23:00 it reports 10,532 MW for North where
`TotalLoad` reports ~11,500 MW. Pairing it with `TotalLoad`'s actual would
manufacture a spurious ~1 GW error. Not used.

### Coverage obtained

IT-North `TotalLoad`, quarter-hours per month:

| Season | Oct | Nov | Dec |
|---|---|---|---|
| 2017 | 0 | 0 | 0 |
| 2018 | 0 | 0 | 0 |
| 2019 | 2,972 | 2,880 | 2,976 |
| 2020–2025 (each) | 2,980 | 2,880 | 2,976 |

**Seven complete seasons, 2019–2025, no holes.** The zonal archive begins in
2019; 2017 and 2018 return zero rows. Austria had thirteen seasons.

### Timezone — verified, not assumed

Terna publishes **local Europe/Rome wall clock**. Proof is in the row counts:
October has 2,980 quarter-hours (2,976 + 4) because the 02:00 hour appears
*twice* on the fall-back date, and March has 2,972 (2,976 − 4) because it is
missing. Neither is possible on a UTC clock. Verbatim:

```
2023-10-29T02:00:00,12424,503000,12546,264000,North,
2023-10-29T02:00:00,12285,899000,12481,174000,North,
```

That is exactly APG's convention, so `apg_pipeline`'s "group by hour string and
average" fold transfers unchanged. (October 2019 is the one exception: the
repeated hour is *absent* rather than duplicated, costing one hour outside the
November–December estimation window.)

### CSV parsing — the one real trap

Terna's `f=csv` export writes **Italian decimal commas into a comma-separated
file**. `17003,081000` is one number, not two fields. `pandas.read_csv` cannot
recover from this and would silently return garbage. The pipeline parses
positionally and asserts exactly six fields per row, so a format change fails
loudly instead:

```
Date, actual_int, actual_frac, forecast_int, forecast_frac, zone, ''
```

All 61,844 rows pulled matched this layout — no missing values, no ragged rows.

---

## 4. Weather data — what was found, and what was not

Austria used one national API (GeoSphere) covering five federal states. Italy has
no national equivalent: alpine weather data is devolved to regional and
provincial agencies. Five were tried.

| Source | Endpoint tried | Outcome |
|---|---|---|
| **Bolzano / South Tyrol** | `https://daten.buergernetz.bz.it/services/meteo/v1/{stations,sensors,timeseries}` | **Works.** No key. 229 stations, 10-minute readings, air temperature (`LT`) and relative humidity (`LF`), full sample history. **Used.** |
| Meteotrentino (Trentino) | `https://dati.meteotrentino.it/service.asmx` | Reachable; `listaStazioni` returns full metadata. But the only historical hourly method, `getValoriAggregatiOraJson`, **takes no parameters** and returns daily min/max temperature and precipitation only — no humidity, no station selection, no date range. `ultimiDatiStazione` serves latest readings only. **Unusable for wet bulb.** |
| ARPA Veneto | `api.arpa.veneto.it/REST/v1/meteo_meteogrammi_last`, `/meteo_meteogrammi`, `/stazioni_meteo`, `/meteo_arpav_ultimi_dati` | HTTP **500, 400, 500, 500**. No working endpoint found. |
| ARPA Lombardia | `www.dati.lombardia.it/resource/nf78-nj6b.json` (sensor registry) works; the per-year historical value datasets were sought via `api.us.socrata.com/api/catalog/v1?domains=www.dati.lombardia.it` → HTTP **404** | Registry reachable, historical values not locatable inside the time budget. |
| ARPA Piemonte | `www.arpa.piemonte.it/rischinaturali/tematismi/clima/...` | HTTP **404**. |

### Deviation: one weather region, not five

**The wet-bulb index rests on South Tyrol alone, at weight 1.0.** This is the
largest deviation from the Austrian specification, so it is stated here rather
than buried.

Defensible because: South Tyrol is the largest Italian ski region and the core of
Dolomiti Superski; it lies inside the IT-North bidding zone; it offers 65
stations in the 900–2600 m band carrying both temperature and humidity; and
cold-threshold *timing* — which is what the design exploits — is strongly
correlated across the Alpine arc.

Costly because: Piedmont and Valle d'Aosta sit on the western Alpine arc and can
be on the other side of a front from the Dolomites. Nights when the west is below
threshold and the east is not are misclassified.

**Region weighting: not applicable — one region at weight 1.0. No skier-visit
weighting was used, because no citable source for skier days by Italian region
was found inside the time budget** (searches returned overnight-stay tourism
statistics, which are not skier days). The Austrian `num`/`den` weighting
machinery is left structurally intact in `wetbulb_index()` so a second region can
drop in unchanged if one of the failing APIs recovers.

### Station selection

`pick_stations()` mirrors `apg_pipeline.pick_stations()`: altitude band
**900–2600 m** unchanged, highest first, require **both** `LT` and `LF`, drop
duplicate site names. Valley stations stay excluded for the Austrian reason —
they cross the threshold hundreds of hours later than where snow is made and
would manufacture a null.

Selected (primary, `per_region=4`):

```
     id                 name  altitude
07740WS   Trafoi Zaufenkofel      2475
69900MS                Plose      2472
01080SF Melago Monte Pratzen      2450
42830SF  Braies Alpe Cavallo      2340
```

`per_region=4` is unchanged from Austria — but five Austrian regions yielded 13
stations after de-duplication, and one Italian region yields 4. The pipeline
therefore also runs the primary specification on a **20-station** index
(1,950–2,475 m), so the effect of that thinning is measured rather than argued
about. It is small: the primary coefficient moves from +4.33 ± 10.19 to
+8.60 ± 9.63, still a null.

Index cold-share, for comparability:

| Index | hours | share below −2 °C |
|---|---|---|
| Austria, 13 stations | 28,704 | 45.8% |
| Italy, 4 stations | 15,455 | 59.1% |
| Italy, 20 stations | 15,456 | 50.9% |

The 20-station Italian index sits close to Austria's; the 4-station one is
colder, because with a single region the four highest sites are all above
2,340 m.

### Wet bulb — unchanged, and spot-checked after transfer

`wet_bulb()` and `pressure_from_altitude()` are transferred verbatim: bisection
on `es(Tw) − A·P·(T−Tw) − e = 0` with `A = 6.53e-4 (1 + 9.44e-4 Tw)` over water,
plus ISA station pressure. The Stull (2011) closed form was **not** substituted.

| T (°C) | RH (%) | P (hPa) | Tw (°C) |
|---|---|---|---|
| 20.0 | 50 | 1013.25 | **13.84** (psychrometric tables ≈ 13.8) |
| 0.0 | 50 | 1013.25 | −2.87 |
| −2.0 | 60 | 1013.25 | −4.06 |
| 2.0 | 40 | 820.0 (≈1800 m) | **−2.35** |

The last row is why station pressure is not optional: at +2 °C and 40% RH an
alpine station is already *below* the snowmaking threshold, and a sea-level
assumption would not say so.

**Deviation:** South Tyrol publishes 10-minute readings where GeoSphere published
hourly. Readings are averaged to the hour *first*, then `wet_bulb()` runs on the
hourly means — one bisection per station-hour, matching what the Austrian run did
with natively hourly data.

Timestamps carry an explicit `CEST`/`CET` suffix (`2019-10-01T00:00:00CEST`), so
slicing to `YYYY-MM-DD HH` lands on the same local wall-clock key Terna publishes
on, and both sides of the join fold the DST-repeated hour by averaging. This is
*simpler* than the Austrian case, which needed an explicit UTC→local conversion.

---

## 5. Specification, deviations, and what the null does bound

### Unchanged from Austria

`err = actual − forecast` · night = 20:00–06:59 local labelled by its 20:00 date,
≥ 8 valid hours · estimated at **night** level · threshold −2.0 °C ·
`dist = wb − (−2)` · `below = 1[wb < −2]` · `cum_cold_h` accumulated from 1
October over **all** hours of the season and lagged · `cum100 = (cum_cold_h −
median)/100` · `holiday = 1` if December and day ≥ 21 · `err ~ below*cum100 +
dist + below:dist + holiday + doy_c + I(doy_c**2) + C(season) + C(dow)`, HC1 ·
primary coefficient `below:cum100`, predicted negative · campaign start = first
below-threshold night after ≥ 2 consecutive nights above.

### Deviations, all forced by data availability

| # | Austria | Italy-North | Why |
|---|---|---|---|
| 1 | 13 seasons (2010–2022) | **7 seasons (2019–2025)** | Terna's zonal archive starts 2019. |
| 2 | 5 weather regions, skier-volume weights | **1 region, weight 1.0** | four of five Italian regional APIs unusable (§4). |
| 3 | 13 stations | **4** (primary), 20 (robustness) | `per_region=4` × 1 region. Both reported. |
| 4 | station filter `valid_from ≤ 2009` | **has October 2019 data** | the API exposes no commissioning date. |
| 5 | hourly station data | **10-min averaged to hourly first** | that is what South Tyrol publishes. |
| 6 | robustness cut "seasons 2016–2022" | **"seasons 2022–2025"** | the late half of the available sample; 2016 predates the archive. |
| 7 | `n_ep = 13 × 9` in the α pass mark | **`n_ep = 7 × 9`** | seven seasons. |

The α pass-mark print still divides by **900 MW**, Austria's central coincident
snowmaking draw, so the printed figure stays directly comparable to the Austrian
run. It is not an Italian coincident-draw estimate — see below.

### What the null bounds, given the gate did not fire

This is a paper-power argument, not an empirical sensitivity demonstration. It is
weaker than what Austria could claim, and it is offered as such.

The 95% interval on the primary coefficient is
`+4.33 ± 1.96 × 10.19 = [−15.6, +24.3]` MW per 100 accumulated cold hours. A
season spans roughly 1,300 cold hours (median season-end `cum_cold_h` = 1,326 h),
i.e. ~13 units of `cum100`. If snowmaking leaves `A` MW unexplained on a
fresh-snowpack cold night and decays to nothing by season end, then
`below:cum100 ≈ −A/13`. Ruling out values below −15.6 therefore rules out
**A > ~200 MW**.

Scaling the repo's derived ~560 GWh/season for Italian snowmaking by Austria's
184.6 operating hours per snowmaker gives a fleet ceiling of ~3.0 GW and, at 50%
coincidence, ~1.5 GW of coincident draw. A 200 MW bound on `A` then corresponds
to **α ≲ 13%** — the share of snowmaking load the forecast leaves unexplained.
Austria's printed pass mark on the same formula was 27.4%.

So on paper this is a *more* sensitive test than Austria's, despite half the
seasons, because Terna's residual is much quieter (sd after hour/dow/season fixed
effects: **318 MW** for Italy vs **554 MW** for Austria). What is missing is any
empirical confirmation that a real load of that size would show up — which is
exactly what the gate was for.

### A correction to the scoping table that motivated this replication

Repo `README.md` §8.8 ranks Italy-North at **~45 GWh/GW**, above Austria's 43, on
a *scoping estimate* of ~12–13 GW for IT-North winter overnight load.

**The measured value is 16.9 GW.**

| IT-North load, 20:00–06:59 | MW |
|---|---|
| Nov + Dec, all days | 16,154 |
| Nov + Dec, weekdays | **16,871** |
| November, weekdays | 17,409 |
| Dec 1–20, weekdays | 18,088 |

At the derived ~560 GWh/season the ratio is therefore **≈33 GWh/GW against
Austria's 281/7.2 ≈ 39**. Even at 700 GWh it only reaches 41.

**Italy-North does not beat Austria on that metric** — it is roughly 0.8×, not
1.05×. §8.8's Italy row should be corrected to ~33 with a measured 16.9 GW
denominator. This does not make the replication pointless (it is still the
closest system with free zonal day-ahead forecast data, and by the α calculation
above it is the *more* sensitive test), but the stated premise for choosing it
was wrong.

---

## 6. Full output

```
GATE - Nov-Dec night hours, day-ahead forecast error
  mean load : 16,154 MW
  bias      : -196.4 MW
  sd        : 389.5 MW
  MAE       : 350.1 MW (2.17% of load)
  sd after hour/dow/season FE : 318.0 MW
  implied alpha pass mark, 7 seasons : 21.4%

8.3 - night bias by month (MW, +- s.e.)
  10:-197+-14  11:-190+-16  12:-204+-20
8.3 - Nov 1 - Dec 30 in 10-day bins (Dec 31 excluded)
            mean   sem  count
Nov 1-10  -144.9  23.6     70
Nov 11-20 -220.1  25.8     70
Nov 21-30 -205.3  34.2     70
Dec 1-10  -142.7  35.9     70
Dec 11-20 -237.5  33.9     70
Dec 21-30 -232.2  31.3     70

night panel: 420 nights across 7 seasons, 21 campaign starts
  cum_cold_h at season end (median across seasons): 1326 h

=== PRIMARY - Nov-Dec, all nights  (n=420) ===
              Coef.  Std.Err.     z  P>|z|
below        -25.85     55.27 -0.47   0.64
cum100        42.01     43.74  0.96   0.34
below:cum100   4.33     10.19  0.42   0.67
dist         -28.69     28.31 -1.01   0.31
below:dist    15.85     28.43  0.56   0.58
holiday      -27.97     71.43 -0.39   0.70

=== Bandwidth |wb+2| <= 3 C  (n=200) ===
               Coef.  Std.Err.     z  P>|z|
below        -179.22     70.47 -2.54   0.01
cum100         45.45     52.27  0.87   0.38
below:cum100    7.75     10.27  0.75   0.45
dist         -126.37     41.57 -3.04   0.00
below:dist     82.60     45.78  1.80   0.07
holiday      -106.22    109.09 -0.97   0.33

=== With campaign-start dummy  (n=420) ===
                Coef.  Std.Err.     z  P>|z|
below          -17.81     55.87 -0.32   0.75
cum100          39.18     43.81  0.89   0.37
below:cum100     3.86     10.20  0.38   0.71
dist           -28.57     28.31 -1.01   0.31
below:dist      16.40     28.41  0.58   0.56
holiday        -24.71     71.34 -0.35   0.73
campaign_start -53.07     54.09 -0.98   0.33

=== Seasons 2022-2025 only (late-half analogue)  (n=240) ===
              Coef.  Std.Err.     z  P>|z|
below        -23.74     76.41 -0.31   0.76
cum100       -72.81     52.38 -1.39   0.16
below:cum100  10.85     14.86  0.73   0.47
dist         -31.07     51.10 -0.61   0.54
below:dist    22.54     51.33  0.44   0.66
holiday      -68.45     83.58 -0.82   0.41

=== Campaign start + second night  (n=420) ===
                 Coef.  Std.Err.     z  P>|z|
below           -16.55     55.58 -0.30   0.77
cum100           33.59     43.59  0.77   0.44
below:cum100      4.13     10.15  0.41   0.68
dist            -30.14     28.50 -1.06   0.29
below:dist       18.33     28.62  0.64   0.52
holiday         -21.72     71.39 -0.30   0.76
campaign_start  -61.49     54.69 -1.12   0.26
campaign_night2 -63.61     46.68 -1.36   0.17

=== PRIMARY, 20-station index  (n=420) ===
              Coef.  Std.Err.     z  P>|z|
below         28.86     48.29  0.60   0.55
cum100         2.53     36.71  0.07   0.95
below:cum100   8.60      9.63  0.89   0.37
dist          -7.17     20.52 -0.35   0.73
below:dist    -4.26     20.95 -0.20   0.84
holiday      -42.19     73.69 -0.57   0.57
```

**One coefficient in that block should not be over-read.** In the narrow-bandwidth
cut, `below` = −179 (p = 0.01) and `dist` = −126 (p = 0.00). It is the wrong sign
for snowmaking (which predicts *positive* `below`), it does not appear in the full
sample, it does not appear in the 20-station index, and `below`, `dist` and
`below:dist` are strongly collinear once the bandwidth is narrowed to ±3 °C. It is
a bandwidth artefact, not a finding.

---

## 7. Reproducing

```
pip install pandas numpy requests statsmodels
python src/it_north/it_pipeline.py
```

No API keys. Cache defaults to
`C:\Users\bcris\.claude-snow\jobs\11224758\tmp\it_cache` (change `CACHE` at the
top of the script). Outputs `night_panel_it.csv` and
`night_panel_it_20stations.csv` next to the script. First run is ~15 minutes,
almost all of it South Tyrol station pulls; later runs are seconds.

**Not cross-checked against ENTSO-E.** The Transparency Platform publishes the
same two series (6.1.A actual, 6.1.B day-ahead forecast) for the IT-North bidding
zone and would be an independent check on Terna's numbers, but its REST API needs
a token issued by email on a ~3-working-day approval cycle (see
`notes/entsoe-token-request.md`). No token was available, so the Terna series is
uncorroborated by a second publisher.
