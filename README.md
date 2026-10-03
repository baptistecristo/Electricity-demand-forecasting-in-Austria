# TO BE FINISHED: Snowmaking as a hidden load in Austrian day-ahead electricity forecasts

📄 **[Read the paper (PDF)](site/paper.pdf)**

## In short

Austrian ski resorts use about 281 GWh of electricity a season to make artificial
snow, almost all of it on cold November and December nights. While the snow guns
run, that is close to 900 MW, or 8 to 15% of what Austria uses overnight.

I tested whether the grid operator's day-ahead load forecast misses this load.
Heating also rises on cold nights, so I looked for something only snowmaking does:
once the base layer is built the guns stop, so the same cold night should use less
power in late December than in early November.

I wrote down this prediction, and the results that would make me stop, before
opening any load data. The commit history shows the order.

The answer is no. The effect is +5.1 MW, with a standard error of 11.9. The same
test does pick up the Christmas industrial shutdown at −274 MW, so it can see effects
of that size. Italy gives the same result, Switzerland's data could never have shown
it, and Vermont points the predicted way but does not hold up when a different
weather station is used.

## References

- Aigner, Steiger & Mayer (2026). *Snowmaking in Austria: resource consumption and greenhouse gas emissions.* Journal of Sustainable Tourism. [Article](https://www.tandfonline.com/doi/full/10.1080/09669582.2026.2656746) · [PDF](https://zukunft-skisport.at/wp-content/uploads/2025-09-16_IMC-Innsbruck_Snowmaking_Aigner-Steiger-Mayer_final.pdf)
- Olefs, Fischer & Lang (2010). *Boundary conditions for artificial snow production in the Austrian Alps.* J. Appl. Meteorol. Climatol. 49(6). [Article](https://journals.ametsoc.org/view/journals/apme/49/6/2010jamc2251.1.xml)
- Stull (2011). *Wet-bulb temperature from relative humidity and air temperature.* J. Appl. Meteorol. Climatol. 50(11). (Benchmark only, not used in the pipeline.)
- [Maldonado et al., arXiv 2302.11017](https://ar5iv.labs.arxiv.org/html/2302.11017), DE-LU TSO day-ahead load forecast MAE

The full reference list is in the [paper](site/paper.pdf).
