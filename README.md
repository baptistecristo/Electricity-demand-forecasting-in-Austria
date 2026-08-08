# Snowmaking as a hidden load in Austrian day-ahead electricity forecasts

**Status: pre-registered, data collection in progress.** No results yet. The
predictions and the kill criteria in §5 were published before any load data was
examined — commit history is the proof.

---

## Abstract

Austrian ski resorts consume roughly 281 GWh of electricity per season making
artificial snow, concentrated into a few hundred cold night hours in November and
December. At full fleet coincidence that is 1.5 GW; at realistic coincidence,
0.6–1.1 GW, or 8–15% of Austria's overnight demand.

Snowmaking is a *task*, not a weather response. It runs only below a wet-bulb
threshold near −2 °C, it stops once the base layer is built, and it is
front-loaded before opening day. Two identical cold nights therefore draw very
different amounts of power depending on how much snow has already been made.

This repository tests whether that path dependence shows up as a systematic,
state-dependent error in published day-ahead load forecasts. The headline
prediction is not that cold nights are under-forecast — that is confounded by
heating load and probably already priced into any temperature coefficient. The
prediction is that **the threshold effect shrinks as season-to-date accumulated
cold rises**, which no memoryless temperature model can generate and no heating
confound can mimic.

A null result is the modal outcome and is reported either way.

---

## 1. The question

Transmission system operators publish a day-ahead load forecast. ENTSO-E and APG
both make the forecast and the realised load available for free. The difference
between them is the forecast error.

If snowmaking is genuinely invisible to the forecast, the error should be
positive (load under-predicted) on nights when snowmaking runs, and the size of
that miss should depend on the state of the snowpack rather than on temperature
alone.

## 2. How big is the load?

From Aigner, Steiger & Mayer (2026), a survey of 141 Austrian resorts, 30 usable,
covering 4,253 equipped hectares or 34.0% of Austrian ski volume:

| Quantity | Value |
|---|---|
| Season electricity, Austria-wide | **281 GWh** (range 260–309) |
| Share of Austrian electricity consumption | 0.46% |
| Mean operating hours per snowmaker per season | **184.6 h** |
| Snowmakers per hectare | 2.9 |
| Energy per hectare equipped | 22,449 kWh |
| Energy per m³ of snow | 3.3 kWh |

The instantaneous power follows from energy over operating hours:

```
Fleet-wide coincident ceiling = 281 GWh / 184.6 h = 1.52 GW

Mean draw per snowmaker while running = 41.9 kW
  Consistent with a lance/fan-gun mix plus pumping and compressed air.
  Internal cross-check passes.

At realistic coincidence:
  40% → 0.61 GW      60% → 0.91 GW
  50% → 0.76 GW      70% → 1.07 GW
```

Austrian weekday overnight load in November and December runs 7.0–7.5 GW
(sampled: 10 Dec 2024 at 7.12–7.48 GW, 5 Dec 2023 at 7.17–7.60 GW). Snowmaking is
therefore **8–15% of overnight demand**, centred near 12%.

Reproduce with `python src/magnitude.py`.

### Two caveats carried forward

**Older figures are too high.** Steiger et al. (2021) put Austrian snowmaking at
355–950 GWh/season. The 2026 survey states these are overestimates. All arithmetic
here uses 281 GWh.

**Part of the load is not in the dependent variable.** APG's published total load
covers all of Austria since 2012 *"mit Ausnahme eines Korridors in Vorarlberg"* —
except a corridor in Vorarlberg, a legally separate control area (VÜN, §23 ElWOG
2010) jointly operated with APG since 1 Jan 2012. Vorarlberg holds real snowmaking
capacity (Lech/Zürs, Montafon) and consumes 2,667 GWh/yr in total. The analysis
reports results with Vorarlberg weighted at 0.10 and at 0.00 in the weather index.

## 3. Why the forecast might miss it — and why it might not

The naive version of this hypothesis is that load forecasts are temperature
models and temperature models have no memory. Two mechanisms argue against it,
and both shrink the expected effect:

**A memoryless model still absorbs the average response.** The temperature
coefficient is estimated on history in which cold nights *are* snowmaking nights.
The model does not need to know snowmaking exists to price it in on average. What
remains in the residual is the deviation from the conditional mean given
temperature — the snowmaking *anomaly*, not the snowmaking *load*.

**Production forecasts are autoregressive.** APG publishes at 08:00 for the
following day and lists its inputs as historical actual load, day type including
holiday calendar, and temperature forecast. Yesterday's actual is already in
there. Any lagged-load term propagates a running snowmaking campaign into
tomorrow's forecast, so the effect survives on the *first* night of a campaign and
decays over the following 24–48 hours.

Call α the share of snowmaking load the forecast leaves unexplained. These two
mechanisms push α down, and §6 shows α is the binding constraint on the whole
design.

## 4. Identification

The obvious test — compare nights just below the wet-bulb threshold to nights
just above — is contaminated. At 1,800 m, −2 °C wet bulb corresponds to roughly
−1 to 0 °C air temperature, and every nonlinearity in heating load lives near
freezing: heat-pump COP collapse and resistive backup cutover, defrost cycles,
pipe and road trace heating. Humidity, which enters wet bulb, is itself a load
driver.

The identifying variation is therefore not the threshold crossing but its
**interaction with accumulated season-to-date cold**:

```
err ~ below × cum_cold_hours
      + dist + below:dist
      + hour FE + dow FE + season FE
      (SE clustered by date, bandwidth ±3 °C around the threshold)

err            = actual load − day-ahead forecast, MW
below          = 1 if the alpine wet-bulb index < −2 °C
dist           = wb_index − (−2)
cum_cold_hours = hours below threshold since 1 Oct, current season
```

Heating load does not care how many cold hours the season has already delivered.
Snowmaking does, because the base gets built and the guns stop. The interaction is
the only coefficient in this design that a temperature confound cannot produce.

### Building the wet-bulb index

Three things that decide the answer before the econometrics do:

- **Altitude band.** Snowmaking happens at 1,200–2,500 m. Valley stations cross
  the threshold hundreds of hours later. Stations are selected at 900–2,600 m.
- **Station pressure.** ISA pressure at 1,800 m is 815 hPa. Assuming sea level
  shifts wet bulb by 0.2–0.4 °C, comparable to the RD bandwidth.
- **Solver, not closed form.** The Stull (2011) approximation errs by ~0.7–1.0 °C
  at sub-zero temperatures, worse than the effect being chased. `src/snowload.py`
  bisects the psychrometric equation instead, agreeing with reference tables to
  ~0.2 °C.

Regions are weighted by state share of Austrian skier visits: Tirol 0.50,
Salzburg 0.24, Vorarlberg 0.10, Steiermark 0.09, Kärnten 0.05.

### On the threshold value

There is no lance-versus-fan-gun threshold split. Olefs et al. (2010) report that
manufacturers quote −1.5 °C wet bulb for both air-water lances and fan guns, and
round to −2 °C; TechnoAlpin quotes −2.5 °C with no equipment distinction. The
documented lance/fan difference is water loss (15–40% vs 5–15%), not temperature.

The threshold is soft for economic reasons instead: marginal production starts
near −2 °C, efficient production wants −4 °C or colder, and how early a resort
starts depends on how far behind its base is. That state dependence is what the
interaction exploits.

## 5. Pre-registered predictions and kill criteria

**Primary prediction.** The `below × cum_cold_hours` coefficient is negative and
significant at 5% with date-clustered standard errors.

**Supporting predictions.**

1. *Campaign starts.* Defining a start as the first hour below threshold after
   ≥48 h above it, the forecast error spikes on night 1 and decays over 24–48 h.
   A temperature confound gives a flat profile across campaign days.
2. *Opening dates.* Conditional on wet bulb and day of season, the error is
   smaller after resorts open than before.
3. *Placebos.* The Netherlands and Denmark, run through the identical pipeline,
   show no effect. Summer months show no effect.

**Kill criteria, committed before looking:**

- The NL placebo shows the same jump → the result is heating load. Stop.
- The interaction coefficient is zero or positive with a tight confidence
  interval → no memory effect. Stop.
- The event-study profile is flat across campaign days → the forecast already
  absorbs it. Stop.

**Publication commitment.** All three outcomes get written up. A null is the
modal outcome and the interesting question either way is how much of a large,
physically lumpy, path-dependent industrial load a production forecast can absorb
without being told about it.

## 6. Statistical power

![Minimum detectable effect versus plausible residual signal](figures/detectability.png)

Assumptions: 9 snowmaking episodes per November–December season, 8 night hours
each, within-episode residual correlation 0.7, overnight load 7.0 GW, 80% power at
5% two-sided. Error scale anchored on a measured figure: the DE-LU zone TSO
day-ahead load forecast has MAE of 3.14% of mean load over 2016–2019 ENTSO-E data.
Austria is a smaller zone, so its relative error is likely worse. MAE converted to
standard deviation assuming near-normal errors.

| Day-ahead forecast error | sd | MDE at 4 seasons | at 7 | at 12 | α needed at 7 seasons |
|---|---|---|---|---|---|
| optimistic, MAE 1.5% | 132 MW | 105 MW | 80 MW | 61 MW | **8.9%** |
| DE-LU measured, MAE 3.14% | 275 MW | 221 MW | 167 MW | 127 MW | **18.5%** |
| small-zone penalty, MAE 5% | 439 MW | 352 MW | 266 MW | 203 MW | **29.5%** |

Read the last column as the pass mark. With the seven clean seasons available
since the bidding-zone split, the forecast must be missing at least ~19% of
snowmaking load for the test to have 80% power.

**More data does not fix this.** Going from 7 to 12 seasons moves the pass mark
only from 18.5% to 14%. The binding constraint is α, and α is decided by §3.

The first computation once load data is in hand is therefore the measured
Austrian forecast error standard deviation, which collapses this table to one
row. `src/snowload.py` prints it before running anything else.

Reproduce with `python src/power.py`.

## 7. Data

| Series | Source | Access |
|---|---|---|
| AT day-ahead total load forecast (A65) | ENTSO-E Transparency | free token, ~3 working days |
| AT actual total load (A16) | ENTSO-E Transparency | same token |
| AT day-ahead forecast + actual, 15-min, 2024– | markt.apg.at ZIP downloads | no registration |
| Hourly temperature and humidity, alpine stations | GeoSphere Austria `klima-v2-1h` | no key |
| Resort opening dates | resort sites and Wayback | manual, ~30 resorts |

The ENTSO-E token is free: register at transparency.entsoe.eu, email
transparency@entsoe.eu with subject "RESTful API access", approval within three
working days, then generate the token under My Account.

Raw data is not committed. `data/README.md` documents exactly how to fetch it.

### Structural breaks

- **1 Oct 2018.** The DE-AT-LU bidding zone split took effect. The load series is
  continuous; the price series is not. Seven clean seasons follow.
- **Season 2020/21.** Austrian lifts shut in the November lockdown, reopened
  24 December, hotels and borders closed, effectively locals-only. Resorts still
  made snow. Excluded from the main sample, then used as a bonus test: the
  coefficient should shrink, not vanish. If it vanishes, the design was measuring
  tourism rather than snowmaking.

## 8. Results

Pending. This section will be added, not substituted — the pre-registration above
stays as written.

## 9. Limitations

- Roughly 360 relevant hours per season, heavily autocorrelated. Effective sample
  size is episodes, not hours.
- The published forecast is the TSO's transparency artefact, not the trading
  consensus. A systematic bias in it demonstrates a blind spot in APG's forecast,
  **not** a market mispricing. Establishing the latter requires day-ahead price or
  imbalance as the outcome and is a separate study.
- Part of Vorarlberg is outside the published load series (§2).
- Opening dates are collected manually for the ~30 resorts covering most capacity,
  so the opening-date test is coarser than the others.

## 10. Reproduce

```bash
pip install -r requirements.txt
export ENTSOE_TOKEN=...           # see §7
python src/magnitude.py           # load magnitude arithmetic, no data needed
python src/power.py               # detectability calculation, no data needed
python src/snowload.py --seasons 2018 2019 2021 2022 2023 2024
```

`snowload.py` selects alpine stations by altitude and state, solves the
psychrometric wet bulb with a station-pressure correction, builds the
region-weighted index and the season-to-date cold accumulator, detects campaign
starts, and runs all four specifications plus the placebos. It prints the measured
forecast error standard deviation and the implied α pass mark before anything
else, so the go/no-go decision comes first.

## References

- Aigner, Steiger & Mayer (2026). *Snowmaking in Austria: resource consumption and greenhouse gas emissions.* Journal of Sustainable Tourism. [Article](https://www.tandfonline.com/doi/full/10.1080/09669582.2026.2656746) · [Figures](https://ciss-journal.org/article/view/11546) · [PDF](https://zukunft-skisport.at/wp-content/uploads/2025-09-16_IMC-Innsbruck_Snowmaking_Aigner-Steiger-Mayer_final.pdf)
- Olefs, Fischer & Lang (2010). *Boundary conditions for artificial snow production in the Austrian Alps.* J. Appl. Meteorol. Climatol. 49(6). [Article](https://journals.ametsoc.org/view/journals/apme/49/6/2010jamc2251.1.xml)
- Stull (2011). *Wet-bulb temperature from relative humidity and air temperature.* J. Appl. Meteorol. Climatol. 50(11). (Used as a benchmark, not in the pipeline.)
- [APG actual total load](https://markt.apg.at/en/transparency/load/actual-total-load/) and [total load forecast](https://markt.apg.at/en/transparency/load/total-load-forecast/)
- [VÜN Netzentwicklungsplan 2025](https://www.e-control.at/documents/1785851/0/VUEN+NEP+2025.pdf), E-Control
- [EPEX SPOT, DE-AT-LU bidding zone split](https://www.epexspot.com/en/news/epex-spot-publish-separate-prices-and-volumes-austrian-and-german-day-ahead-markets)
- [Maldonado et al., arXiv 2302.11017](https://ar5iv.labs.arxiv.org/html/2302.11017) — DE-LU TSO day-ahead load forecast MAE
- [GeoSphere Austria Dataset API](https://dataset.api.hub.geosphere.at/v1/docs/)
- [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/)

## License

MIT. See [LICENSE](LICENSE).
