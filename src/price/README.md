# Does the day-ahead spot price move with snowmaking weather?

> **STATUS: sections 1 to 9 are the pre-registration, section 10 is the result.**
>
> Sections 1 to 9 were committed before any price coefficient was estimated, and
> the commit that added them contains no results. Section 5's predicted sign was
> amended once, in its own commit, still before estimation, and the amendment is
> printed inside section 5 rather than substituted for what it replaced. Section
> 10 came later. `git log --oneline -- src/price/` shows all three in order, and
> that ordering is the only thing that makes the answer worth reading.
>
> **The answer is no, and in Vermont a placebo settles it outright.** The power
> gate, which prints before every coefficient by design, puts Austria 1.3× short
> of being able to detect the effect, Italy-North 2.7×, Switzerland 3.8× and
> Vermont 4.0×. Section 5 named that outcome in advance and said what to do about
> it, which is to report the coefficients and make no claim from them.
>
> Vermont is the exception worth reading. Its price interaction *is* negative and
> significant at p = 0.007 — and Rhode Island, which makes no snow, returns the
> same coefficient to within a quarter of a standard error. Section 10.4.

The load test asks whether the grid operator's day-ahead forecast misses
snowmaking. This asks a different question about the same load: whether the
day-ahead auction prices it.

Four markets, the same specification in each: Austria, Italy-North,
Switzerland, and the Vermont zone of ISO New England.

---

## 1. Why this is a spot test, and why futures are not tested

A snowmaking decision has a horizon of about eighteen hours. The operator reads
the evening wet-bulb forecast, decides whether tonight is cold enough to run the
guns, and the electricity is drawn between roughly 20:00 and 07:00. Only one
instrument clears on that horizon: the day-ahead auction, which closes around
noon for every hour of the following day.

A monthly or quarterly baseload futures contract cannot carry the signal. By the
time a quarter of snowmaking is inside a Q1 contract it has been averaged into a
seasonal expectation, and the day-to-day wet-bulb variation this design depends
on has been integrated away. Futures would be the wrong instrument even if the
data were free, and EEX and ICE settlement history is not free.

So the outcome here is a **day-ahead auction clearing price**. It is a spot
price. It is called spot everywhere in this directory, in the code, and in the
paper. Nothing in this test touches a futures contract.

> **Since written:** `src/futures/README.md` takes up the one futures question
> this section does not dispose of. The argument above is about *day-to-day*
> wet-bulb news, which a calendar-month contract does average away. It leaves
> open the seasonal level — whether the winter off-peak months in a snowmaking
> zone carry a premium the market has priced — which is asked at the horizon
> snowmaking is *planned* at rather than dispatched at. That leg was run on the
> ISO-NE New Hampshire zone and stops at the liquidity gate: the contract is
> listed on CME (AU3), ICE (IHD) and Nodal (AAV), and in sixteen years of CFTC
> Commitments of Traders it has never once had twenty traders holding
> twenty-five lots, on any of the three. The sentence above stands; the reason
> futures are untested is now measured rather than assumed.

## 2. What the price test can add that the load test cannot

The two tests fail in different ways, which is the reason to run both.

|                          | forecast captures the load | forecast misses the load |
| ---                      | ---                        | ---                      |
| **load is large enough to move price** | day-ahead price responds, forecast error flat | day-ahead price flat, balancing price spikes |
| **load is too small to move price**    | nothing visible anywhere   | forecast error responds, price flat |

Austria's load test returned a null: the day-ahead forecast error does not
respond to snowmaking weather. That null is consistent with two of these cells,
the top-left and the bottom-left. A price response separates them. If the
day-ahead price moves with snowmaking weather, the load exists and the market
already knows about it, which is the most likely reason the forecaster is not
caught out. If the price does not move either, and the test has the power to
have seen it, then the load is simply too small to matter to either.

The price test therefore cannot rescue the load finding and is not intended to.
It can only tell you which kind of nothing the load null was.

## 3. Outcome variable

**Primary: the night-minus-midday spread**, in currency per MWh.

    spread(D) = mean price over 20:00 D .. 06:59 D+1
              - mean price over 11:00 D .. 15:59 D

Night is defined exactly as in `src/apg_pipeline.py`: hours 20:00-06:59,
labelled by `date(timestamp - 7h)`, requiring at least 8 valid hours.

The spread rather than the level, for two reasons that are both fatal to the
level on its own. Gas set the marginal price in all four markets through most of
the sample, and the 2021-22 and 2022-23 winters multiplied the level several
times over without anything happening on a Tyrolean piste. A same-day midday
reference differences out the fuel cost, the carbon price, the exchange rate and
the demand level that all four night hours share with the four midday hours ten
hours earlier. Second, snowmaking is a night-only load, so the night-day spread
is where its footprint would be even if the level were clean.

Midday is taken from the same calendar day the night starts on, so that the
midday hours and the first four night hours clear in the same auction and are
priced against the same weather information.

**Sensitivity: the night level**, unchanged, with season fixed effects doing
what they can. Reported alongside so the choice of outcome is visible rather
than assumed.

Negative prices are kept. They are real clearing prices and the spread is
defined on the level, not on its logarithm, precisely so they need no treatment.

## 4. Specification

Identical right-hand side to the load test. Not similar: identical.

    spread ~ below * cum100 + dist + below:dist + holiday
             + doy_c + I(doy_c**2) + C(season) + C(dow)

HC1 standard errors. One observation per night. The regressors are not rebuilt
here. The pipeline reads each country's existing night panel, the one its own
load pipeline wrote, and joins the price outcome onto it by night date. Every
regressor is therefore the same column of the same file that produced the load
coefficient, which is what makes the two numbers comparable.

Primary coefficient: **`below:cum100`**, in currency per MWh per 100
accumulated cold hours.

## 5. Predicted sign and kill criteria

> **Amended before any price data was estimated.** The first version of this
> section predicted a *positive* interaction, on the reasoning that the fleet is
> progressively brought on as cold accumulates. That is backwards, and it is
> backwards against this project's own mechanism. Section 4 of the root README
> is explicit: the base gets built and the guns stop, so the snowmaking effect is
> front-loaded and **decays** with accumulated cold. That is why the
> pre-registered load coefficient in root README section 5 is predicted negative
> and why a positive load coefficient fires a kill criterion. The price
> prediction has to inherit the same sign, and now does. The amendment is here,
> in its own commit, before a single price coefficient was estimated, rather than
> discovered afterwards.

**Predicted sign: negative**, matching the load test.

Snowmaking is a load, and a load raises the price at which the market clears. On
a cold night early in the season, with no base built, a resort runs everything it
owns and the night-day spread should carry that. On an equally cold night in late
December, after 900 hours of accumulated cold have already put snow on the
ground, the same weather draws much less power. The threshold effect on price
therefore shrinks as `cum100` rises, which is a negative `below:cum100`.

A heating confound cannot produce that shape. Heating responds to how cold
tonight is, not to how many cold hours the season has already delivered.

Fixed before estimation:

1. **Supports the mechanism** if `below:cum100` is negative, significant at 5%,
   and its implied magnitude is within an order of magnitude of the price impact
   the power gate in section 7 computes from the market's own supply slope.
2. **Rejects the mechanism** if the coefficient is zero or positive while the
   test is powered to have found the implied impact.
3. **Uninformative** if the minimum detectable effect exceeds the implied
   impact. In that case the coefficient is reported and no claim is made from
   it, the way Switzerland's load coefficient was handled.

Outcome 3 is a live possibility and is stated here rather than discovered later.
A few hundred megawatts against a merit order that is flat overnight may be
worth well under one currency unit per MWh, against a night spread whose
standard deviation runs to tens. If the arithmetic in section 7 lands there,
that is the headline, and it is a statement about the instrument rather than
about snowmaking.

## 6. Sanity gate

`holiday` must come back **negative** in all four markets. The Christmas
industrial shutdown cuts demand, and lower demand clears lower down the merit
order. A price panel that does not show this is broken, and no coefficient from
it should be read.

This gate transfers where the load test's did not, and the reason matters. In
the load test the gate was the Christmas coefficient on *forecast error*, and
section 8.8b of the root README shows that gate is an Austrian peculiarity:
Terna and Swissgrid both forecast their Christmas shutdown almost perfectly, so
nothing is left in the error for the gate to find. Price is not a forecast
error. It responds to demand that actually happened, and no amount of forecaster
skill can absorb it. So the same calendar control that fails as a sensitivity
check on Italian forecast error works as one on Italian price.

## 7. Power gate, computed before the coefficient is looked at

Reported first, in the order the Austrian gate in section 8.2 was:

1. Estimate the local supply slope `dP/dQ` for each market by regressing the
   night mean price on the night mean **residual load** (load minus wind minus
   solar), within season, over the same nights. Slope in currency per MWh per
   GW.
2. Multiply by the snowmaking increment already estimated for that country in
   section 2 of the root README, to get the price impact a fully committed fleet
   would produce.
3. Compute the minimum detectable effect as `1.96 x` the HC1 standard error on
   `below:cum100`, scaled to a representative end-of-season `cum_cold_h`.
4. Print both, and the verdict, before printing the coefficient.

## 8. Data

| series | source | zones |
| --- | --- | --- |
| day-ahead spot price, hourly | energy-charts.info `/price` | AT, CH, IT-North |
| day-ahead LMP, hourly | ISO-NE *Day-Ahead Energy Market Hourly LMP Report*, `WW_DALMP_ISO_YYYYMMDD.csv`; session cookie plus matching `Referer`, rate-limited; archive reaches 2015-12-03 | .Z.VERMONT, .Z.RHODEISLAND |
| load and residual load, hourly | energy-charts.info `/public_power` | AT, CH, IT-North |
| system load, hourly | EIA-930 ISNE, already cached by the Vermont pipeline | ISO-NE |
| wet-bulb index, cold hours, all controls | the four existing night panels | all |

Two things to check rather than assume, both recorded here before the data
arrives so that the answer cannot be quietly adjusted afterwards:

- **The Austrian bidding zone did not exist before 1 October 2018.** Earlier AT
  prices are the common DE-AT-LU price, which is set by German wind and German
  gas and is not an Austrian price in any useful sense. The split date is to be
  established empirically from the data, by finding where AT and DE-LU stop
  being identical, and the Austrian price panel starts there. It will be much
  shallower than the Austrian load panel, which reaches 2010.
- **energy-charts has already served this project a fabricated series.** Its
  Swiss day-ahead load forecast for the 2021 and 2022 winters is the realised
  load multiplied by a constant, which section 8.9 of the root README documents.
  The price series gets the same treatment: the crisis winters must be visibly
  extreme, the three zones must be distinct series rather than one series under
  three names, and the timezone convention must be established from the shape of
  the daily profile rather than assumed.

## 9. What this test cannot do

Cold weather raises electricity prices through heating, and snowmaking happens
in cold weather. No design separates them completely. What the specification
leans on is that heating responds to the *contemporaneous* temperature, which
`dist` and `below` absorb, while snowmaking responds to the *accumulated* cold
of the season so far, because a resort that has already built a base makes less
urgent use of the next cold night than one that has not. `below:cum100` is the
term that carries that difference. It is a weaker instrument than an experiment
and the reader should treat it as one.

Four other things this cannot settle:

- Hydro reservoirs in Austria, Switzerland and Italy-North shift water between
  hours in response to the same weather, which moves the night-day spread for
  reasons unrelated to snowmaking.
- Snowmaking that is contracted forward, or supplied by a resort's own hydro,
  never reaches the day-ahead auction at all and is invisible here.
- Switzerland's load test was underpowered by a factor of five. Nothing about
  moving to price fixes that, and the Swiss price result inherits the problem.
- Vermont's zone is about 5% of a 12 GW system, and ISO-NE is usually
  unconstrained overnight, so the Vermont LMP may be identical to the system
  price for most hours. If it is, the Vermont price test has no local content
  and says nothing about Vermont specifically. The share of hours where the
  Vermont and Rhode Island LMPs are equal to the cent is reported for exactly
  this reason.

## 10. Results: the day-ahead spot price cannot answer this question

Outcome 3 of section 5 fired in all four markets. The power gate,
printed before any coefficient as designed, says the test could not have detected
the effect it was looking for. The coefficients are reported below and no claim
is made from them.

| market | seasons | nights | supply slope | fleet | implied impact | min. detectable swing | short by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Austria** | 5 (2018–22) | 300 | +15.6 €/MWh per GW | 900 MW | +14.02 €/MWh | 18.0 €/MWh | **1.3×** |
| **Italy-North** | 7 | 420 | +3.5 | 1,500 MW | +5.29 | 14.4 | 2.7× |
| **Switzerland** | 9 | 540 | +7.7 | 200 MW | +1.55 | 5.9 | 3.8× |
| **Vermont** (ISO-NE, USD) | 6 | 344 | +23.9 $/MWh per GW | 70 MW | +1.67 $/MWh | 6.7 $/MWh | 4.0× |

The reason is physical rather than statistical. The overnight merit order is
close to flat: Austria's own night data puts the supply slope at 15.6 €/MWh per
gigawatt, so a 900 MW Austrian snowmaking fleet moves the price about
**14 €/MWh** at the margin. The night-minus-midday spread it has to be found in
has a standard deviation of **43 €/MWh**, inside a five-season panel two of whose
winters are the energy crisis. Italy-North has a flatter slope still, 3.5 €/MWh
per GW, so even a 1.5 GW fleet is worth only 5.3 €/MWh there.

**Austria is the near miss and is worth flagging as one.** It falls short by 1.3×
on the favourable scale and 2.0× on the strict one, not by the wide margin the
other two do. Austria has five price seasons against thirteen load seasons purely
because its bidding zone did not exist before October 2018, and the panel grows
by one season a year on its own. This is the one arm of the project where simply
waiting is a real strategy: three or four more winters would bring the detectable
swing under the implied impact. Note also that its two crisis winters are 40% of
the current panel and carry most of the variance, so the standard error should
improve faster than the square root of the seasons.

The megawatt-detection arithmetic in §6 of the root README does not carry over.
A load test can find a few hundred megawatts because load is measured in
megawatts. A price test has to find what those megawatts are worth, and overnight
they are worth almost nothing.

The scale used above is the favourable one. Measuring the detectable swing over
the full observed range of accumulated cold rather than from the median gives
28.5, 26.7 and 7.9 €/MWh. The verdict does not turn on that choice.

### 10.1 The sanity gate failed, and how it failed is informative

| market | `holiday` on the spread | on the night level |
| --- | --- | --- |
| Austria | −15.10 (8.09), t = −1.86 | −6.64 (16.32), t = −0.41 |
| Italy-North | +1.97 (6.50), t = +0.30 | −11.19 (11.20), t = −1.00 |
| Switzerland | +0.66 (2.20), t = +0.30 | **−7.84 (2.62), t = −2.99** |

The gate is registered on the primary outcome and is scored there: it fails in
all three. The level column was added after seeing that and is labelled post-hoc
in the pipeline output; it is there to distinguish a broken price panel from a
spread doing its job, not to move the goalposts.

It says the panel is not broken. Switzerland recovers Christmas cleanly on the
level, and the Austrian and Italian level coefficients are negative but drowned
by crisis-winter variance. What the spread column shows is that the Christmas
shutdown removes demand from the midday window and the night window at once, so
differencing them removes most of the effect too. That is the spread doing
exactly what section 3 built it to do. It is also a warning: **an outcome
constructed to be insensitive to common demand shocks is insensitive to the
Christmas reference effect as well**, which leaves this design with no working
sensitivity check on price. §8.8b of the root README already found the Christmas
gate fails against a good forecaster. This is a second, independent way to lose
it.

### 10.2 Switzerland produces another significant coefficient that cannot be real

`below:cum100` on the Swiss spread is **+1.46 (0.40), z = +3.65, p = 0.0003**:
significant, and pointing the wrong way. It is reported as a confound rather than
a finding, on the same grounds Switzerland's load coefficient was, and section 9
named the mechanism in advance:

> *Hydro reservoirs in Austria, Switzerland and Italy-North shift water between
> hours in response to the same weather, which moves the night-day spread for
> reasons unrelated to snowmaking.*

Switzerland is the most hydro-dominated market of the three and is where that
confound should bite hardest. It does. The coefficient is also five times smaller
than the market's own minimum detectable swing, so under the pre-registered rule
it is uninformative regardless of its p-value.

Austria shows a weaker version of the same thing on the level sensitivity,
+4.86 (1.99), p = 0.015, also wrong-signed, also inside a market the power gate
has already declared unable to see the effect.

### 10.3 Vermont: the one place a placebo settled it

The ISO-NE arm is the only part of this project where a placebo discriminated
outright rather than failing to.

**First, the local-content gate that section 9 asked for.** ISO-NE is usually
unconstrained overnight, so the worry was that the Vermont LMP is the system
price under another name, in which case a Vermont price test says nothing about
Vermont whatever its coefficient does. Measured over 10,269 shared hours: Vermont
and Rhode Island clear at the same cent in **0.4%** of them (0.4% on night hours
alone), correlation 0.9956, and Vermont's own congestion component is nonzero in
**45.3%** of hours with a mean absolute value of 0.50 USD/MWh. The zones are
tightly coupled but genuinely distinct. The gate passes.

**Then the coefficient, which looks like a finding until you read the next line.**

| | `below:cum100` on the spread | s.e. | p |
| --- | --- | --- | --- |
| **Vermont** | **−1.469** | 0.541 | **0.007** |
| **Rhode Island**, no snowmaking | **−1.328** | 0.523 | **0.011** |
| Vermont, load test's 5 seasons | −1.373 | 0.540 | 0.011 |
| Rhode Island, load test's 5 seasons | −1.175 | 0.519 | 0.024 |

Negative, significant, the predicted sign — and reproduced almost exactly in the
zone with no snow guns in it. The Vermont-minus-Rhode-Island difference is 0.14,
about a quarter of either standard error, and it is 0.20 on the load test's own
five-season sample. **What the coefficient measures is a New England–wide
relationship between accumulated cold and the night-day price spread. It is not a
Vermont snowmaking signal.**

The bottom two rows exist because the price panel has no weather-coverage filter
of its own and silently readmits the 2022 season, which the load test drops for
covering only 54% of the October–December clock. Restricting to the load test's
five seasons changes nothing.

**Why this placebo works when the load test's did not.** In the load test the
outcome is a regional *share*, and the eight shares sum to zero by construction,
so a genuine Vermont effect is forced to push Rhode Island the other way and the
placebo cannot cleanly separate signal from mirror image. Price has no such
constraint: both zones clear near the same system price, so a system-wide driver
appears identically in both while a Vermont-specific driver would appear in
Vermont alone. The compositional outcome that made the load test possible is
exactly what blunted its placebo, and the price outcome, useless for power, is
where the placebo becomes sharp.

**It was underpowered regardless.** ISO-NE's overnight supply slope is
+23.9 USD/MWh per GW, steeper than any European market here, but a 70 MW Vermont
fleet is still worth only 1.67 USD/MWh against a smallest detectable swing of
6.71. Even without the placebo the pre-registered rule would have declared it
uninformative. The sanity gate also failed the same way it did in Europe:
`holiday` = +1.56 (4.30) on the spread, +4.84 (7.14) on the level.

One deviation to note: the supply slope is estimated against **total** system
load rather than residual load, because EIA-930's ISNE subregion files carry no
wind or solar split. That biases the slope toward zero if anything, so the
implied impact is if anything overstated and the underpowered verdict is safe.

### 10.4 Two data facts worth recording

**The Austrian price panel is five seasons, not thirteen.** The AT bidding zone
did not exist before 1 October 2018, and this was established from the data
rather than assumed: energy-charts serves no AT price before that instant, SMARD
begins its AT and DE-LU series at the same epoch, and OPSD's DE-LU column is
empty for the earlier autumns. Nothing was back-filled from the common DE-AT-LU
price. So 300 of the load test's 780 nights carry a price at all.

**Austria and Italy-North are not independent tests on price.** Their day-ahead
prices are equal to the cent in **16.0 %** of shared hours, against 0.1 % for
Austria and Switzerland and 0.2 % for Switzerland and Italy-North. That is market
coupling across the Brenner working normally, and it is not a data defect, but it
means the Austrian and Italian price results are close to one observation rather
than two.

**A trap for anyone rerunning this.** From 1 October 2025 the European day-ahead
auction clears on a 15-minute MTU for AT and IT-North, and Switzerland did not
switch. A fetcher that de-duplicates timestamps instead of averaging the four
quarters keeps only the first quarter of each hour and never says so.
`fetch_prices.py` averages them, and the averaging was checked against two
independent publishers on a known hour.

## 11. Run it

```
python src/price/fetch_prices.py        # AT / CH / IT-North day-ahead spot
python src/price/fetch_lmp.py           # ISO-NE day-ahead hourly zonal LMP
python src/price/price_pipeline.py      # gates first, then the coefficients
```

Both fetchers cache every response and skip what is already on disk;
`fetch_lmp.py --no-fetch` rebuilds its CSVs from cache without making a single
request. Neither is fast on a cold cache. energy-charts rate-limits bursts even
at 3.5 s spacing, and ISO-NE needs about 9 s between per-day requests, so its
427 days take roughly 75 minutes.

`price_pipeline.py` rebuilds nothing on the right-hand side: it reads the night
panel each load pipeline wrote and joins one column onto it. Run the load
pipelines first, or there is nothing for it to join to.

Every number in section 10 is printed by these three scripts. None was carried
over from a prior pass or filled in by hand.
