# Swiss replication — snowmaking in the day-ahead load forecast

Replication of the Austrian test (`../apg_pipeline.py`, README §8) for Switzerland.
Same question: is ski-resort snowmaking a systematic blind spot in the day-ahead
electricity **load forecast**?

Run it with:

```
python src/swiss/ch_pipeline.py
```

Everything below is the actual printed output of that script. Nothing is
estimated by hand or carried over from Austria.

---

## Headline, stated up front

Three things, in the order that matters:

1. **The sanity gate FAILED.** The `holiday` coefficient on the forecast error is
   **+28.9 MW (se 74.1, z = +0.39)** — not negative, not significant. The
   pre-registered rule says: report the breakage, not a finding. So this
   document reports breakage.
2. **The gate failure is diagnosed, and it is not a coding bug.** The Christmas
   shutdown is unambiguously present in the Swiss *load* (holiday = **−197.7 MW**,
   z = −2.93), which proves the local-time conversion, the 20:00–06:59 night
   construction, the holiday flag and the panel all work. It is absent from the
   *error* because the Swiss day-ahead forecast **anticipates the shutdown**
   (holiday on forecast = **−226.6 MW**, z = −3.58). The gate's premise — a
   forecaster that misses Christmas — is an Austrian fact, not a Swiss one.
3. **The test could never have detected Swiss snowmaking anyway.** MDE = **313.9 MW**
   against a plausible coincident Swiss snowmaking load of **~200 MW**. The
   required α is **157 %**. Even if the forecast modelled *none* of Swiss
   snowmaking, the signal would be smaller than this sample can resolve.

The specification did return a significant negative primary coefficient
(`below:cum100` = −42.45, z = −2.97). **It is not evidence of the hypothesis.**
Section "Why the significant coefficient is not the finding" below shows that it
implies a seasonal swing 1.6× larger than the entire Swiss snowmaking fleet
(2.1× when measured on the load level itself), which no amount of snowmaking can
produce.

---

## 1. Data provenance and exact endpoints

### Load and day-ahead load forecast — energy-charts.info (Fraunhofer ISE)

Free, no token, no registration. Two requests, one wide window each, spaced 30 s
apart (CH is rate limited at roughly 16 requests; 429s follow).

```
https://api.energy-charts.info/public_power_forecast?country=ch&production_type=load&forecast_type=day-ahead&start=2015-01-01&end=2026-01-05
https://api.energy-charts.info/public_power?country=ch&start=2015-01-01&end=2026-01-05
```

The second returns a `production_types` array; the series used is the one named
exactly `"Load"`. Underlying source is the ENTSO-E Transparency Platform
(Swissgrid as data provider).

- Resolution: **hourly**, 24 points/day. Timestamps are `unix_seconds` (UTC).
- Data floor: **2015-01-01T00:00Z** exactly, for both endpoints. Earlier starts
  return HTTP 400.
- Raw rows returned: **96,551**. Usable after dropping nulls and non-positive
  values in either series: **96,527** (24 dropped).
- `err = actual − forecast`, so `err > 0` means the load was under-forecast.

Both series arrive on the same epoch grid, so they are joined on **UTC** and
converted to `Europe/Zurich` exactly once, for night labelling only.

### Weather — MeteoSwiss open government data (SMN network)

MeteoSwiss IDAWEB requires registration; the open alternative used here does not.
The automatic monitoring network (SwissMetNet, SMN) is published as open data on
`data.geo.admin.ch` under collection `ch.meteoschweiz.ogd-smn`, licence
"Opendata BY" (free use with source attribution).

Station metadata:

```
https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/ogd-smn_meta_stations.csv
```

Hourly measurements, two files per station covering 2015–2025:

```
https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/<abbr>/ogd-smn_<abbr>_h_historical_2010-2019.csv
https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/<abbr>/ogd-smn_<abbr>_h_historical_2020-2029.csv
```

(`<abbr>` lower-cased, e.g. `dav` for Davos.) The `2020-2029` file already runs
through **2025-12-31 23:00**, so no `_recent` file is needed and the 2025 season
is complete. Semicolon-separated; parameters used:

| Column | Meaning |
|---|---|
| `reference_timestamp` | `DD.MM.YYYY HH:MM`, **UTC** |
| `tre200h0` | air temperature 2 m, hourly mean, °C |
| `ure200h0` | relative humidity 2 m, hourly mean, % |

**UTC verified empirically, not assumed.** The July diurnal cycle at Davos peaks
at stamped hour 14 and bottoms at stamped hour 4 — i.e. 16:00 and 06:00 CEST,
which is right for a mountain valley. Local stamping would have put the peak at
12 UTC and the minimum two hours before sunrise. Combined with the load series
being joined on epoch seconds, there is no wall-clock string join anywhere in
this pipeline.

---

## 2. Seasons obtained

Eleven complete Nov–Dec seasons are available, **2015–2025**. Nine are analysed.

**Two seasons were rejected as fake forecasts.** From 2021-09-01 through
2022-12-31 the published CH "day-ahead load forecast" is not a forecast: the ratio
actual/forecast is pinned to a constant — **1.06052 for Sep–Nov 2021**, **1.05969
for Dec 2021** (monthly ratio sd 4.6 × 10⁻⁴, i.e. the factor is reset once inside
December rather than drifting), and **1.05080 to five decimals for every month of
2022**. The published forecast is the *realised load rescaled by a fixed factor*.
The pipeline detects this automatically from the
standard deviation of actual/forecast over Oct–Dec and prints the table:

```
      ratio_mean  ratio_sd  hours             verdict
Y
2015     1.01388   0.08945   2209                keep
2016     1.02610   0.06546   2209                keep
2017     1.07620   0.07879   2209                keep
2018     1.02407   0.06879   2209                keep
2019     1.05835   0.07416   2209                keep
2020     1.05956   0.07818   2209                keep
2021     1.06025   0.00043   2209  DROP (placeholder)
2022     1.05080   0.00001   2209  DROP (placeholder)
2023     1.01125   0.10137   2209                keep
2024     1.03055   0.12788   2209                keep
2025     1.03860   0.08260   2209                keep
```

A genuine forecast gives a ratio sd of 0.065–0.128. The threshold is 0.005; the
two rejected seasons are three to four orders of magnitude below it. Keeping them
would have made `err` a deterministic linear function of realised load for 2/11 of
the sample. **Analysis sample: 9 seasons, 540 nights.**

---

## 3. Weather stations and region weighting

### Region weighting: EQUAL, and here is why

**No published split of Swiss skier visits by region was findable.** Two searches
were run:

- *"Seilbahnen Schweiz skier visits by region Graubünden Wallis Berner Oberland
  share Ersteintritte"* — returned only year-on-year **growth rates** by region
  (e.g. winter 2024/25: Bernese Oberland +18 %, Eastern Switzerland +14 %,
  Ticino +11 %, Valais +9 %, Graubünden +3 %), never levels or shares.
- *"Switzerland skier days by region Valais Grisons percentage share skier visits
  Vanat report"* — returned revenue growth comparisons and pointers to the Vanat
  *International Report on Snow & Mountain Tourism*, but no regional share table.

Seilbahnen Schweiz publishes *first entries* (Ersteintritte) only as indices and
growth rates in its public releases; the Austrian pipeline's skier-visit weights
(Tirol 0.50, Salzburg 0.24, …) have no sourceable Swiss counterpart. **So every
canton gets weight 1/8, and stations inside a canton split that weight evenly.**
This is stated here rather than buried because it is a real limitation: it
over-weights small ski cantons (GL, FR, OW, VD) relative to Graubünden and Valais,
which between them carry most Swiss lift capacity.

### Station selection rule

Mechanical, from the metadata CSV:

1. Station type = "Automatic weather stations".
2. Altitude in **900–2600 m** (the Austrian band, unchanged — valley stations
   would manufacture a null).
3. Canton in the ski set **{GR, VS, BE, VD, UR, OW, FR, GL}**. Excluded: **TI**
   (negligible snowmaking); **NE, ZH, LU, SZ, AI** (Jura, Napf and pre-alpine
   ridges with marginal or no lift-served terrain).
4. `station_data_since ≤ 2015-10-01`, so every station covers every season.
5. Six named stations dropped by hand — the only hand adjustment: **CHA**
   (Chasseral, Jura ridge), **NAP** (Napf, Emmental ridge), **BAN** (Bantiger,
   hill above the city of Bern), **DOL** (La Dôle, Jura), **FRE** (La Frétaz,
   Jura), **CHB** (Les Charbonnières, Vallée de Joux). They sit inside kept
   cantons and inside the altitude band but have no snowmaking infrastructure
   beneath them, so their wet bulb tracks weather no snow gun responds to.
6. Top 4 by altitude per remaining canton.

Result — 20 stations:

| id | name | canton | altitude m | weight |
|---|---|---|---|---|
| GRH | Grimsel Hospiz | BE | 1980 | 0.0625 |
| ABO | Adelboden | BE | 1321 | 0.0625 |
| MLS | Le Moléson | FR | 1974 | 0.0625 |
| PLF | Plaffeien | FR | 1042 | 0.0625 |
| ELM | Elm | GL | 958 | 0.1250 |
| CMA | Crap Masegn | GR | 2468 | 0.0312 |
| NAS | Naluns / Schlivera | GR | 2380 | 0.0312 |
| BEH | Passo del Bernina | GR | 2260 | 0.0312 |
| BUF | Buffalora | GR | 1971 | 0.0312 |
| PIL | Pilatus | OW | 2105 | 0.0625 |
| ENG | Engelberg | OW | 1036 | 0.0625 |
| GUE | Gütsch, Andermatt | UR | 2286 | 0.0417 |
| ANT | Andermatt | UR | 1435 | 0.0417 |
| GOS | Göschenen | UR | 950 | 0.0417 |
| CDM | Col des Mosses | VD | 1412 | 0.0625 |
| CHD | Château-d'Oex | VD | 1028 | 0.0625 |
| GSB | Col du Grand St-Bernard | VS | 2472 | 0.0312 |
| EVO | Evolène / Villa | VS | 1825 | 0.0312 |
| ZER | Zermatt | VS | 1638 | 0.0312 |
| GRC | Grächen | VS | 1605 | 0.0312 |

Resulting index: **24,299 hourly observations**, **30.6 %** of them below the
−2.0 °C wet-bulb threshold.

---

## 4. Deviations from the Austrian specification

Reused **unchanged**: `wet_bulb()` bisection on
`es(Tw) − A·P·(T−Tw) − e = 0` with `A = 6.53e-4·(1 + 9.44e-4·Tw)` over water (no
Stull closed form); `pressure_from_altitude()` ISA correction; 900–2600 m band;
threshold wb < −2.0 °C with `below` and `dist = wb − (−2)`; night = 20:00–06:59
**local**, labelled by the date of its 20:00 hour, ≥ 8 valid hours; night-level
estimation; `cum_cold_h` accumulated from 1 October over **all** hours of the
season and **lagged**; `cum100 = (cum_cold_h − median)/100`; `holiday` = December
day ≥ 21; the formula
`err ~ below*cum100 + dist + below:dist + holiday + doy_c + I(doy_c**2) + C(season) + C(dow)`
with HC1 standard errors; and the `campaign_start` / `campaign_night2` construction.

| # | Deviation | Why |
|---|---|---|
| 1 | Load from energy-charts.info (ENTSO-E/Swissgrid) instead of APG ZIPs | There is no Swiss APG. Same object: hourly actual load and hourly day-ahead load forecast for one control area. |
| 2 | Join on UTC epoch, convert to `Europe/Zurich` once | Both Swiss sources are natively UTC. The Austrian pipeline joined local wall-clock strings and had to fold the DST-repeated `2A`/`2B` hour. Identical *definition*, cleaner *mechanics*, one less failure mode. |
| 3 | Weather from MeteoSwiss OGD SMN instead of GeoSphere | Austrian equivalent for Switzerland. IDAWEB (the registration-gated archive) was **not** used. |
| 4 | Canton weights equal (1/8) instead of skier-visit weights | No sourceable Swiss skier-visit share (§3). Documented, not silent. |
| 5 | 9 analysed seasons, not 11 | 2021 and 2022 forecasts are rescaled copies of actual load (§2). Automatic, threshold-based, printed. |
| 6 | Six named stations excluded by hand | Jura/pre-alpine ridges inside kept cantons (§3). |
| 7 | The "seasons 2016–2022 only" specification is **dropped** | That Austrian specification exists only to test the AT–DE bidding-zone split of 1 Oct 2018. Switzerland has no analogous structural break, so the subset would be arbitrary. Four specifications are run instead of five. |
| 8 | Measured station pressure (`prestah0`) available but **not** used | MeteoSwiss publishes true station pressure, which would be marginally better than the ISA profile. The Austrian spec says `pressure_from_altitude()`, so `pressure_from_altitude()` is what runs. Noted for anyone who wants the robustness check. |

---

## 5. Gate statistics

Nov–Dec night hours (20:00–06:59 local), 9 usable seasons:

```
  night hours   : 6,039 over 9 seasons
  mean load     : 7,683 MW
  bias          : +215.5 MW
  sd            : 634.2 MW
  MAE           : 513.8 MW (6.69% of load)
```

For scale: the measured DE-LU day-ahead load-forecast MAE is 3.14 % of load. The
Swiss series is **more than twice as noisy**, and the forecast is badly
calibrated at night-to-night frequency:

```
    actual on forecast slope : 0.714 (se 0.043); a calibrated forecast gives 1.000
    corr(err, actual)        : +0.584; an unbiased forecast gives ~0
      2015  slope 0.350  R2 0.086  sd(err) 548 MW
      2016  slope 0.567  R2 0.700  sd(err) 310 MW
      2017  slope 0.652  R2 0.452  sd(err) 333 MW
      2018  slope 0.955  R2 0.533  sd(err) 307 MW
      2019  slope 0.624  R2 0.451  sd(err) 335 MW
      2020  slope 0.979  R2 0.707  sd(err) 266 MW
      2023  slope 0.446  R2 0.188  sd(err) 425 MW
      2024  slope 0.899  R2 0.225  sd(err) 635 MW
      2025  slope 1.098  R2 0.682  sd(err) 329 MW
```

Night-level descriptives (all months, all usable seasons; MW ± s.e.):

```
  01:+395+-22  02:+314+-24  03:+381+-22  04:+326+-26  05:+242+-24  06:+406+-22
  07:+159+-23  08:+102+-22  09:+14+-28   10:+243+-26  11:+235+-28  12:+196+-26

Nov 1 - Dec 30 in 10-day bins (Dec 31 excluded)
            mean   sem  count
Nov 1-10    93.3  54.2     90
Nov 11-20  172.4  42.8     90
Nov 21-30  438.8  40.7     90
Dec 1-10   247.2  50.7     90
Dec 11-20  228.5  39.9     90
Dec 21-30  114.2  47.3     90
```

Night panel: **540 nights, 9 seasons, 42 campaign starts.**

---

## 6. The MDE verdict — this test was never capable of a finding

Same detectability logic as `../power.py`, with Swiss numbers measured from this
sample rather than assumed:

```
  sd after hour/dow/season FE       : 587.5 MW
  episodes assumed  9/season x 9 seasons  = 81
  hours/episode 8, rho 0.7, Z 2.8 (80% power / 5% two-sided)
  episode-mean sd                   : 504.5 MW
  MDE                               : 313.9 MW
  CH coincident snowmaking load S   : 200 MW (900 MW x 62.5/281.0 GWh)
  alpha needed = MDE / S            : 157%
  (same MDE against the Austrian S = 900 MW would need alpha 35%)
```

`S` is anchored the same way Austria's was. Austria's 281 GWh/season of
snowmaking energy was matched to a 900 MW coincident overnight snowmaking load;
Switzerland's published 60–65 GWh (midpoint 62.5) scales that to
900 × 62.5/281 ≈ **200 MW**.

**Verdict, stated plainly: no. The Swiss test could not have detected an effect of
the plausible size at all.** The α required is 157 % — greater than one. α is the
share of the snowmaking load the day-ahead forecast has *not* already absorbed
through its temperature and lagged-load terms, so it is bounded above by 100 %.
Even a forecaster that modelled **zero** of Swiss snowmaking would produce a
residual signal smaller than this sample can resolve at 80 % power.

Two things made this worse than the desk scoping suggested. Switzerland's
7.1–7.7 GWh of snowmaking per GW of winter overnight load is already ~6× worse
than Austria's 43, and Austria at 43 was already a null. On top of that, the Swiss
forecast-error series is twice as noisy as the German benchmark and 2 of 11
seasons had to be thrown away. Ratio-wise the Austrian sample would have needed
α = 29 % to see its own effect; the Swiss sample needs α = 35 % to see an
*Austrian-sized* effect, and 157 % to see its own.

**A null here would carry no information.** It would be the null of a test that
had no power, not evidence that snowmaking is visible to no forecaster.

---

## 7. Sanity gate — FAILED

The gate is non-negotiable and it did not pass.

```
  8a. Christmas gate, same controls, three regressands
    holiday on err    :    +28.9 MW  (se  74.1, z +0.39)
    holiday on actual :   -197.7 MW  (se  67.5, z -2.93)
    holiday on fcst   :   -226.6 MW  (se  63.3, z -3.58)
```

Austria, for comparison (parent README §8.4): `holiday` on `err` = **−273.6**
(se 84.0), t = −3.26.

**Diagnosis.** The failure is located, and it is not a broken pipeline:

- The Christmas industrial shutdown is present in the Swiss **load** at
  −197.7 MW, z = −2.93. That single number certifies the machinery — UTC→local
  conversion, the 20:00–06:59 night with its 20:00-date label, the ≥ 8-hour
  filter, the December-≥21 holiday flag, the season/dow fixed effects. A pipeline
  with a timezone or night-labelling bug could not recover a clean holiday effect
  in the level.
- The Swiss day-ahead **forecast** anticipates the shutdown at −226.6 MW, z = −3.58 —
  slightly *more* than the actual drop.
- −197.7 − (−226.6) = +28.9, which is exactly the `err` coefficient. Nothing is
  left over.

So the gate's premise fails on Swiss data. It assumes a forecaster that misses
Christmas; Swissgrid's day-ahead forecast does not. That is an Austrian
regularity generalised into a universal check, and Switzerland is the
counterexample.

**Per the pre-registered rule, this is reported as breakage.** The specification
coefficients below are printed for completeness and audit. They are **not**
offered as a finding, and no claim in this document rests on them.

---

## 8. Results (reported for audit, not as a finding)

`err ~ below*cum100 + dist + below:dist + holiday + doy_c + doy_c² + C(season) + C(dow)`,
night-level, HC1 standard errors, 9 seasons, Nov–Dec.

**Specification 1 — PRIMARY, all nights (n = 540)**

| term | coef | s.e. | z | P>\|z\| |
|---|---|---|---|---|
| below | −66.25 | 53.49 | −1.24 | 0.22 |
| cum100 | −20.00 | 30.28 | −0.66 | 0.51 |
| **below:cum100** | **−42.45** | **14.28** | **−2.97** | **0.00** |
| dist | +19.46 | 13.80 | +1.41 | 0.16 |
| below:dist | −40.00 | 17.03 | −2.35 | 0.02 |
| holiday | −4.31 | 74.74 | −0.06 | 0.95 |

**Specification 2 — bandwidth \|wb+2\| ≤ 3 °C (n = 319)**

| term | coef | s.e. | z | P>\|z\| |
|---|---|---|---|---|
| below | +43.75 | 72.30 | +0.61 | 0.55 |
| cum100 | +19.11 | 34.52 | +0.55 | 0.58 |
| **below:cum100** | **−34.12** | **18.24** | **−1.87** | **0.06** |
| dist | +64.51 | 46.55 | +1.39 | 0.17 |
| below:dist | −51.51 | 53.11 | −0.97 | 0.33 |
| holiday | +3.54 | 85.25 | +0.04 | 0.97 |

**Specification 3 — with campaign-start dummy (n = 540)**

| term | coef | s.e. | z | P>\|z\| |
|---|---|---|---|---|
| below | −92.44 | 55.41 | −1.67 | 0.10 |
| cum100 | −14.90 | 30.39 | −0.49 | 0.62 |
| **below:cum100** | **−41.38** | **14.41** | **−2.87** | **0.00** |
| dist | +19.36 | 13.82 | +1.40 | 0.16 |
| below:dist | −43.06 | 17.09 | −2.52 | 0.01 |
| holiday | −5.87 | 75.08 | −0.08 | 0.94 |
| campaign_start | +101.50 | 61.23 | +1.66 | 0.10 |

**Specification 4 — campaign start + second night (n = 540)**

| term | coef | s.e. | z | P>\|z\| |
|---|---|---|---|---|
| below | −99.21 | 55.52 | −1.79 | 0.07 |
| cum100 | −11.82 | 30.12 | −0.39 | 0.69 |
| **below:cum100** | **−40.73** | **14.35** | **−2.84** | **0.00** |
| dist | +19.30 | 13.81 | +1.40 | 0.16 |
| below:dist | −43.12 | 17.10 | −2.52 | 0.01 |
| holiday | −9.66 | 75.46 | −0.13 | 0.90 |
| campaign_start | +112.38 | 61.37 | +1.83 | 0.07 |
| campaign_night2 | +63.84 | 78.35 | +0.81 | 0.42 |

---

## 9. Why the significant coefficient is not the finding

`below:cum100` came back **−42.45 (14.28), z = −2.97**, with the predicted sign
and p < 0.01, stable across all four specifications. That is the result the study
predicted. It should still not be believed, for four independent reasons.

**(a) The gate failed.** The pre-registered rule is unconditional: if `holiday`
does not come back strongly negative, report breakage. Reading a significant
primary coefficient out of a specification whose own sanity check failed is
exactly the failure mode the gate exists to prevent.

**(b) It is far too big to be snowmaking — and the load level makes that
unmistakable.** Running the identical specification with three regressands:

```
    below:cum100 on err    :   -42.45 MW/100 h  (se 14.28, z -2.97)
    below:cum100 on actual :   -56.24 MW/100 h  (se 13.09, z -4.30)
    below:cum100 on fcst   :   -13.79 MW/100 h  (se 10.34, z -1.33)
```

A caveat first, because it cuts against a tempting reading: **this decomposition
does not on its own separate snowmaking from anything else.** Snowmaking is real
load, so a genuine forecast blind spot would show exactly this signature —
present in the level, largely absent from the forecast, surviving in the error.
The pattern "level > error > forecast" is not disqualifying.

What *is* disqualifying is magnitude. `cum100` spans −2.54 to +7.51 in this
sample, so:

```
    below:cum100 on err    = -42.45 -> implied swing  +108 .. -319 MW
    below:cum100 on actual = -56.24 -> implied swing  +143 .. -423 MW
    entire plausible CH coincident snowmaking load S =  200 MW
```

The load-level estimate implies a **−423 MW** swing across the season, **2.1×**
the entire Swiss coincident snowmaking fleet; the error-level estimate implies
**−319 MW**, **1.6×** the fleet. The majority of this pattern therefore cannot be
snowmaking under any α. It is a seasonal load–weather interaction — the shape a
heating ramp interacting with accumulated cold produces — of which snowmaking
could at most be a minority component, and one this sample cannot isolate.

**(c) The error inherits it through a badly calibrated forecast, not through a
snowmaking-specific blind spot.** The Swiss night-level forecast has a
calibration slope of **0.714** (a calibrated forecast gives 1.000) and
**corr(err, load) = +0.584** (an unbiased forecast gives ~0). A forecast that
systematically under-responds to load variation will pass through *any*
load–weather structure into `err` with a large gain. That mechanism explains the
error coefficient without invoking snowmaking at all, and it also explains why
`dist` and `below:dist` come back significant — plain temperature terms, with no
snowmaking interpretation, behave the same way.

**(d) The power calculation says the real signal is invisible here.** The binding
statement is the level-based MDE of §6: **313.9 MW against a 200 MW ceiling,
α = 157 %**. For context, the 80 %-power MDE on this single coefficient is
**40.0 MW per 100 cold-hours**, so the estimate does clear its own coefficient-level
bar — but clearing it is not informative, because what the coefficient is
detecting (a ~400 MW seasonal load–weather swing) is roughly an order of magnitude
larger than the snowmaking signal the study set out to find. The test is
well-powered for the confound and underpowered for the effect.

---

## 10. Conclusion

- **The Swiss replication does not produce a usable result, and it was not going
  to.** The MDE calculation, done before looking at any coefficient, puts the
  required α at 157 %. This is an underpowered test by construction, exactly as
  the expectations section anticipated, and worse than the 6×-versus-Austria
  scoping implied because the Swiss error series is unusually noisy and two of
  eleven seasons are unusable.
- **The sanity gate failed**, and the reason is a genuine Swiss/Austrian
  difference — Swissgrid's day-ahead forecast anticipates the Christmas
  shutdown — not a defect in this code. Under the pre-registered rule the
  specification output is not reportable as a finding, and it is not reported as
  one here.
- **The significant primary coefficient is a confound, not the effect.** It
  implies a seasonal swing of −319 MW in the error and −423 MW in the load level
  — 1.6× and 2.1× the entire Swiss snowmaking fleet — so the bulk of it cannot be
  snowmaking, and a forecast with a 0.714 calibration slope passes that
  load–weather structure straight into the error.
- **This is not evidence for or against the Austrian null.** Switzerland cannot
  arbitrate that question with these data. The parent study's own ranking already
  said so; this run confirms it with measured numbers instead of scoping
  estimates.

Anyone continuing this line should go where the ratio is favourable and the
forecast is honest — ISO-NE Vermont at 62–140 GWh/GW, with a Rhode Island
placebo inside the same feed — not to another low-ratio European country.

---

## 11. Files

| file | contents |
|---|---|
| `ch_pipeline.py` | end-to-end: download, wet bulb, panel, gate, MDE, four specifications, diagnostics |
| `ch_night_panel.csv` | the 540-night estimation panel, written by the script |

Cache directory (downloads, ~280 MB, not in the repo):
`C:\Users\bcris\.claude-snow\jobs\11224758\tmp\ch_cache\`

Environment: Python 3.14, pandas 3.0.2, numpy 2.4.4, statsmodels 0.14.6,
requests. No pyarrow, no parquet.
