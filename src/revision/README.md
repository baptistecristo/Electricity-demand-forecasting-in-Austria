# Snowfall-forecast revisions as the treatment

> **STATUS: sections 1 to 14 are the pre-registration. Section 15 is the result.**
>
> Sections 6 to 11 fix the unit of observation, the treatment, the outcome, the
> specification, the predicted sign, the kill criteria and the power gate. They
> were committed before a single coefficient was estimated, the way
> `src/price/README.md` sections 1 to 9 were, and for the same reason: the
> ordering in `git log --oneline -- src/revision/` is the only thing that makes
> section 15 worth reading.
>
> Nothing in sections 1 to 14 is a coefficient, a standard error, or a p-value;
> every number there is a design choice or a descriptive count of the forecast
> archive. Two amendments were needed after the archive was complete and before
> anything was estimated, anchor A in section 7 and the Windsor zone split in
> section 6. Both are printed where they apply rather than substituted for the
> text they correct.
>
> **The result is outcome 4 of the five registered in section 10: the
> falsification test passes, and the coefficient is too imprecise to be read.**
> Section 15.2 gives the arithmetic, 15.4 the one thing worth carrying forward,
> and 15.5 the answers to an independent review of the specification written
> before the coefficient existed.

## 1. Why this exists

Every test in this repository so far uses `cum_cold_h`, hours below the wet-bulb
threshold since 1 October. It is a slow seasonal variable, badly collinear with
day-of-season, which is why `doy` and `doy²` absorb so much of it and why the
required α in §8.8b came out between 27% and 201%. **No test in the project could
see a forecaster missing less than about a quarter of the snowmaking load.**

A *forecast revision* is the opposite kind of variable: high-frequency,
plausibly exogenous news, arriving six to ten times a day instead of nine times a
season. And a revision to expected **natural snowfall**, holding the temperature
revision fixed, should not move heating demand at all. That is the confound
that has dogged every test here since §4.

The wedge the design aims at: ISO-NE's day-ahead market closes mid-morning. A
forecast revision arriving after that is information a resort can act on and the
day-ahead price cannot contain. Section 10 turns that into a falsification test
which, unusually for this project, can fail in a way that is informative.

## 2. Why Vermont and not the Alps

Three independent reasons, in the order they were established.

1. **Hydro.** Snow is a component of the hydrological balance that sets Alpine
   power prices. A revision toward more snow means less snowmaking *and* more
   expected reservoir inflow, and both push price down. The two channels share a
   sign, so a negative Alpine coefficient identifies nothing. Vermont has very
   little seasonal reservoir hydro.
2. **Archive depth.** Open-Meteo's snowfall previous-runs archive begins
   2024-01-19. That is two Alpine seasons. The Vermont products below run from
   2016 continuously, matching the free ISO-NE day-ahead LMP archive, for ten.
3. **The placebo already works there.** Rhode Island has now twice discriminated
   on ISO-NE data, once on the day-ahead LMP spread (`src/price/README.md`
   §10.3) and once on the same-publisher load arm (`src/vermont/README.md` §7).

## 3. The product, and why it is not the obvious one

`AFMBTV`, the NWS Burlington **Area Forecast Matrices**, zone-level.

The obvious choice is `PFMBTV`, the Point Forecast Matrices, and it is wrong.
All nine of its points are valley towns: Burlington 93 m, Rutland 244 m,
Morrisville 280 m, the highest anywhere being Saranac Lake at 515 m *in New
York*. That is lower than the RWIS stations `src/vermont/README.md` already calls
too low to make snow at, and a valley forecast of `00-00` is perfectly consistent
with six inches at 1,000 m.

`AFMBTV` carries 26 zone blocks, each with its own `Snow 12hr` row, and the zones
split east/west along the Green Mountain spine:

| zone | resorts |
| --- | --- |
| Eastern Rutland | Killington, Pico |
| Eastern Addison | Sugarbush, Mad River Glen |
| Eastern Franklin | Jay Peak |
| Lamoille | Stowe, Smugglers' Notch |
| Eastern Chittenden | Bolton |
| Washington | Sugarbush, Northfield |

`RECBTV` sounds like the mountain product and is not: it forecasts wave heights
on Lake Champlain.

**Zone-level is still not elevation-resolved.** Eastern Rutland spans the town
and the summit. That is measurement error in the treatment, and measurement error
attenuates toward zero, so it biases against finding an effect. That is the safe
direction to be wrong in, but it is a real limit and it belongs in any write-up.

## 4. What is in the archive

Confirmed by listing `AFMBTV` issuances on 10 December of each year:

| season | issuances that day |
| --- | --- |
| 2016 | 10 |
| 2018 | 8 |
| 2020 | 10 |
| 2022 | 7 |
| 2024 | 9 |
| 2025 | 6 |

Continuous 2016–2025. The binding constraint is the price series, not the
weather: free ISO-NE day-ahead LMPs start 2015-12-03, established by bisection
and recorded in `provenance_isone.md`, and re-confirmed for this arm by pulling
2016-11-01, 2017-11-01 and 2018-11-01 directly, all three return full files with
24 Vermont hourly rows. **Ten seasons are available on both sides of the join.**

`src/price/fetch_lmp.py` took seven seasons because that is what the price panel
needed; it now accepts `--seasons 2016-2018` so the cache can be extended
backwards without touching what the price test reads.

### 4.1 Seven things found by inspection that would have failed silently

1. **The row is `Snow 12hr`, not `SNOW 12HR`.** Older products use upper case and
   modern ones mixed case. An exact-case match returns nothing across ten years
   and never raises.
2. **Blank is not zero.** A blank cell means the period is beyond the
   quantitative forecast range. Filling blanks with zero manufactures revisions
   out of the forecast horizon rolling forward, which looks exactly like signal.
3. **The 12-hour values are right-aligned on the column of the UTC hour the
   period ends at.** This is not documented anywhere I could find. It is inferred
   from the values landing on the 00Z and 12Z columns, and `parse_afm.py --audit`
   prints the alignment on a real product so the inference can be checked. On the
   audited product every token is off by exactly zero.
4. **`retrieve.py` answers `ERROR: Could not Find: AFMBTV`.** Use the JSON API:
   `/api/1/nws/afos/list.json?cccc=KBTV&date=…` then `/api/1/nwstext/{product_id}`.
5. **The 12-hour temperature row changes its name with the time of day.** It is
   `MIN/MAX` on an evening issuance and `MAX/MIN` on a morning one, because the
   label names the periods in the order they arrive. A parser keyed on either
   literal silently drops half the products, and, worse, a parser that keys on
   both but assumes a fixed order silently swaps minima for maxima on half of
   them. §9 therefore builds its temperature control from the **3-hourly `Temp`
   and `RH` rows**, which carry no such ordering, rather than from this row.
6. **The gate is a local-time rule and the sample straddles the fall-back.**
   29 October to the first Sunday in November is EDT, the rest is EST, so a gate
   hardcoded at a fixed UTC hour, as an earlier draft of this file had it, at
   "15:30 UTC in winter", misclassifies the first week of every season. The gate
   is applied in `America/New_York` and converted per date.
7. **Season 2016 prints the zone names in upper case.** `EASTERN RUTLAND` in
   2016, `Eastern Rutland` from 2017 on. Keyed verbatim these are two zones, and
   any downstream match on the modern spelling deletes the whole first season
   without raising: the archive appeared to hold 52 zones when it holds 27, and
   the four-zone core panel came out 54,618 rows when it is 60,738. Nothing about
   the aggregate counts looked wrong, this is the failure mode this list exists
   for, and it was invisible in the 2,476-product snapshot because that snapshot
   started in 2016 and every product in it was internally consistent. Zone labels
   are now normalised to title case at parse time.

## 5. What the parse yields

Final, measured on the complete archive: **5,063 products, all ten seasons,
640 of 640 dates, no gaps and no fetch failures.** One product
(`202412231433-KBTV-FOUS51-AFMBTV`) is a 31-character truncated transmission
carrying no zone block; it is dropped and named in the parse output, which is
why the run reports 5,062 issuances against 5,063 files.

**385,602 rows over 27 zones**, issued 2016-10-29 01:39Z to 2025-12-31 21:02Z.
Every zone block's reconstructed time grid was checked against that product's own
UTC header row: **0 disagreements in 5,062 issuances.** Lead time runs 5 to 44
hours, median 24. Wet bulb resolves on 99.5% of rows; the remainder are periods
with fewer than three of the four 3-hourly steps, which are set missing rather
than averaged over a short window.

Seven resort zones are continuous across all ten seasons, 106,293 rows, no
missing `Snow 12hr` cells within them:

| zone | rows | non-zero | ≥ 2 in |
| --- | --- | --- | --- |
| Eastern Franklin | 15,186 | 4,740 | 964 |
| Eastern Chittenden | 15,186 | 4,259 | 786 |
| Eastern Rutland | 15,186 | 3,127 | 677 |
| Washington | 15,186 | 3,828 | 756 |
| Lamoille | 15,183 | 4,771 | 974 |
| Eastern Addison | 15,183 | 3,674 | 684 |
| Orange | 15,183 | 2,625 | 509 |

Across the four core zones of §6: **60,738 rows, 26.9% of forecast periods carry
non-zero snow and 5.4% carry two inches or more**, maximum 10.0 inches per
12-hour period.

The provisional counts this section carried before collection finished, 157,359
rows, 50 zones, 29.3% non-zero, were measured on the first 2,113 products and
are superseded. Two of the three differences are just sample size; the zone count
fell from 50 to 27 because of the casing defect in §4.1 item 7, not because zones
disappeared.

Each issuance gives roughly two to three forward 12-hour snow forecasts per zone,
so revisions are measurable at **zero-to-two-day lead**.

## 6. Unit of observation and the treatment

**One observation per night.** Nights are labelled by the calendar date `D` the
night begins on, 1 November ≤ `D` ≤ 30 December, in each of the ten seasons.

**The night's snow forecast.** The `Snow 12hr` value for the 12-hour period
ending at **12Z on `D+1`**. That period is 19:00–07:00 EST, or 20:00–08:00 EDT.
The project's night block is 20:00–06:59 local. The two windows agree on eleven
of twelve hours in EST, which is a piece of luck rather than a design choice: the
AFM's own overnight period is nearly the snowmaking night this project has
used since `src/apg_pipeline.py`.

**Zones.** The primary treatment is the unweighted mean over the four zones that
carry the largest snowmaking systems: **Eastern Rutland, Eastern Addison,
Eastern Franklin, Lamoille**. Unweighted because this project has a 70 MW figure
for Vermont as a whole (root README §2) and no defensible per-resort split;
inventing weights would be a free parameter. A night is kept only if at least
three of the four zones have a non-missing value at every anchor in §7.
Sensitivity: all eight zones of `RESORT_ZONES`.

> **Amendment 2, 2026-08-10, made before any coefficient was estimated.**
> The sensitivity is **seven** zones, not eight. Parsing the full archive showed
> that NWS split the Windsor county zone into **Eastern Windsor** and **Western
> Windsor** at the start of season 2022: `Windsor` exists 2016–2021 and
> `Western Windsor`, the one holding Okemo, exists 2022–2025, and they are
> different geographies. Splicing them gives one zone whose definition changes
> mid-sample, which is worse in a pre-registered design than losing the zone, so
> Windsor is excluded from `RESORT_ZONES` altogether. The registered sensitivity
> is now *the seven resort zones present in all ten seasons*. **The primary
> treatment is untouched**, none of the four core zones is affected.

The outcome is a single statewide zonal price, so zone-level treatment against
it would repeat one outcome across four rows and manufacture precision. The
aggregation to one number per night is deliberate and is not a convenience.

## 7. The gate, and the two-auction problem this design has to solve

Three anchors, all defined on the wall clock in `America/New_York`:

| anchor | definition | what it represents | typical package |
| --- | --- | --- | --- |
| **A** | last issuance at or before `g(D) − 12h` | last night's view | ~21:00 ET on `D−1` |
| **B** | last issuance at or before `g(D)` | **the view the auction had** | ~09:00 ET on `D` |
| **C** | last issuance strictly before 19:00 ET on `D` | the view when the guns start | ~18:00 ET on `D` |

    rev_pre  = S(B) − S(A)     news the auction HAS
    rev_post = S(C) − S(B)     news the auction CANNOT have

`S` is the zone-mean `Snow 12hr` forecast for the 12-hour period ending 12Z on
`D+1`; `g(D)` is the day-ahead bid deadline on day `D`, which prices operating
day `D+1`.

> **Anchor A amended from `g(D) − 24h` to `g(D) − 12h`, before any coefficient
> was estimated, because the original was not merely inconvenient but empty.**
> The registered version asked for the night's snow forecast as it stood 24
> hours before the gate. The overnight period ends at 12Z on `D+1`, so that
> anchor needs a forecast at a lead of about 44.5 hours, and **`Snow 12hr`
> does not reach that far**. Measured on 11,708 core-zone overnight rows from
> the first 2,476 products: the row carries at most three forward 12-hour
> periods, the longest observed lead is 42.8 hours, and the median longest lead
> available for a given night and zone is 40.0 hours. A 44.5-hour anchor is
> available on **0.0%** of night-zones; a 32.5-hour one, which is what
> `g(D) − 12h` implies, is available on **98.1%**.
>
> This was found by parsing the archive rather than by reasoning about it, and
> the amendment is printed here rather than substituted for what it replaced.
> The replacement is also the better instrument, which is luck and is worth
> saying out loud: the three anchors now land on the three routine packages that
> bracket the gate, so `rev_pre` is the overnight-to-morning revision and
> `rev_post` the morning-to-evening one, and neither anchor is chosen on the
> weather.

The horizon this buys is short, and §13 already said a short horizon may be the
wrong one. It is now shorter than registered. Nothing else in the design moves.

**The gate time changed during the sample.** ISO-NE and NEPOOL filed in September
2020 (FERC docket ER20-2511) to extend the Day-Ahead Energy Market offer and bid
window so that it closes "thirty minutes later in the morning from 10:00 a.m. to
10:30 a.m." The earlier seasons of this panel sit before that change and the
later ones after it, and the public filings did not give up the effective date.

Rather than assume one, bound it. **Across the 2,359 products cached so far, 38
issuances, 1.61%, land in the disputed half-hour 10:00–10:30 ET.** The routine NWS Burlington packages land
near 09:00, 12:00, 15:00, 18:00 and 21:00 ET, so anchor **B** is almost always
the scheduled ~09:00 package and anchor **C** almost always the scheduled ~18:00
one. Both anchors are therefore *scheduled* issuances rather than storm-triggered
special updates, which also means the anchors are not selected on the treatment.

Registered: **`g(D) = 10:30 ET` primary, `g(D) = 10:00 ET` as a sensitivity**, and
the count of nights whose anchor B moves between the two definitions is reported.
If that count is small the question is closed; if it is not, the sensitivity is
the answer and the primary is not.

**The two-auction problem.** The project's 11-hour night block straddles two
operating days: 20:00–23:59 of `D` clears in the auction that closed on `D−1`,
and 00:00–06:59 of `D+1` clears in the auction that closed on `D`. A single gate
cannot be defined for it. The outcome in §8 is therefore redefined onto the hours
that share one auction, rather than fudging the gate to fit the old window.

## 8. Outcome

**Primary.** The night-minus-midday spread taken entirely inside operating day
`D+1`, in USD/MWh:

    spread(D) = mean DA LMP over hours beginning 00:00 .. 06:00 on D+1
              - mean DA LMP over hours beginning 11:00 .. 15:00 on D+1

Both windows clear in the **same auction**, the one that closed at `g(D)`, and
are priced against the same weather information. That is exactly the property
`src/price/README.md` §3 built its spread for, preserved here under a gate the
old window could not support. The midday reference differences out the fuel cost,
the carbon price and the demand level common to both windows.

**Co-primary: the Vermont-minus-Rhode-Island differential of that spread.**
§10.3 of the price README established that Vermont and Rhode Island clear at
correlation 0.9956 and that a common New England driver reproduces itself in both
zones to within a quarter of a standard error. Whatever is Vermont-specific lives
in the difference, and the difference is far less noisy than either level.
Registering it as co-primary rather than as a robustness check is the lesson from
§10.3 applied in advance instead of after the fact.

**Sensitivities.** (i) The full 11-hour night block against midday of `D`, which
is the price test's own definition, reported so the two arms remain comparable
and labelled as straddling two auctions. (ii) The night level rather than the
spread. Negative prices are kept; the spread is defined on the level, not on its
logarithm, so they need no treatment.

## 9. Specification

    spread ~ rev_pre + rev_post + wbrev_pre + wbrev_post
             + snow_gate + wb_gate
             + holiday + doy_c + I(doy_c**2) + C(season) + C(dow)

One observation per night. HC1 standard errors as the primary, for comparability
with every other coefficient in this repository; Newey–West with 7 lags as a
sensitivity, because storms persist across nights even though revisions are
innovations.

**Primary coefficient: `rev_pre`**, in USD/MWh per inch of snowfall revision.

`holiday`, `doy_c`, `season` and `dow` are constructed exactly as in
`src/apg_pipeline.py`: `holiday = (month == 12) & (day >= 21)`,
`doy_c = (doy − mean(doy)) / 10`, `season = year if month ≥ 10 else year − 1`.
Copied rather than re-derived.

**The temperature revision is the whole point of the design and gets built from
the same product, the same zone and the same anchors as the treatment.** `wb` is
the wet-bulb temperature from the AFM's 3-hourly `Temp` and `RH` rows, averaged
over the 3-hourly steps falling inside the same 12-hour period, using the
bisection solver `wet_bulb()` in `src/apg_pipeline.py` verbatim, not the Stull
closed form, which that function's docstring records as erring 0.7–1.0 °C below
freezing. Station pressure is taken from a nominal 600 m via
`pressure_from_altitude()`; because `wbrev` is a *difference* between two
issuances at the same nominal elevation, the elevation assumption very nearly
cancels and cannot drive the control.

`snow_gate` and `wb_gate` are the *levels* at anchor B. Without them a revision
of +2 inches from 0 and from 4 would be treated as the same event.

**This arm does not reuse the load test's right-hand side, and that is a
deliberate break with `src/price/README.md` §4.** The price test insisted on an
identical RHS because its whole purpose was to make a price coefficient
comparable to a load coefficient on the same `below × cum100` design. This arm
exists precisely to *escape* `cum_cold_h` (§1). Its regressors need no EIA-930
weather panel, so it is not confined to the six seasons the Vermont load panel
covers, and running it on ten seasons is worth more than the comparability. The
six-season run on the joined panel is reported as a sensitivity so nothing is
hidden by the choice.

## 10. Predicted sign and kill criteria

**Predicted sign of `rev_pre`: negative.** A revision toward more natural snow
means less snowmaking, less night load, and a lower night-minus-midday spread.
This inherits the sign of the load mechanism in root README §4 for the same
reason `src/price/README.md` §5 does.

**Predicted value of `rev_post`: zero, by construction.** The auction closed
before that news existed. This is the sharpest falsification available anywhere
in this project and it is registered as a rule, not offered as a remark:

1. **INVALID, read nothing else.** If `rev_post` is significant at 5%, the
   day-ahead price is responding to information that did not exist when it
   cleared. That is impossible, so `rev_post` is proxying something else:
   persistent weather, or a storm the auction had already partly priced from
   other sources, and `rev_pre` is proxying it too. In that case **no claim is
   made from `rev_pre` whatever it does.** This criterion is scored first and
   printed first.
2. **SUPPORTS** if `rev_pre` is negative and significant at 5%, `rev_post` is
   not, and the Vermont-minus-Rhode-Island differential carries the coefficient.
3. **REJECTS** if `rev_pre` is zero or positive while §11 says the test is
   powered to have found the implied impact.
4. **UNINFORMATIVE** if the minimum detectable effect exceeds the §11 upper
   bound. The coefficient is reported and no claim is made from it, the way
   Switzerland's load coefficient and all four price coefficients were.
5. **NOT A VERMONT SIGNAL** if Rhode Island reproduces `rev_pre` within half a
   standard error, exactly as in price §10.3. This is scored even when 2 fires.

Outcome 4 is the most likely one and outcome 1 is a live risk. Both are stated
here rather than discovered later.

## 11. Power gate, computed before the coefficient is looked at

Printed before any coefficient, in the order price §7 established.

This arm's power gate needs **no behavioural parameter**. The largest price
impact any snowfall-forecast response could have is the one where the revision
switches off the *entire* Vermont snowmaking fleet. Price §10.3 already measured both halves of that product on
this exact market: an overnight ISO-NE supply slope of **+23.9 USD/MWh per GW**
and a **70 MW** Vermont fleet, giving **1.67 USD/MWh**.

So the gate is:

1. Print the minimum detectable effect: `1.96 × HC1 s.e.(rev_pre)`, scaled to a
   one-standard-deviation snowfall revision and, separately, to the full observed
   revision range.
2. Compare it to **1.67 USD/MWh**, which is an *upper bound*, since no revision turns
   off more than the whole fleet.
3. If the MDE exceeds it, the test could not have seen the effect even under the
   assumption that a forecast revision shuts down every gun in Vermont, and
   outcome 4 fires regardless of what the coefficient turns out to be.
4. Re-estimate the supply slope on the ten-season sample rather than inheriting
   the six-season one, and print both.

Because the bound is an upper bound, a verdict of "underpowered" from this gate
is assumption-free, which no other power gate in this project has managed. The
converse does not hold and the pipeline prints it that way: an MDE *below* the
bound certifies nothing, because a one-standard-deviation revision plainly does
not shut down the whole fleet and this gate has no way to say what fraction it
does shut down. The gate can fire outcome 4. It cannot rule it out.

## 12. What this test cannot do

- **Zone is not elevation.** §3. Attenuation toward zero; the safe direction.
- **The treatment is coarse.** Snow is published as inch ranges (`01-03`), read
  as midpoints, with trace as a nominal 0.05 in. Revisions smaller than the
  rounding are invisible. Attenuation again. Sensitivities: lower bound of the
  range instead of the midpoint, and trace as exactly zero.
- **A snowstorm is not only a snowmaking signal.** A revision toward more snow
  also revises the probability of outages, transmission de-rates, wind, cloud and
  road-driven demand. `wbrev` holds the *temperature* revision fixed and nothing
  else. This is the main threat to interpretation and it is not solved.
- **`rev_post = 0` is only a falsification if the auction is efficient.** An
  auction that failed to update on pre-gate news would also produce a null there.
  The test can catch a broken design; it cannot certify a working one.
- **Price is worth almost nothing overnight.** Price §10 found the overnight
  merit order close to flat in all four markets. Moving from `cum_cold_h` to a
  revision fixes the treatment, not the outcome's sensitivity.
- **The horizon may be the wrong one.** §13.

## 13. The open question, stated before any result exists

The operational research in this project found that no published source states a
rule linking a natural-snow forecast to a nightly snowmaking decision. The Alpine
modelling literature assumes base production runs *regardless* of natural
snowfall, manufacturer planning software forecasts on temperature rather than
snowfall, and the one clean case of an operator stopping because snow was coming
was a season-termination call at a ten-day horizon.

**If that is right, snowfall forecasts act on the campaign margin at four-day-to-
seasonal horizons, and this instrument, which reaches zero to two days, is
aimed at the wrong one.** That is a reason to run it and look, not a reason to
skip it, but it should be written down before the coefficient is, and it is.

Note what that implies for scoring: a null on `rev_pre` is consistent with "no
nightly snowfall response exists" and with "the price cannot see it", and §11
will most likely say the second cannot be ruled out. A null here is weak
evidence. Kill criterion 1 in §10 is the part of this design that can fail
loudly, and it is the one to watch.

## 14. Run it

```
python src/revision/fetch_afm.py               # forward, and in another shell:
python src/revision/fetch_afm.py --reverse     # newest first; they meet
python src/revision/parse_afm.py               # writes afm_snow.csv
python src/revision/parse_afm.py --audit       # check the column alignment

python src/price/fetch_lmp.py --seasons 2016-2018 --no-october   # ten seasons
python src/revision/fetch_isne_load.py         # ISO-NE demand, for the slope
python src/revision/revision_pipeline.py       # gates first, then coefficients
python src/revision/revision_pipeline.py --review   # the section 15.5 checks
```

An earlier version of this section said the archive takes about 45 minutes cold.
It does not. The measured rate is around 1.5 dates a minute, so one pass over
640 dates is closer to seven hours, and IEM's latency rather than this script's
`PACE` is what sets it. Running the forward and reverse passes together roughly
halves that. Both are resumable: a date is skipped once its marker exists, so
an interrupted run costs nothing but the date it was on.

The cache path at the top of `fetch_afm.py` is the only thing that needs changing
on another machine. `parse_afm.py` and `revision_pipeline.py` import that
constant rather than naming a path of their own.

## 15. Result

Everything registered was committed at `52e9a6e`, before the pipeline was run
once. The check is `git diff 52e9a6e..HEAD -- src/revision/README.md`, and it
must be stated precisely enough to survive being run: that diff touches text
above this line in exactly two places, the STATUS block at the top and the
`--review` line in §14's run instructions. **Sections 6 to 11 (the unit of
observation, the treatment, the outcome, the specification, the predicted sign,
the kill criteria and the power gate) carry no post-estimation edit at all.**
Where §15.5 concedes that a registered criterion was worded badly, it says so
here rather than correcting it up there, for the same reason.

**Panel.** 600 nights, exactly 60 in each of the ten seasons, 2016–2025. A
genuinely later anchor C exists on 100% of nights, so the falsification test is
available everywhere and is not being read off a subsample. `rev_pre` has
sd 0.263 in and is non-zero on 37.7% of nights; `rev_post` sd 0.244 in, non-zero
on 35.8%. The outcome has sd 14.60 USD/MWh.

### 15.1 Kill criterion 1, passes

    rev_post   -0.8585  (2.5755)   t = -0.33   p = 0.74

The day-ahead price does not respond to news that postdates it. The design is
not invalidated, so `rev_pre` may be read. §10 registered this as a weak pass and
it is one: `rev_post` carries less variance than `rev_pre`, its own MDE is
1.231 USD/MWh, and a null against that is survival, not certification.

### 15.2 The registered gate fires outcome 4

    rev_pre  MDE   4.303 USD/MWh per inch   (1.96 x HC1 s.e. 2.196)

§11 registered two scalings and did not say which governs when they disagree.
They disagree here: scaled to one sd the MDE is 1.134 against a bound of 1.673,
scaled to the full observed range it is 16.622. **The ambiguity is resolved here,
after estimation, in the direction adverse to the design**. That is the only
direction in which resolving a registered ambiguity post-hoc is defensible, and
it is also the logically correct one. The bound caps the effect *of a revision*,
not the effect per inch: under the linear model in §9, `β·r ≤ 1.673` must hold at
every observed `r`, so the largest admissible slope is `1.673 / max r`. The
one-sd comparison embeds an impossible premise: if a 0.26-inch revision shut off
the whole fleet, a full-range revision would shut off fifteen of them.

| bound | scaling | β_max | MDE / β_max |
| --- | --- | --- | --- |
| inherited 1.673 | span 3.862 in | 0.432 | **9.9×** |
| inherited 1.673 | max\|rev\| 2.380 in | 0.703 | **6.1×** |
| re-estimated 1.536 | span 3.862 in | 0.397 | **10.8×** |
| re-estimated 1.536 | max\|rev\| 2.380 in | 0.645 | **6.7×** |

Underpowered by six to eleven times, under every combination of the two slopes
§11 item 4 registered and both scalings. **Outcome 4. The coefficient is reported
and no claim is made from it**, the same treatment Switzerland's load coefficient
and all four price coefficients received.

### 15.3 The coefficients, reported and not claimed

    Vermont      rev_pre   +0.2023  (2.1956)   t = +0.09   p = 0.93
    RhodeIsland  rev_pre   +0.0834  (2.2365)   t = +0.04   p = 0.97
    VT - RI      rev_pre   +0.1189  (0.2038)   t = +0.58   p = 0.56

The point estimate carries the *wrong* sign, §10 predicted negative, and it is
nowhere near significance. Outcome 3 (REJECTS) explicitly requires that §11 find
the test powered, and §11 did not, so the wrong sign is given no weight in either
direction. Every registered sensitivity is null: 10:00 gate (4 of 600 nights
change, 0.7%), seven zones, range lower bound with trace at zero, the straddling
11-hour block, HAC(7), night level rather than spread, and the six-season
restriction to the load panel's own nights.

**Outcome 5 is mechanically met and is vacuous.** Rhode Island reproduces
`rev_pre` to within 0.12 USD/MWh against a half-standard-error threshold of about
1.1. The rule exists to catch a region-wide signal masquerading as a Vermont one;
here there is no signal to attribute to anywhere, and it should not be read as a
second finding.

### 15.4 One thing worth carrying forward, labelled post-hoc

This was not registered and is not scored. Differencing Vermont against Rhode
Island removes the ISO-NE-wide component of the night spread and cuts the
standard error by a factor of about eleven, from 2.196 to 0.204. That puts the
differential's MDE at 0.399 USD/MWh per inch, **0.57× to 0.92× the whole-fleet
bound, and 1.01× under the re-estimated slope.** Its 95% CI, [−0.28, +0.52],
excludes the whole-fleet effect in all four cells of the table above.

Three reasons that is not a rejection, all of which have to be said for the
paragraph to be honest. It is knife-edge: a verdict that holds under one
registered slope and fails under the other by one percent is a boundary, not a
result. The CI exclusion depends partly on the point estimate landing at +0.12;
with the same standard error and an estimate of −0.31 the whole-fleet effect
would sit inside it. And translated into the fraction α of the fleet that
responds, the differential can only detect **α ≳ 0.57 to 0.92**, excluding "a
quarter-inch forecast revision shuts down sixty to ninety percent of Vermont's
snowmaking" excludes nothing anybody believed.

The value is in the design, not the inference. **A successor arm that registers
the Vermont-minus-Rhode-Island differential as its primary specification, with
the §11 power gate computed on that specification, starts out powered against the
assumption-free bound**, which no arm in this project has managed. That is the
one genuinely new thing this run produced, and it bears directly on §13: the
reason to run this again is not a better instrument but a better-chosen outcome.

### 15.5 Answers to the independent review

A second session reviewed §1–14 at commit `1d8af41`, before any coefficient
existed. Its write-up is committed unedited beside this file as
[`review.md`](review.md), answering it point by point while leaving the reader
unable to read it would be worth little. It raised four points. All
four are answered here on the post-casing-fix parse, including the two it
flagged as needing restatement.

**1. Anchor collapse, confirmed clean.** The review checked that "the last
issuance at or before" never silently returns the previous anchor's product, and
found 0 of 600 nights where A and B or B and C resolve to the same product. On
the fixed parse both revisions are non-missing on **100% of nights**. `rev_pre`
is exactly zero on 62.3% and `rev_post` on 64.2%, which is the forecast not
changing rather than the anchors collapsing.

**2. `rev_pre` and `rev_post` share anchor B, real mechanism, small magnitude,
and it could not have caused the result.** The review is right that an error `u`
in `S(B)` enters `rev_pre` with a plus and `rev_post` with a minus, inducing
covariance `−var(u)` whether or not the forecast is efficient. It asked for the
discriminating regression first, so here it is:

    corr(rev_pre, rev_post)  = -0.106
    rev_post on rev_pre      = -0.0985  (0.0969)   t = -1.02   p = 0.31
    same, snow_in_lo         = -0.1214  (0.0868)   p = 0.16

The **sign is the one the review predicted**, shared rounding error, not
revision momentum, and it survives the range-lower-bound treatment, so it is a
property of the construction rather than of the midpoint rule. But the magnitude
is small. The slope identifies `var(u)/var(rev_pre)`, giving an implied
**sd(u) ≈ 0.083 in, 95% CI [0.000, 0.142]**, a third of sd(`rev_pre`) and an
order of magnitude below the 1.0-inch grain of an `01-03` range. The review's
worry that the error is "comparable to the signal" is not borne out at the level
of the four-zone nightly mean, and the arithmetic of why is in point 5 below.

The decisive point is directional. This contamination biases **toward** firing
kill criterion 1, and **criterion 1 did not fire** (`rev_post` p = 0.74). A
channel that could only have produced a false INVALID cannot explain a pass. The
criterion holds as written, and the review's own stopping rule, "if it is near
zero the concern is idle", is met. The second falsification specification it
offered as a fallback is therefore not run, on its own condition.

**3. "SUPPORTS" had no object, conceded.** §10 outcome 2 should have read
"supports the claim that the day-ahead **price** impounds pre-gate snow news,"
which is a statement about the market and not about the load-forecaster blind
spot that §1 motivates the arm from. The arm escapes the `cum_cold_h`
collinearity but it does not produce an α. The clause is not being retrofitted
into §10, amending a registered criterion after estimation is exactly what this
file exists to prevent, so the correction is recorded here instead. It costs
nothing in this run: outcome 2 did not fire.

**4a. Multiplicity was unregistered, conceded, and it did not bite.** Roughly
ten looks at 5% carry about a 40% chance of one false positive. Registering it
afterwards is worth nothing, so the honest statement is the count: **0 of the
sensitivities came back significant**, which is what a genuine null looks like
and is the opposite of the failure mode multiplicity creates. For any successor
arm: sensitivities are descriptive and cannot upgrade a null primary.

**4b. The zone mean does not float.** §6 keeps a night on three of four zones,
and the review was right to ask how often that fires. It fires **never**: all
**600 of 600** nights carry all four core zones. `MIN_ZONES = 3` is dead code on
this archive, so the treatment is a four-zone mean on every night and none of the
night-to-night variation is zone-set churn.

**5. The review's own caveats, discharged.** Its descriptives predated the
casing fix and so excluded season 2016; it asked for them to be restated, and
§5 and this section are the restatement. Its sd of **0.534 in** for a successive
revision is not comparable to sd(`rev_pre`) = **0.263 in**, and the gap is not a
correction: theirs is a single zone-period revision, `rev_pre` is a mean over
four zones for one 12Z period, and averaging four imperfectly correlated zones is
most of the factor of two. Its own judgement that the `222` figure should not be
quoted is correct and it is not quoted anywhere here.

### 15.6 What this run settles

`rev_post` is flat, so the falsification the design was built around holds and the
arm is structurally sound. The nightly snowfall-revision channel is not visible
in the ISO-NE day-ahead night spread at a precision that could see it, and §13
predicted exactly that, for the reason it gave, before the numbers existed. What
`src/revision/` adds to the project is not a coefficient. It is a treatment
variable with real high-frequency variation, a falsification test that passes, and
a specification whose standard error is small enough to be worth a second look.
