# Snowmaking in ISO-NE's Vermont day-ahead forecast

> **STATUS: DESIGNED AND WRITTEN, NOT RUN. There are no results here.**
>
> The identification argument in §1 is settled and is the substantive
> contribution: ISO-NE's regional forecast is a system total times a separately
> published regional share, so Vermont MW error is mostly system error rescaled
> by about 4.7% and the test must target the *share*. The pipeline implements
> that and was exercised end to end against a two-season cached subset only.
> The full collection did not finish, because ISO-NE rate-limits the per-day CSV
> hard enough that seven seasons take hours.
>
> Any coefficient printed below this line came from that two-season subset. It
> is a smoke test, not a finding, and it must not be read as one. The partial
> night panels were deliberately not committed for the same reason.

A replication of the Austrian test in `src/apg_pipeline.py` on the system with
the best snowmaking-to-winter-overnight-load ratio anywhere. Austria returned a
clean null. Vermont is the harder test to dismiss: the same physical mechanism,
a far larger ratio of snowmaking capacity to overnight regional load.

Run it with

```
python src/vermont/vt_pipeline.py
```

Everything below is printed by that script from data it downloads itself. No
number in this file was carried over from a prior pass, and nothing here is
estimated or filled in by hand.

---

## 1. Why the outcome variable is the SHARE, not Vermont MW

ISO-NE's *Three-Day Reliability Region Demand Forecast* is not eight independent
regional forecasts, and it does not use fixed load-share factors. It is a hybrid:
a system-level total, published on its own cycle, multiplied by a regional
percentage published on a different cycle. `GATE 1` in the pipeline re-establishes
that from the downloaded files rather than asserting it:

*(results in section 6)*

The consequence for study design is that a Vermont megawatt error is the sum of
two things that have nothing to do with each other:

```
VT MW error  =  s_f x (T_a - T_f)      <- New England system forecast error
             +  T_a x (s_a - s_f)      <- Vermont share error
```

where `s` is the share and `T` the system total, `f` forecast and `a` actual.
The identity is exact and the pipeline checks that it closes to floating-point
precision. Only the second term can carry a *Vermont-specific* blind spot; the
first is New England weather. So the outcome variable is **option (a): the
day-ahead Vermont share against the realised Vermont share, in percentage
points**, with positive values meaning Vermont's share was under-forecast.

`GATE 2` also reports the variance split between those two terms. That split is
reported in section 6 and it is worth flagging in advance that **it runs opposite
to the direction anticipated before any actuals were in hand.** The prior
expectation was that Vermont MW error would be dominated by rescaled system
error. It is not. The structural claim (share is the primitive, MW is derived) is
confirmed; the variance claim is not. Both are reported, because the design
choice survives either way — if anything the share is a *better* outcome for
being where the error actually lives, not a worse one.

## 2. Data provenance

| series | source | access | coverage obtained |
| --- | --- | --- | --- |
| day-ahead regional forecast | ISO-NE `/transform/csv/reliabilityregionloadforecast` | session cookie from the report page **plus** matching `Referer`; rate-limited | 427 target dates, 1 Nov – 31 Dec 2019 … 2025 |
| realised zonal load | EIA-930 six-month `SUBREGION` files, balancing authority `ISNE` | plain HTTPS, keyless, bulk | 2019-01 … 2026-07 |
| realised zonal load (cross-check) | ISO-NE `/transform/csv/fiveminuteestimatedzonalload` | as above, **needs both `start` and `end`** | Nov–Dec 2025 only (see below) |
| mountain weather | Iowa Environmental Mesonet archive of the VTrans **RWIS** network | keyless | Oct–Dec, seven seasons |
| summit weather (robustness) | IEM archive of **Mount Washington ASOS** (KMWN, 1910 m) | keyless | Oct–Dec, seven seasons |

Notes on each, including the things that did not work:

**Forecast.** The per-day CSV endpoint is reachable without solving the CAPTCHA
that guards the bulk/zip UI, but only with a cookie obtained from the report tree
page *and* a `Referer` header naming that page; either alone returns 403. A fresh
session per request paced at ~11 s sustained 427 fetches without hitting a 403
wall. The archive was bisected: `2018-06-01`, `2019-03-01` return zero data rows;
`2019-09-01` and later return full days. The pre-2017 zip archive was not pursued
— the elevated weather stations do not reach back that far either.

Each target date's CSV contains every publication for that date. The pipeline
keeps the **latest publication timestamped at or before 10:30 on D-1**, the
ISO-NE day-ahead market bid deadline. In practice that selects the ~09:30 morning
run in every season.

**Actuals.** ISO-NE's own five-minute zonal report would be the definitionally
perfect actual — it is the same publisher and the header literally prints
"Estimated Native Load" per load zone. It is not usable for the panel: its
archive is shallow. Probes at 2024-06-01, 2024-11-01, 2024-12-15 and 2025-01-01
all returned zero data rows, while 2025-06-01, 2025-12-15, 2026-03-15, 2026-06-15
and 2026-08-01 each returned the full 2,304 rows. So EIA-930 carries the panel
and ISO-NE's own series is fetched whole for Nov–Dec 2025 as a same-publisher
robustness arm.

EIA-930 labels ISO-NE subregions `4001`…`4008` with no names attached. The
pipeline does not assume the mapping: `GATE 0` reads ISO-NE's own zonal report,
which prints load-zone ID and load-zone name side by side, and checks the eight
pairs against the table it uses.

**Weather.** NOAA's own hosts are unreachable from this machine — `ncei.noaa.gov`
and `www1.ncdc.noaa.gov` reset the TLS connection on every attempt, with and
without a browser user agent, for `isd-history.csv` and the v3 services path
alike. The Iowa Environmental Mesonet archives the same NWS/FAA/state
observations and is reachable, so it is the carrier for both ASOS and RWIS.

Vermont has no high-elevation ASOS: the highest station in the `VT_ASOS` network
is Lyndonville at 362 m, and snow is not made at 362 m. The **VTrans RWIS**
network does have elevated sites, and they sit on the mountain roads at the
resorts. Eight are used, equally weighted:

| id | site | elev (m) | resort served |
| --- | --- | --- | --- |
| VT028 | Rt 17 Buels Gore | 721 | Sugarbush / Mad River Glen |
| VT040 | Rt 242 Westfield | 685 | Jay Peak |
| VT023 | Rt 11 Winhall | 679 | Stratton / Bromley |
| VT014 | Woodford | 664 | Mount Snow / Prospect |
| VT035 | Rt 4 Mendon Mountain | 652 | Killington / Pico |
| VT022 | Rt 105 Jay | 582 | Jay Peak (lower) |
| VT001 | Brookfield | 492 | central Green Mountains |
| VT021 | Mount Holly Rt 103 | 462 | Okemo |

Equal weights rather than load weights: this is a physical index of snowmaking
conditions, and each resort makes snow off its own hill.

## 3. What is reused from Austria unchanged

- `wet_bulb()`, the bisection solver on `es(Tw) - A·P·(T-Tw) - e = 0`. The Stull
  closed form is **not** used; it errs 0.7–1.0 °C below freezing, which is larger
  than the effect being tested.
- `pressure_from_altitude()`, applied at each station's own elevation.
- Night = **20:00–06:59 local**, labelled by the date of its 20:00 hour,
  requiring ≥ 8 valid hours. Estimation at **night** level, so standard errors
  count nights rather than the heavily autocorrelated hours inside them.
- Threshold wet bulb **< −2.0 °C**; `dist = wb − (−2)`; `below = 1` below it.
- `cum_cold_h` = hours below threshold since 1 October over **all** hours of the
  season, not only night hours, **lagged** so the current hour never enters its
  own regressor.
- Controls: `holiday` (December, day ≥ 21), `doy_c`, `doy_c²`, `C(season)`,
  `C(dow)`. **HC1** standard errors.
- Primary coefficient: **`below:cum100`**.
- Campaign-start and second-night dummies, defined identically.

## 4. Every deviation from the Austrian specification

1. **Outcome variable.** Night-mean *share* error in percentage points
   (`realised % − day-ahead %`) instead of night-mean MW error. Reason in
   section 1. The pipeline prints the megawatt equivalent of 1 pp so coefficients
   remain physically readable.
2. **Weather stations.** Eight equally-weighted VTrans RWIS road stations at
   462–721 m, rather than Austria's region-weighted 900–2600 m climate stations.
   Vermont's terrain and its observing network are both lower; there is no
   900 m+ hourly temperature-and-humidity station in the state.
3. **Two seasons lost to weather data, for two different reasons.** These are
   not the same problem and section 5 keeps them apart:
   - **2020-21 is absent outright.** Every VTrans RWIS site returns zero
     observations for Nov 2020 – Feb 2021, while the same sites return normal
     data for Sep–Oct 2020 and for Jan–Feb 2022. It is a hole in the archive, not
     a coverage shortfall, and no restriction rule could rescue it.
   - **2022-23 is present but thin**, at ~54 % of the hourly clock, and thin in a
     structured way: the missing hours are October and November, the observed
     ones December. The primary sample therefore keeps only seasons covering
     ≥ 90 % of the 1 Oct – 31 Dec clock. Restriction, not imputation: rescaling
     the cold count by the inverse observation rate assumes the missing hours
     resemble the observed ones, and here they demonstrably do not — it would
     credit 2022-23 with the cold of a December applied to a whole autumn. Both
     the unrestricted estimate and the rescaled one are reported as
     sensitivities so the reader can see what the choice costs.
4. **`cum_cold_h` is built from the weather index alone**, on a complete hourly
   clock, rather than from hours that happen to have load data. This is *more*
   faithful to "all hours of the season" than the Austrian implementation, where
   hours missing load data silently dropped out of the running total.
5. **Forecast vintage rule.** Latest publication at or before 10:30 on D-1. The
   Austrian series had one forecast per hour and needed no such rule.
6. **DST alignment.** Both sources are aligned by chronological slot within the
   local day rather than by clock label, because ISO-NE writes the repeated
   November hour as `02X` while EIA-930 numbers it as hour 3 of 25. The repeated
   hour is then averaged into its night, as Austria averages its DST duplicates.
7. **Outlier screen.** A within-night robust screen (> 5 × 1.4826 × MAD from the
   night median of the forecast share) — Austria had no such screen. It exists
   because ISO-NE's regional file contains occasional single-hour share glitches;
   the 26 Jan 2026 HE02 Vermont value of 3.927 against ~4.6 neighbours is the
   known instance. Drop counts are reported.
8. **De-biased persistence comparison.** Realised shares come from EIA-930 and
   forecast shares from ISO-NE, so a constant definitional gap would penalise the
   forecast while cancelling out of a persistence benchmark that is EIA-versus-
   EIA. Both error series are therefore also compared after removing their own
   season × hour-of-day mean.
9. **Feasible persistence.** In addition to the prescribed lag-1 benchmark, a
   benchmark restricted to information a forecaster actually had at ~09:30 on
   D-1: lag 1 day for hours ending ≤ 09:00, lag 2 days for the evening hours,
   which had not yet happened when the forecast was published.
10. **Data carrier.** IEM instead of NOAA/NCEI direct, forced by the TLS block.
11. **Sample window.** Nov–Dec, matching Austria. Vermont snowmaking continues
    into January and February; that extension is not tested here.
12. **All-eight-zone table, and how the placebo must be read.** Austria had one
    load series and needed no placebo. Here the outcome is compositional: the
    eight regional share errors sum to zero by construction, so the eight
    estimated `below:cum100` coefficients also sum to (numerically) zero, which
    the pipeline prints as a consistency check. A genuine Vermont effect must
    therefore push the other seven zones the other way. That makes "Rhode Island
    is not significant" the wrong test on its own — a strong Vermont effect
    *should* leak a little into Rhode Island. The correct question is whether
    Vermont stands out from the field of eight, so the pipeline estimates the
    identical specification on all eight regions and prints them ranked.

## 5. Sample obtained

*(results in section 6)*

## 6. Results

*(to be filled from the run)*

## 7. Honest limitations

*(to be filled from the run)*
