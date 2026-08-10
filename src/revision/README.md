# Snowfall-forecast revisions as the treatment

> **STATUS: sections 1 to 12 are the pre-registration. There is no result here.**
>
> Sections 6 to 11 fix the unit of observation, the treatment, the outcome, the
> specification, the predicted sign, the kill criteria and the power gate. They
> were committed before a single coefficient was estimated, the way
> `src/price/README.md` sections 1 to 9 were, and for the same reason: the
> ordering in `git log --oneline -- src/revision/` is the only thing that makes
> whatever comes next worth reading.
>
> Everything printed below is either a design choice or a descriptive count of
> the forecast archive. No number below is a coefficient, a standard error, or a
> p-value.

## 1. Why this exists

Every test in this repository so far uses `cum_cold_h`, hours below the wet-bulb
threshold since 1 October. It is a slow seasonal variable, badly collinear with
day-of-season, which is why `doy` and `doy²` absorb so much of it and why the
required α in §8.8b came out between 27% and 201%. **No test in the project could
see a forecaster missing less than about a quarter of the snowmaking load.**

A *forecast revision* is the opposite kind of variable: high-frequency,
plausibly exogenous news, arriving six to ten times a day instead of nine times a
season. And a revision to expected **natural snowfall**, holding the temperature
revision fixed, should not move heating demand at all — which is the confound
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
   on ISO-NE data — once on the day-ahead LMP spread (`src/price/README.md`
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

`RECBTV` sounds like the mountain product and is not — it forecasts wave heights
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
2016-11-01, 2017-11-01 and 2018-11-01 directly — all three return full files with
24 Vermont hourly rows. **Ten seasons are available on both sides of the join.**

`src/price/fetch_lmp.py` took seven seasons because that is what the price panel
needed; it now accepts `--seasons 2016-2018` so the cache can be extended
backwards without touching what the price test reads.

### 4.1 Six things found by inspection that would have failed silently

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
   literal silently drops half the products, and — worse — a parser that keys on
   both but assumes a fixed order silently swaps minima for maxima on half of
   them. §9 therefore builds its temperature control from the **3-hourly `Temp`
   and `RH` rows**, which carry no such ordering, rather than from this row.
6. **The gate is a local-time rule and the sample straddles the fall-back.**
   29 October to the first Sunday in November is EDT, the rest is EST, so a gate
   hardcoded at a fixed UTC hour — as an earlier draft of this file had it, at
   "15:30 UTC in winter" — misclassifies the first week of every season. The gate
   is applied in `America/New_York` and converted per date.

## 5. What the parse yields

> Provisional: measured on the first 2,113 of roughly 5,000 products, seasons
> 2016 to late 2020. Collection is still running and these counts will be
> restated on the full archive before any estimation. They are here to show that
> the treatment has variation, not to characterise the final panel.

157,359 rows over 50 zones. Across the four core resort zones, **29.3% of
forecast periods carry non-zero snow and 6.4% carry two inches or more**, maximum
7.5 inches per 12-hour period.

Each issuance gives roughly two to three forward 12-hour snow forecasts per zone,
so revisions are measurable at **zero-to-two-day lead**.

## 6. Unit of observation and the treatment

**One observation per night.** Nights are labelled by the calendar date `D` the
night begins on, 1 November ≤ `D` ≤ 30 December, in each of the ten seasons.

**The night's snow forecast.** The `Snow 12hr` value for the 12-hour period
ending at **12Z on `D+1`**. That period is 19:00–07:00 EST, or 20:00–08:00 EDT.
The project's night block is 20:00–06:59 local. The two windows agree on eleven
of twelve hours in EST, which is a piece of luck rather than a design choice: the
AFM's own overnight period is very nearly the snowmaking night this project has
used since `src/apg_pipeline.py`.

**Zones.** The primary treatment is the unweighted mean over the four zones that
carry the largest snowmaking systems: **Eastern Rutland, Eastern Addison,
Eastern Franklin, Lamoille**. Unweighted because this project has a 70 MW figure
for Vermont as a whole (root README §2) and no defensible per-resort split;
inventing weights would be a free parameter. A night is kept only if at least
three of the four zones have a non-missing value at every anchor in §7.
Sensitivity: all eight zones of `RESORT_ZONES`.

The outcome is a single statewide zonal price, so zone-level treatment against
it would repeat one outcome across four rows and manufacture precision. The
aggregation to one number per night is deliberate and is not a convenience.

## 7. The gate, and the two-auction problem this design has to solve

Three anchors, all defined on the wall clock in `America/New_York`:

| anchor | definition | what it represents |
| --- | --- | --- |
| **A** | last issuance at or before `g(D) − 24h` | the view one auction earlier |
| **B** | last issuance at or before `g(D)` | **the view the auction had** |
| **C** | last issuance strictly before 19:00 ET on `D` | the view when the guns start |

where `g(D)` is the day-ahead bid deadline on day `D`, which prices operating day
`D+1`.

    rev_pre  = S(B) − S(A)     news the auction HAS
    rev_post = S(C) − S(B)     news the auction CANNOT have

**The gate time changed during the sample.** ISO-NE and NEPOOL filed in September
2020 (FERC docket ER20-2511) to extend the Day-Ahead Energy Market offer and bid
window so that it closes "thirty minutes later in the morning from 10:00 a.m. to
10:30 a.m." The earlier seasons of this panel sit before that change and the
later ones after it, and the public filings did not give up the effective date.

Rather than assume one, bound it. **Across the 2,359 products cached so far, 38
issuances — 1.61% — land in the disputed half-hour 10:00–10:30 ET.** The routine NWS Burlington packages land
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
bisection solver `wet_bulb()` in `src/apg_pipeline.py` verbatim — not the Stull
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

1. **INVALID — read nothing else.** If `rev_post` is significant at 5%, the
   day-ahead price is responding to information that did not exist when it
   cleared. That is impossible, so `rev_post` is proxying something else —
   persistent weather, or a storm the auction had already partly priced from
   other sources — and `rev_pre` is proxying it too. In that case **no claim is
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
2. Compare it to **1.67 USD/MWh**, which is an *upper bound* — no revision turns
   off more than the whole fleet.
3. If the MDE exceeds it, the test could not have seen the effect even under the
   assumption that a forecast revision shuts down every gun in Vermont, and
   outcome 4 fires regardless of what the coefficient turns out to be.
4. Re-estimate the supply slope on the ten-season sample rather than inheriting
   the six-season one, and print both.

Because the bound is an upper bound, a verdict of "underpowered" from this gate
is assumption-free, which no other power gate in this project has managed.

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
- **The horizon may simply be the wrong one.** §13.

## 13. The open question, stated before any result exists

The operational research in this project found that no published source states a
rule linking a natural-snow forecast to a nightly snowmaking decision. The Alpine
modelling literature assumes base production runs *regardless* of natural
snowfall, manufacturer planning software forecasts on temperature rather than
snowfall, and the one clean case of an operator stopping because snow was coming
was a season-termination call at a ten-day horizon.

**If that is right, snowfall forecasts act on the campaign margin at four-day-to-
seasonal horizons, and this instrument — which reaches zero to two days — is
aimed at the wrong one.** That is a reason to run it and look, not a reason to
skip it, but it should be written down before the coefficient is, and it is.

Note what that implies for scoring: a null on `rev_pre` is consistent with "no
nightly snowfall response exists" and with "the price cannot see it", and §11
will most likely say the second cannot be ruled out. A null here is weak
evidence. Kill criterion 1 in §10 is the part of this design that can fail
loudly, and it is the one to watch.

## 14. Run it

```
python src/revision/fetch_afm.py     # ~5,000 products, ~45 min cold, cached
python src/revision/parse_afm.py     # writes afm_snow.csv
python src/revision/parse_afm.py --audit    # check the column alignment

python src/price/fetch_lmp.py --seasons 2016-2018 --no-october   # ten seasons
```

The cache path at the top of `fetch_afm.py` is the only thing that needs changing
on another machine.
