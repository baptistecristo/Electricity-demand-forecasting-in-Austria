# TO BE FINISHED: Snowmaking as a hidden load in Austrian day-ahead electricity forecasts

### 📄 [Read the paper →](https://snowmaking-load-austria.vercel.app) · [PDF](site/paper.pdf)

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

## References

- Aigner, Steiger & Mayer (2026). *Snowmaking in Austria: resource consumption and greenhouse gas emissions.* Journal of Sustainable Tourism. [Article](https://www.tandfonline.com/doi/full/10.1080/09669582.2026.2656746) · [PDF](https://zukunft-skisport.at/wp-content/uploads/2025-09-16_IMC-Innsbruck_Snowmaking_Aigner-Steiger-Mayer_final.pdf)
- Olefs, Fischer & Lang (2010). *Boundary conditions for artificial snow production in the Austrian Alps.* J. Appl. Meteorol. Climatol. 49(6). [Article](https://journals.ametsoc.org/view/journals/apme/49/6/2010jamc2251.1.xml)
- Stull (2011). *Wet-bulb temperature from relative humidity and air temperature.* J. Appl. Meteorol. Climatol. 50(11). (Benchmark only, not used in the pipeline.)
- [Maldonado et al., arXiv 2302.11017](https://ar5iv.labs.arxiv.org/html/2302.11017), DE-LU TSO day-ahead load forecast MAE

The full reference list is on the [paper](https://snowmaking-load-austria.vercel.app).
