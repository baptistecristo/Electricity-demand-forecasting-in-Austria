# Does the day-ahead spot price move with snowmaking weather?

> **STATUS: PRE-REGISTRATION. No price coefficient has been estimated yet.**
>
> The commit that adds this file and `price_pipeline.py` contains no results.
> Read `git log --oneline` to confirm that the results commit comes after it.
> That ordering is the only thing that makes the answer, whatever it turns out
> to be, worth reading. The load test in the repository root was built the same
> way for the same reason.

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

**Predicted sign: positive.** Snowmaking is a load. A load raises the price at
which the market clears. As cumulative cold hours accumulate the fleet is
progressively brought on, so the night-day spread should widen with `cum100`
among below-threshold nights.

Fixed before estimation:

1. **Supports the mechanism** if `below:cum100` is positive, significant at 5%,
   and its implied magnitude is within an order of magnitude of the price impact
   the power gate in section 7 computes from the market's own supply slope.
2. **Rejects the mechanism** if the 95% interval excludes that implied impact
   while the test is powered to have found it.
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
| day-ahead LMP, hourly | ISO-NE day-ahead hourly LMP by load zone | .Z.VERMONT, .Z.RHODEISLAND |
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

## 10. Run it

```
python src/price/price_pipeline.py
```

Everything the script prints is computed from data it fetches or from the four
committed night panels. No number in the results write-up will be carried over
from a prior pass.
