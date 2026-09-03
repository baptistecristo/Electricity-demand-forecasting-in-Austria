# TO BE FINISHED: Snowmaking as a hidden load in Austrian day-ahead electricity forecasts

### 📄 [Read the paper →](https://snowmaking-load-austria.vercel.app)

**Pre-registered, tested in four markets, null in Austria.** This repository holds
the code, the data recipe and the commit history behind that paper. The full
argument, the figures and every table live on the page above.

## In short

Austrian ski resorts burn about 281 GWh of electricity a year making artificial
snow, and they burn nearly all of it on cold November and December nights. While
the guns are running that is close to 900 MW, or 8 to 15% of what Austria draws
overnight.

I wanted to know whether the grid operator's day-ahead load forecast sees it
coming. A forecast that misses a load this lumpy leaves a predictable error
behind, and predictable error is the kind of thing somebody gets paid for.

Comparing cold nights to mild ones does not work, because heating load rises with
cold too. What separates snowmaking from heating is memory. Once the base layer
is built the guns stop, so an identical cold night draws far less power in late
December than in early November. Heating has no such memory. The prediction, then,
is that the cold-night effect *shrinks* as the season's accumulated cold rises.

I wrote that prediction and three stopping rules into the repository before
opening any load data. The commit history is the proof of order.

It came back null. The interaction is +5.1 MW against a standard error of 11.9,
and two of the three stopping rules fired. On the same nights the same equation
recovers the Christmas industrial shutdown at −274 MW, so the design can see
effects of the size snowmaking would have to produce. It does not see snowmaking.
Three further markets were run: Italy agrees, Switzerland could never have seen
the effect, and Vermont is suggestive but does not survive a change of weather
station.

## Headline numbers

| | |
|---|---|
| Pre-registered interaction, Austria | **+5.1 MW** (s.e. 11.9), 780 nights, 13 seasons |
| Same equation, Christmas shutdown | **−274 MW** (t = −3.3) |
| Kill criteria fired | **2 of 3** |
| Italy-North | +4.3 (10.2), null |
| Switzerland | needs α = 201%, could never have detected it |
| Vermont | −0.0211 pp of share (s.e. 0.0073, p = 0.004), suggestive |
| The bound behind all four | no test here could see a forecaster missing **less than about a quarter** of the snowmaking load |

## What is in this repository

| Path | What it is |
|---|---|
| `src/snowload.py` | the pre-registration commit's script, carrying the predicted sign and the kill criteria |
| `src/apg_pipeline.py` | the Austrian pipeline that produced the reported results |
| `src/magnitude.py`, `src/power.py` | the load arithmetic and the ex-ante detectability calculation, neither needing data |
| `src/it_north/`, `src/swiss/`, `src/vermont/` | the three replications, each with its own README and its own list of deviations |
| `src/price/` | the separately pre-registered day-ahead spot price test |
| `site/` | the paper: `build.py` renders the single-file page |
| `data/README.md` | how to fetch the raw series, which are not committed |

## Reproduce

No token and no registration required:

```bash
pip install -r requirements.txt
python src/apg_pipeline.py
```

That downloads both APG archives, unpacks the nested per-year ZIPs, joins the
15-minute actual load to the 15-minute day-ahead forecast at hourly resolution,
selects the alpine stations, solves the psychrometric wet bulb with the station
pressure correction, builds the region-weighted index and the season-to-date cold
accumulator, detects campaign starts, writes `data/night_panel.csv`, and prints
the gate statistics followed by all four specifications. A few minutes, most of it
the two ~6 MB downloads.

```bash
python src/magnitude.py            # load magnitude arithmetic, no data needed
python src/power.py                # detectability calculation, no data needed

python src/it_north/it_pipeline.py # Terna, Italy-North bidding zone
python src/swiss/ch_pipeline.py    # Swissgrid via energy-charts
python src/vermont/vt_pipeline.py  # ISO-NE, regional share outcome

python src/price/fetch_prices.py   # day-ahead spot, AT / CH / IT-North
python src/price/price_pipeline.py # gates first, then the coefficients
```

`price_pipeline.py` reads the night panel each load pipeline wrote, so run those
first. Vermont is slow on a cold cache: ISO-NE rate-limits its per-day CSV hard
enough that 427 dates take about 75 minutes, and the script paces itself
accordingly. `snowload.py` is the ENTSO-E path, kept because it handles the NL/DK
placebos that APG cannot serve; set `ENTSOE_TOKEN` to use it.

## Data

| Series | Source | Access |
|---|---|---|
| AT actual load, 15-min, 2009–2022 | markt.apg.at `Gesamtlast.zip` | no registration |
| AT day-ahead forecast, 15-min, 2010–2022 | markt.apg.at `Prognose über die Gesamtlast.zip` | no registration |
| Hourly temperature and humidity, alpine stations | GeoSphere Austria `klima-v2-1h` | no key |
| AT forecast and actual load (A65, A16) | ENTSO-E Transparency | free token, ~3 working days |
| IT / CH forecast, load and spot price | energy-charts.info (Fraunhofer ISE) | no token |
| Vermont regional demand forecast | ISO-NE, EIA-930 | no key |

The APG archives go back to 2009, not 2024 as the web view implies, which is
thirteen overlapping seasons with no token and no waiting. Raw data is not
committed; `data/README.md` documents exactly how to fetch it.

## References

- Aigner, Steiger & Mayer (2026). *Snowmaking in Austria: resource consumption and greenhouse gas emissions.* Journal of Sustainable Tourism. [Article](https://www.tandfonline.com/doi/full/10.1080/09669582.2026.2656746) · [PDF](https://zukunft-skisport.at/wp-content/uploads/2025-09-16_IMC-Innsbruck_Snowmaking_Aigner-Steiger-Mayer_final.pdf)
- Olefs, Fischer & Lang (2010). *Boundary conditions for artificial snow production in the Austrian Alps.* J. Appl. Meteorol. Climatol. 49(6). [Article](https://journals.ametsoc.org/view/journals/apme/49/6/2010jamc2251.1.xml)
- Stull (2011). *Wet-bulb temperature from relative humidity and air temperature.* J. Appl. Meteorol. Climatol. 50(11). (Benchmark only, not used in the pipeline.)
- [Maldonado et al., arXiv 2302.11017](https://ar5iv.labs.arxiv.org/html/2302.11017), DE-LU TSO day-ahead load forecast MAE

The full reference list is on the [paper](https://snowmaking-load-austria.vercel.app).

## License

MIT. See [LICENSE](LICENSE).
