# Imbalance as the outcome: two arms, registered before any coefficient

> **STATUS: this file is the pre-registration. There is no result here.**
>
> Sections 4 to 11 fix the unit of observation, both treatments, the outcome, the
> specifications, the predicted signs, the kill criteria and the power gates.
> They are committed before a single coefficient is estimated, the way
> `src/price/README.md` §1–9 and `src/revision/README.md` §6–11 were, and for the
> same reason: the ordering in `git log --oneline -- src/imbalance/` is the only
> thing that makes whatever comes next worth reading.
>
> Every number below is either a design choice, a published constant carried in
> from another section, or a descriptive count of the acquired archive. None is a
> coefficient, a standard error or a p-value.

## 1. Why this exists

Root README §9 lists imbalance as the one untried instrument in the project.

Every outcome used so far is either a **published forecast error** (the load arm)
or a **cleared price** (the price arm). Both are produced by an agent who could
have known better, and both are coarse: hourly at best, and in the price arm
§10 found the overnight merit order close to flat in all four markets, so the
outcome barely moves whatever the load does.

Imbalance is different in three ways that matter here.

1. **It is measured by the TSO, not by me.** APG settles it. It is not a residual
   from a model I fit.
2. **It is quarter-hourly.** PT15M is the finest-grained outcome anywhere in this
   project, against hourly load and hourly day-ahead price.
3. **It is where unabsorbed news has to go.** APG publishes its day-ahead load
   forecast at 08:00 on D-1 and the day-ahead auction clears around noon.
   Anything the forecast failed to absorb, or that arrived after both gates,
   cannot be in the schedule. It lands in imbalance by construction.

Point 3 is what §8 below turns into a design, and it is the first instrument in
this project that speaks directly to the **α** parameter of root README §3 — the
share of snowmaking load the day-ahead forecast already absorbs — rather than
around it.

## 2. The series, and the eleven seasons that survive

| series | code | endpoint parameter |
| --- | --- | --- |
| Total imbalance volumes [17.1.G] | `A86` | `controlArea_Domain` |
| Imbalance prices [17.1.F] | `A85` | `controlArea_Domain` |
| Day-ahead prices [12.1.D] | `A44` | `in_Domain` / `out_Domain` |

`A85` and `A86` return data for AT continuously from 2014 to 2025, confirmed by
probing 1 December of each year. **Season 2014 is nevertheless dropped, leaving
eleven seasons, 2015 to 2025.** The reason is in `fetch_entsoe.py` fact 6: in
2014 essentially every quarter-hour is labelled with one flow direction (2,973 of
2,976 in October) while 2015 onward splits sensibly, and the hypothesis that 2014
signs its values within a single direction is false because every 2014 quantity
is non-negative. The 2014 series is an unsigned magnitude with a constant label
and carries no directional information at all.

Eleven seasons compares with six for the Austrian load panel and ten for Vermont.

## 3. Six format facts, and why they are in the fetcher rather than here

`fetch_entsoe.py` documents six things found by inspection, each of which
produces a wrong answer silently and none of which raises: the ZIP wrapper, the
three mutually exclusive value tags, `position` restarting inside every `Period`,
`curveType=A03` meaning a held value rather than a gap, `A44` publishing two
resolutions for the same month, and the 2014 direction defect above.

The one worth repeating here is the third, because it is the only one whose
output passes every count check. On 2023-12-01 the AT volume document splits the
day into 23 `Period` blocks across two TimeSeries, one per contiguous run of a
single flow direction. `position` restarts at 1 in each. The timestamp of a point
is `Period.start + (position − 1) × resolution` and **not** an offset from the
requested window. A parser that assumes one Period per TimeSeries still emits
exactly 96 values of plausible magnitude, in scrambled order, on every day of
eleven seasons.

### 3.1 Sign convention, established from the data before anything was built

`flowDirection.direction` is A01 or A02 and the mapping to short and long is not
documented in the response. It was read off the data by the one test that does
not depend on which direction happens to fall in expensive hours: within a
quarter-hour, when the control area is short the TSO is buying, so the imbalance
price must sit above the day-ahead price. Over December 2023, 2,976
quarter-hours:

| direction | imbalance − day-ahead | median | positive in |
| --- | --- | --- | --- |
| A01 | +54.78 | +30.92 | 86.4% |
| A02 | −51.84 | −39.06 | 6.4% |

**A01 is system short. A02 is system long.** This project published one
pre-registered sign backwards once already; the correction cost more than this
check did.

Austria settles on a single imbalance price: categories A04 and A05 carry
identical values.

## 4. Unit of observation and the outcome

**One observation per night**, matching every other arm in this project. The
night is 20:00–06:59 `Europe/Vienna`, labelled by `date(timestamp − 7h)`, and is
kept only if at least 8 of its 11 hours are valid, which at PT15M means at least
32 quarter-hours. Copied from `src/apg_pipeline.py`, not re-derived.

**A night is 44 quarter-hours except one a year, when it is 48.** European
summer time ends on the last Sunday of October, inside the 1 October window, so
that night runs 12 hours. Verified on the acquired data: October 2024 holds
exactly 2,976 UTC quarter-hours, local 27 October holds 100, and exactly one
night in the month holds 48 against 29 full nights at 44. A completeness rule
written as `== 44` silently drops the fall-back night in every season, and one
expressed as a share of a hardcoded 44 scores that night at 109% complete. The
rule is an absolute count of at least 32, which is correct in both cases.
§8.10 of the root README was a timezone error and §8.5b still carries it; this
one is checked rather than assumed.

**Primary outcome: mean signed imbalance over the night, in MW.**

    signed(q) = +value(q)  if flowDirection is A01 (short)
                −value(q)  if flowDirection is A02 (long)
    imb(D)    = 4 × mean over the night's quarter-hours of signed(q)

`A86` publishes MWh per quarter-hour (`quantity_Measure_Unit.name = MWH`), so the
factor of 4 puts the outcome in MW and makes it directly comparable to the 900 MW
fleet figure of root README §2 and to the load arm's coefficients in MW.

Short is positive, which makes the outcome the direct analogue of the load arm's
`err = actual − forecast`, where positive means under-forecast. **The whole
project therefore keeps one sign convention**, and the predicted signs in §7 and
§9 are the same negative as the load arm's for the same reason.

Quarter-hours carrying the rare third direction code `A03` are excluded from the
signed aggregate and counted in the run log.

**Secondary outcome: the night-mean imbalance price premium**, `A85` minus the
day-ahead price from `A44`, in EUR/MWh, with the hourly day-ahead price held
across its own hour. Reported alongside, never substituted for the primary.

## 5. Two arms, and why both are registered

The user chose to register both rather than pick one. They fail in different
ways, which is the point: a null in both is more informative than a null in
either.

| | arm A, replication | arm B, post-gate revisions |
| --- | --- | --- |
| seasons | 11 (2015–2025) | 2 (2024–2025) |
| treatment | `below × cum100` | snowfall forecast revision |
| identification | weak, collinear with day-of-season | sharp, but confounded by hydro |
| speaks to | does the load show up at all | **α directly** |

## 6. Arm A specification, the replication

    imb ~ below*cum100 + dist + below:dist
          + holiday + doy_c + I(doy_c**2) + C(season) + C(dow)

One observation per night, HC1 standard errors, estimated at night level. This is
`src/apg_pipeline.py`'s right-hand side **verbatim**, with imbalance substituted
for forecast error as the outcome and nothing else changed. That is deliberate:
the whole value of arm A is that it is the same test measured by the TSO instead
of by me, so any difference in the answer is attributable to the outcome and not
to a redesign.

`below`, `cum100`, `dist`, `holiday`, `doy_c` and `season` are constructed
exactly as in the load arm. Wet-bulb keeps the project's non-negotiables: the
900–2,600 m altitude band, station pressure rather than sea level, and the
bisection solver rather than the Stull (2011) closed form.

**Primary coefficient: `below × cum100`. Predicted sign: negative.** Snowmaking
adds unforecast load, so the system runs short on snowmaking nights, and the
effect fades as the base is built. A fade is a negative number. This is the same
prediction, with the same reasoning, as root README §4.

**Arm A inherits the ceiling it was built to escape.** `cum_cold_h` is collinear
with day-of-season, which is what produced the 27–201% α bound of §8.8b. Arm A
does not fix that and is not claimed to. It asks a narrower question: with a
finer, independently-measured outcome, does the same treatment move anything.

## 7. Arm B specification, the post-gate revision

Two gates, both on D-1: APG publishes the day-ahead load forecast at **08:00**
and the day-ahead auction clears around **12:00**. Let `g` be the later of the
two. For the night beginning on D:

    rev_pre  = S(last run before g)      − S(first run of D-1)
    rev_post = S(last run before 20:00 D) − S(last run before g)

`S` is expected overnight snowfall in the 900–2,600 m band over the Austrian ski
regions, from Open-Meteo's previous-runs archive.

    imb ~ rev_pre + rev_post + snow_gate + wb_gate + wbrev_pre + wbrev_post
          + holiday + doy_c + I(doy_c**2) + C(season) + C(dow)

### 7.1 The two coefficients separate, and this is the mirror of the Vermont arm

`src/revision/README.md` registers `rev_post = 0` as its falsification, because a
day-ahead **price** is fixed at the gate and cannot respond to later news. For an
**imbalance** outcome the logic inverts, and both coefficients become
interpretable rather than one being a placebo:

- **`rev_post` ≠ 0 is irreducible.** The news arrived after both gates. No
  forecaster could have used it. Imbalance is the correct place for it to land
  and nobody is at fault. This coefficient is the design's **positive control**.
- **`rev_pre` ≠ 0 is a forecasting failure, and it is α.** That information was
  published, on the table, before APG's forecast went out. If the forecast had
  absorbed it, it would not appear in imbalance. A non-zero `rev_pre` is the
  day-ahead forecast demonstrably failing to use snowfall information it held.

That is the first quantity in this project that bears directly on the blind-spot
claim rather than on whether the load exists. Every earlier arm measured whether
snowmaking moves something. This one measures **whether the forecaster saw it**,
which is what root README §3 has been asking since the beginning.

### 7.2 The two coefficients identify α as a ratio

An earlier draft of this section said a non-zero `rev_pre` *is* α. That is wrong
and the correction belongs here rather than in a later commit.

Let β be the imbalance response to a one-inch revision in expected overnight
snowfall, and α the share of that response the day-ahead forecast absorbs, which
is the parameter root README §3 defines and §8.8b could only bound between 27%
and 201%.

    coef(rev_post) = β            absorbed share is zero by construction
    coef(rev_pre)  = (1 − α) β    the forecast had it and used α of it

so

    α = 1 − coef(rev_pre) / coef(rev_post)

**Registered as the arm's headline estimand.** It is a ratio, so three rules come
with it and are registered now rather than chosen once the numbers are visible:

1. **Report it only if `rev_post` is significant.** A ratio with an insignificant
   denominator is unbounded. This is kill criterion 3 and it is the reason that
   criterion is scored before `rev_pre` is read.
2. **The interval is Fieller's, not the delta method.** A ratio of two normal
   coefficients is not normal, and the delta method understates the interval
   badly when the denominator is imprecise, which on two seasons it will be.
3. **The identifying assumption is that β is the same for pre-gate and post-gate
   news.** It may not be: pre-gate revisions arrive at longer lead, and a resort
   with more notice can respond more completely, which would make β larger before
   the gate and bias α upward. This is stated as an assumption because it cannot
   be tested with these data, and it is the main reason to read α as indicative
   rather than as a measurement.

**Predicted signs, both negative.** A revision toward more natural snow means
less snowmaking, so less load than was scheduled, so the system runs long, so
signed imbalance falls.

## 8. Kill criteria

Scored in this order and printed in this order.

1. **UNINFORMATIVE, arm A**, if the minimum detectable effect exceeds the §10
   upper bound. The coefficient is reported and no claim is made from it, exactly
   as for Switzerland's load coefficient and all four price coefficients.
2. **KILL** if the arm A interaction is **positive** and significant. That is the
   opposite of the registered prediction and is scored as a failure, not
   reinterpreted. This is the criterion the load arm's §4 fires on and it is
   copied deliberately.
3. **NO POSITIVE CONTROL, arm B**, if `rev_post` is not significant. If news that
   provably could not be scheduled does not move imbalance, then either the
   snowmaking response is absent or the outcome cannot see it, and **`rev_pre`'s
   null carries no information about α.** This is scored before `rev_pre` is
   read and it is the criterion arm B is most likely to fail, because two seasons
   is thin.
4. **CONFOUNDED, arm B**, if the hydro control of §11 moves `rev_pre` by more
   than half a standard error. Snow revisions move reservoir scheduling and
   snowmaking with the same sign, and if the two cannot be separated then arm B
   identifies nothing regardless of significance.
5. **NOT AUSTRIA-SPECIFIC** if the CH control reproduces either coefficient
   within half a standard error, the discipline `src/price/README.md` §10.3
   established with Rhode Island and that Vermont later failed.

## 9. Multiplicity, registered rather than discovered

Two arms, two outcomes, and a list of sensitivities. Ten-odd looks at 5% give
roughly a 40% chance that one returns significant on noise alone.

**Registered: the primary coefficient of each arm is the only one that can
support a claim. Sensitivities are descriptive and cannot upgrade a null
primary.** The secondary price-premium outcome is reported for every
specification the primary is, so nothing is hidden by having chosen one.

This rule is written here because the revision arm's review noted its absence
there, and the criticism applies with more force to a directory registering two
arms at once.

## 10. Power gate, computed before any coefficient is looked at

Same assumption-free structure as `src/revision/README.md` §11.

The largest imbalance any snowmaking response could produce is the one where the
entire Austrian fleet is unforecast: **900 MW** (root README §2) at the
**50–60%** coincidence factor recorded there, so **450–540 MW**, and the upper
bound taken forward is **540 MW**.

1. Print the minimum detectable effect as `2.80 × HC1 s.e.` scaled by the full
   observed range of `cum_cold_h`, which is §8.8b's formula rather than a new
   one, and separately for a one-standard-deviation revision in arm B.
2. Compare to 540 MW.
3. If the MDE exceeds it, criterion 1 fires whatever the coefficient is.
4. Print the night-level standard deviation of the outcome first, since that is
   what sets the answer and it is a descriptive rather than a result.

**The gate can fire "underpowered" and cannot certify the converse.** An MDE
below 540 MW means the test could have seen a total fleet shutdown, which no
night resembles. Stated here so it cannot be quietly read the other way later.

## 11. What this cannot do

- **Hydro.** Austria has large seasonal reservoir hydro, and a snow revision
  moves both snowmaking and reservoir scheduling. This is the reason
  `src/revision/README.md` §2 sent the revision design to Vermont instead. Arm B
  runs it in Austria anyway because the imbalance outcome exists only here, and
  criterion 4 is the admission that it may not survive. A control for reservoir
  level and hydro generation is included and it is not claimed to be sufficient.
- **Two seasons is thin for arm B.** Open-Meteo's previous-runs archive begins
  2024-01-19.
- **Imbalance is netted across the control area.** Everything else moving in
  Austria at 03:00 is in the same number, and snowmaking is a small share of it.
- **Arm A cannot escape the collinearity.** §6.
- **A quarter-hourly outcome is not a quarter-hourly treatment.** Wet-bulb and
  snowfall are hourly at best, so the fine resolution buys precision in the
  outcome and nothing in the treatment.

## 12. Run it

```
python src/imbalance/fetch_entsoe.py --probe        # which zones serve
python src/imbalance/fetch_entsoe.py --check-sign   # the A01/A02 convention
python src/imbalance/fetch_entsoe.py                # cache + tidy CSVs
```

The cache lives at `C:\Users\bcris\snow\entsoe-cache`, outside the repository,
because these are bulk third-party files and the repository is public. The token
is read from `ENTSOE_TOKEN` or from `.env` at the repository root, which
`.gitignore` covers, and is never written to the cache, a filename, or the log.
