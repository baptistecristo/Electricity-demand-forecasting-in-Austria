# Snowfall-forecast revisions as the treatment

> **STATUS: data collection and parsing only. Nothing has been estimated.**
>
> This directory holds a working forecast archive and a verified parser. There is
> no specification committed here yet and no coefficient. When a design is
> settled it goes in its own commit *before* any result, the way
> `src/price/README.md` did.

## Why this exists

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

The wedge the design aims at: ISO-NE's day-ahead market closes at 10:30 ET. A
forecast revision arriving after that is information a resort can act on and the
day-ahead price cannot contain.

## Why Vermont and not the Alps

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

## The product, and why it is not the obvious one

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

## What is in the archive

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
weather: free ISO-NE day-ahead LMPs start 1 January 2016.

On a sample day the issuances land at 02:26, 05:19, 11:23, 14:32, 17:32, 19:39
and 23:02 UTC. The ISO-NE bid deadline is 15:30 UTC in winter, so there are
issuances cleanly before the gate and cleanly after it, which is what the design
needs.

## Four things found by inspection that would have failed silently

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

## What the parse yields

On the first 2,113 products (seasons 2016 to late 2020): 157,359 rows over 50
zones. Across the four core resort zones, **29.3% of forecast periods carry
non-zero snow and 6.4% carry two inches or more**, maximum 7.5 inches per
12-hour period. There is real variation to work with.

Each issuance gives roughly two to three forward 12-hour snow forecasts per zone,
so revisions are measurable at **zero-to-two-day lead**.

## The open question, stated before any result exists

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

## Run it

```
python src/revision/fetch_afm.py     # ~5,000 products, ~45 min cold, cached
python src/revision/parse_afm.py     # writes afm_snow.csv
python src/revision/parse_afm.py --audit    # check the column alignment
```

The cache path at the top of `fetch_afm.py` is the only thing that needs changing
on another machine.
