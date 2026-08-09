# Snowmaking in ISO-NE's Vermont day-ahead forecast

> **STATUS: RUN END TO END, 9 August 2026. Sections 5 to 7 are results.**
>
> An earlier version of this file carried a banner saying the pipeline had been
> designed but never run, because ISO-NE rate-limits the per-day CSV hard enough
> that collecting seven seasons takes hours and the first attempt did not
> finish. It has now finished: 427 target dates, five usable seasons, and the
> `night_panel_*.csv` files in this directory are the real panels rather than the
> two-season smoke test that was deliberately withheld.
>
> **Read section 6 before anything else. The pre-registered prediction is met
> here.** The primary interaction is negative and significant at p = 0.004, which
> is the direction section 5 of the root README committed to before any load data
> was opened, and Vermont is the only one of the four markets tested where a
> coefficient of the predicted sign cleared its own detection threshold. Sections
> 6.4 and 6.5 give the reasons to hold it loosely, and by the end of the file
> there are three: it does not survive a change of weather index, it clears its
> own detection threshold by almost nothing, and the same-publisher robustness
> arm in section 7 nearly halves it while making the placebo significant.
> **Suggestive, and weakening.**
>
> **Correction, same day.** The first version of sections 6.2 to 6.5 described
> this coefficient as *rejecting* the prediction with the sign reversed. That was
> a misreading of the pre-registration by the author of that draft, not a change
> of result: the predicted sign is negative, per root README section 5 and the
> kill criterion in section 8.5 that fires on a coefficient that is "zero or
> positive." The numbers below are unchanged from the run; the reading of them is
> corrected. Both commits are in the history.

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

| step | result |
| --- | --- |
| forecast CSVs fetched | 427 target dates, 1 Nov – 31 Dec 2019 … 2025, 554,880 zone-hour publications |
| day-ahead vintage kept | 427 of 427 dates; the chosen publication falls at 09:24–09:29 in every season |
| EIA-930 ISNE actuals | 531,256 zone-hours, 1 Jan 2019 – 29 Jul 2026 |
| matched hourly panel | 82,040 zone-hours over 427 dates |
| RWIS wet-bulb index | 12,151 hours from 8 stations; 40.9 % below −2.0 °C |

Season coverage of the complete 1 Oct – 31 Dec hourly clock, which is what
decides the primary sample:

| season | observed h | coverage | % below −2 °C | cold hours by 31 Dec |
| --- | --- | --- | --- | --- |
| 2019 | 2,206 | 99.9 % | 43.6 | 962 |
| 2020 | 0 | **0.0 %** | – | – |
| 2021 | 2,208 | 100.0 % | 36.1 | 797 |
| 2022 | 1,191 | **53.9 %** | 35.3 | 779 |
| 2023 | 2,206 | 99.9 % | 31.0 | 684 |
| 2024 | 2,170 | 98.3 % | 33.6 | 742 |
| 2025 | 2,170 | 98.3 % | 45.3 | 999 |

The primary sample keeps 2019, 2021, 2023, 2024 and 2025 and drops the two
seasons flagged in section 4.3, for the two different reasons given there. Both
are put back in a reported sensitivity.

**Vermont, primary sample.** 297 nights, of which 183 are below threshold and 27
are campaign starts. 344 nights before the weather restriction. The outlier
screen removed 75 of 4,704 night-hours (1.59 %).

Mean share error **+0.0020 pp** (sd 0.1842), mean realised share **4.880 %**.
Mean night system load is 12,003 MW, so **1 pp of share is 120 MW** and the
standard deviation of the night share error is **22.1 MW**. Every coefficient
below can be read in megawatts by multiplying by 120.

## 6. Results

### 6.1 The gates

**GATE 0.** The eight EIA-930 subregion codes match ISO-NE's own zone names
one for one. The mapping was checked, not assumed.

**GATE 1: the forecast is a hybrid, as section 1 argued.** The eight regional MW
figures sit within 0.003 MW of an exact multiple of 10 for 100.00 % of hours,
and `|MW − pct × total|` never exceeds 0.095 MW across 554,880 zone-hours. So MW
is derived from a rounded system total and a published percentage. Yet the
percentages are not fixed load-share factors: 24.7 % of consecutive revisions of
the same Vermont target hour leave the share byte-identical to three decimals,
and 11 % of *those* nonetheless revise the MW by more than 0.5 MW. Totals and
shares refresh on separate cycles. The Vermont day-ahead share ranges 1.65 % to
6.03 % with a mean of 4.71 %, so it is modelled, not frozen.

**GATE 2: the variance split runs the opposite way to the prior expectation,
exactly as section 1 pre-committed to reporting.** Over 4,704 night hours the
identity closes to 0.085 MW, and:

| | system component | share component |
| --- | --- | --- |
| raw variance | 18.1 % | **88.8 %** |
| de-meaned by season × hour | 17.0 % | **82.7 %** |
| correlation with VT MW error | 0.345 | **0.906** |

The expectation written down before any actuals were in hand was that Vermont MW
error would be dominated by New England system error rescaled to Vermont's ~4.7 %.
It is not. Four fifths of the variance is Vermont's own share error. The
structural claim survives and the variance claim does not, and the design choice
survives either way: the share is a *better* outcome for being where the error
actually lives.

**Baseline skill.** Against raw lag-1 persistence the Vermont day-ahead share
forecast has −5.7 % skill, which is an artifact of the constant definitional gap
between EIA-930 and ISO-NE. After each series is de-meaned by season and
hour-of-day the skill is +1.1 %, and against the *feasible* persistence benchmark
that uses only information available at 09:30 on D-1 it is +9.5 %. The forecast
is barely better than assuming yesterday. Its correlation with the same-day
realised share is 0.398. Off the Friday-to-Saturday transition it moves 62 % of
the true change and its skill goes negative. This is a weak regional model, which
is a favourable condition for the test: a weak forecaster is an easy one to catch
out.

### 6.2 The pre-registered test

    below:cum100  =  -0.0211 pp per 100 cold hours
                     (HC1 s.e. 0.0073, z = -2.89, p = 0.004, n = 297)

**Negative, significant at the 1 % level, and that is the direction the
pre-registration predicted.**

The prediction, fixed in section 5 of the root README before any load data was
opened, is that the threshold effect *shrinks* as season-to-date accumulated cold
rises: the base gets built, the guns stop, and the same cold night draws less
power in late December than in early November. A memoryless temperature model
cannot produce that shape and no heating confound mimics it, which is why the
interaction and not the level is the coefficient the design rests on.

In megawatts, one point of Vermont's share is 120 MW, so the coefficient is
**−2.53 MW per 100 accumulated cold hours**. Across the observed range of
`cum_cold_h`, 0 to 972 hours, the cold-night effect falls by about **25 MW** from
the start of a season to the end of it. The `below` main effect at the median
accumulated cold is **+0.0726 pp (s.e. 0.0288, p = 0.012)**, or +8.7 MW, so
extrapolated back to the start of a season a below-threshold night is
under-forecast by roughly 17 MW and by the end of one is not. Against a fleet
whose coincident draw is estimated at 30–110 MW, that is an unexplained share α of
somewhere between a sixth and a half early in the season. The `below` level is
the contaminated coefficient section 4 of the root README warns about, so it is
read as a scale for the interaction and not as evidence on its own.

It is stable across the specification variants: −0.0208 with the campaign-start
dummy, −0.0210 with campaign start plus second night, −0.0232 (p = 0.001) with
the low-coverage seasons put back. The bandwidth restriction to |wb + 2| ≤ 3 °C
halves it and loses significance (−0.0139, s.e. 0.0104), which is what a
122-night subsample does to any of these.

**The placebo is clean.** Rhode Island, which makes no snow, returns
+0.0019 (0.0037), p = 0.61, and stays null in every variant.

**Multiplicity.** Four markets were tested on this coefficient. A Bonferroni
correction across the four puts Vermont at p = 0.016, still under 5 %. That is
the whole correction, and it is the right family: the four markets were the
pre-planned replication set, not a search.

### 6.3 Supporting prediction 1 is also met

The pre-registration's first supporting prediction is that the error spikes on
the first night of a campaign and decays over the following 24 to 48 hours,
because APG-style autoregressive forecasts have not yet caught up on night one.
A temperature confound gives a flat profile instead.

| term | coefficient (pp) | s.e. | p | in MW |
| --- | --- | --- | --- | --- |
| `campaign_start`, first night of a cold snap | **+0.0757** | 0.0313 | **0.016** | +9.1 |
| `campaign_night2` | +0.0476 | 0.0312 | 0.127 | +5.7 |

Positive, larger on night one, smaller on night two, which is the predicted
shape. Rhode Island returns −0.0125 (0.0161) and −0.0177 (0.0151), both null.

Held loosely: this rests on 27 campaign starts, the night-two coefficient is not
significant on its own, and two points do not establish a decay curve. It is
consistent with the prediction rather than a demonstration of it.

### 6.4 Four reasons to hold all of this loosely

A result that agrees with the hypothesis deserves harder scrutiny than one that
does not. Everything in this subsection was run **after** seeing 6.2 and is
labelled POST-HOC in the pipeline output. The design commit for this pipeline
predates it in the git history, which is the only reason the distinction is
checkable.

**1. It does not survive a change of weather index, and this is the real
problem.** Swapping the eight Vermont road stations for the Mount Washington
summit ASOS at 1,910 m gives **−0.0058 (0.0068), p = 0.39** on the identical five
seasons: same sign, a quarter of the size, no significance. The sample is not the
explanation — the primary index on all seven seasons gives −0.0232 (0.0070),
p = 0.001, and Mount Washington on all seven gives −0.0057 (0.0056), p = 0.31. It
is the thermometers.

Which index deserves more weight is genuinely unsettled, and this write-up does
not pick a winner. Mount Washington is a true summit at 1,910 m, in the altitude
band the Austrian design specified, where the road stations sit 500 m too low.
Against that, it is in New Hampshire about 100 km from the nearest Vermont
resort, and 70.6 % of its hours fall below the threshold against the road
network's 40.9 %, which accumulates roughly 1,500 cold hours a season against
about 800. A site that is below threshold most of the time has little variation
left in `below` and a saturated `cum_cold_h`, so it may be the weaker instrument
rather than the purer one. Both readings are available and neither is
established. **The honest summary is that the headline coefficient is
index-dependent, and that is the strongest argument against taking it at face
value.**

**2. The eight-zone gradient is consistent with the hypothesis and with a
confound, and separates neither.** The eight share errors sum to zero by
construction, so the eight coefficients do too (they sum to +0.0005). Ranked by
latitude:

| zone | lat | `below:cum100` | s.e. | p |
| --- | --- | --- | --- | --- |
| Maine | 44.8 | −0.0208 | 0.0160 | 0.19 |
| **Vermont** | 44.1 | **−0.0211** | 0.0073 | **0.004** |
| New Hampshire | 43.3 | −0.0118 | 0.0074 | 0.11 |
| NEMA / Boston | 42.4 | −0.0064 | 0.0097 | 0.51 |
| WC Mass | 42.4 | +0.0138 | 0.0068 | 0.04 |
| SE Mass | 41.8 | +0.0199 | 0.0069 | 0.004 |
| Rhode Island | 41.7 | +0.0019 | 0.0037 | 0.61 |
| Connecticut | 41.5 | +0.0252 | 0.0134 | 0.06 |

Spearman(latitude, coefficient) = **−0.886**, p = 0.003. Every northern zone is
negative and every southern zone except Rhode Island is positive.

This cuts both ways and the pipeline prints it saying so. Vermont, Maine and New
Hampshire are the three snowmaking states in New England, and they are also the
three northernmost zones. Under the compositional constraint a real snowmaking
effect in those three *must* push the southern five the other way, so a genuine
finding would produce exactly this gradient. So would a regional forecast model
whose temperature response is simply too strong in the north. The table is
consistent with both and discriminates between neither. What it does establish is
that Vermont is the most negative of eight rather than different in kind from its
neighbours, which is what a state-level physical mechanism shared across northern
New England would look like, and also what a latitude artifact would look like.

Normalising by each zone's own load rather than by system share tilts slightly
toward the first reading: per gigawatt of zonal night load the effect is 0.43 %
in Vermont, 0.21 % in Maine and 0.12 % in New Hampshire, which is the order of
their snowmaking intensity relative to their own demand. That ordering is a
descriptive observation on three points and is not offered as a test.

**3. The one test that could separate night from day is inconclusive.** Holding
the right-hand side fixed and moving only the outcome window from the night to
the following afternoon (10:00–16:59), when the guns are largely off, gives
**−0.0037 (0.0169)** against the night's −0.0211 (0.0073) on the same 297 nights.
The point estimate is a sixth of the night's, which is what night-specificity
would look like, but the afternoon share error is 2.3 times noisier and its
interval comfortably contains the night estimate. **This placebo does not
discriminate and is not offered as if it did.** It neither establishes
night-specificity nor rules it out.

**4. The same-publisher arm has since run and does not support it.** On the one
season ISO-NE's own zonal report covers, Vermont's coefficient nearly halves and
loses significance, and the Rhode Island placebo turns significant and negative.
Sixty nights in a single season, so this is weak evidence either way — but it is
weak evidence pointing away, and it is the second post-hoc check to do so. See
section 7, item 1.

### 6.5 Power, and the effect sitting on its own threshold

The quantity the mechanism predicts is a *seasonal swing*: `below:cum100` times
the range of accumulated cold a season delivers. Vermont's `cum_cold_h` runs 0 to
972, so the range is 9.72 and the fitted standard error of 0.0073 pp gives a
smallest detectable swing of 2.80 × 0.0073 × 9.72 = 0.199 pp, or **23.8 MW** at
80% power and 5% two-sided.

Vermont's snowmaking energy is 40–90 GWh a season (§8.8 of the root README),
which spread over a campaign implies a coincident draw between 30 and 110 MW. So
this test can see a forecaster missing **22% to 79%** of the Vermont fleet,
centring near **34%** at a 70 MW draw.

On the same arithmetic the rest of the project needs Austria 47%, Italy-North
27%, Switzerland 201%. **Vermont is second of the four on paper, and the gap to
Italy-North is not real:** Italy's denominator is the one desk derivation in the
set, with no published Italian snowmaking total behind it, so 27% and 34% sit
inside each other's uncertainty. Vermont's own range, 22% to 79%, is wide for the
same reason in smaller form.

What Vermont has that the others do not is not power. It is the only market with
a same-forecaster, same-weather, zero-snowmaking placebo inside the same data
feed, and the only one outside Austria whose Christmas gate could have worked,
because ISO-NE's regional share model is weak enough to leave something in the
residual for it to find.

**And the effect it found clears that threshold by almost nothing.** The estimated
seasonal swing is −0.0211 × 9.72 × 120 = **−24.6 MW**, against a smallest
detectable swing of 23.8 MW. The coefficient sits on its own noise floor. A
pre-registered prediction met at p = 0.004 with a clean placebo is still what it
is, but an effect this close to the floor is precisely the kind that moves when
an input changes, which is what 6.4 point 1 reports happening.

The verdict this section supports is **predicted sign, significant, at the edge
of what this market could resolve, and not surviving three separate checks**: the
weather index (6.4 point 1), the same-publisher actuals (section 7, item 1), and
the price placebo on the same two zones (`src/price/README.md` §10.3). Each is
individually weak — a different thermometer, sixty nights, a different outcome —
and none of them refutes the coefficient. But they were run to find support and
none of them found any, and an effect sitting on its own noise floor is the kind
that should not survive that.

**Reported as suggestive, and weakening.** It is not confirmation, it does not
overturn the Austrian null, and on the evidence assembled after the fact the more
likely reading is a New England–wide response to accumulated cold that Vermont
happens to sit at the north end of.

## 7. Honest limitations

1. **The same-publisher arm has now run, and it does not support the result.**
   ISO-NE's own five-minute zonal load report lets the forecast and the outcome
   share a publisher, so no cross-source definitional gap can be doing the work.
   Its archive covers one season, Nov–Dec 2025, which is 60 of the 297 nights.
   On those 60 nights:

   | | ISO-NE's own actuals | EIA-930, same nights |
   | --- | --- | --- |
   | **Vermont** `below:cum100` | −0.0281 (0.0188), p = 0.14 | −0.0492 (0.0200), **p = 0.014** |
   | **Rhode Island** `below:cum100` | −0.0215 (0.0101), **p = 0.033** | −0.0069 (0.0097), p = 0.47 |
   | mean share error | +0.0042 pp | +0.1199 pp |

   Two things go the wrong way at once. Vermont's coefficient nearly halves and
   loses significance when the actuals come from the same publisher as the
   forecast. And **the placebo fires**: Rhode Island, which makes no snow, turns
   significant and negative on that same data. The definitional level gap between
   the two sources is 0.116 pp of share, about 14 MW, which is over half the
   standard deviation of the night share error the whole test is measured in.

   **How much weight this carries.** Not much on its own: 60 nights in a single
   season, so the season fixed effects carry no variation and every estimate here
   is noisy. Neither Vermont pair nor Rhode Island pair is separated by much more
   than one standard error, and a 60-night panel would struggle to replicate a
   true effect of this size either. What it does do is fail to rule out the
   confound it was built to rule out, in the direction that matters. Read it with
   §10.3 of `src/price/README.md`, where the same two zones on a price outcome
   gave Rhode Island a coefficient indistinguishable from Vermont's: two
   independent post-hoc checks now point the same way.
2. **Two of seven seasons are lost**, one to a hole in the RWIS archive and one
   to structured missingness. Five seasons of 297 nights is a thin panel for a
   design with season fixed effects.
3. **The weather stations are road-level, 462–721 m**, not the 900–2,600 m band
   the Austrian design specified, because Vermont has no high-elevation hourly
   temperature-and-humidity station. The Mount Washington arm is 1,910 m but sits
   in New Hampshire, 100 km from the nearest Vermont resort.
4. **Nov–Dec only**, matching Austria. Vermont snowmaking runs hard into January
   and February and that extension is untested here.
5. **The outcome is compositional.** Vermont is 4.9 % of the system, so its share
   error is measured against seven other zones that must absorb the mirror image.
   The latitude result in 6.3 is a consequence of taking that seriously rather
   than a separate finding.
6. **The price test on the same two zones has since run, and it belongs next to
   section 6.4 point 2.** `src/price/README.md` §10.3 puts this exact right-hand
   side against the Vermont day-ahead LMP spread and gets −1.47 (0.54),
   p = 0.007 — and Rhode Island returns −1.33 (0.52). There the placebo
   discriminates outright, because price carries no compositional constraint:
   both zones clear near the same system price, so a New England–wide driver
   shows up identically in both. The load placebo cannot do that, because its
   eight shares must sum to zero. That contrast is the clearest available
   statement of what this replication's placebo can and cannot rule out.
