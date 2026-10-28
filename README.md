# Does Austria's electricity forecast miss snowmaking?

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/baptistecristo/Electricity-demand-forecasting-in-Austria/blob/simple/analysis.ipynb)

**Result: to be filled in after the first full run.**

## The question

Every afternoon, Austria's grid operator APG forecasts the next day's electricity use. When the forecast is wrong, someone pays to fill the gap in real time, so for a power trader forecast error is money.

Ski resorts make artificial snow on cold nights, mostly in November and early December. With every snow gun running that is close to 900 MW, about a tenth of what Austria uses at night (Aigner, Steiger & Mayer, 2026). If the forecast left this out, it would be too low on exactly those nights.

## The test

Cold nights also mean more heating, so a forecast that is too low on cold nights would not prove anything by itself. What only snowmaking does is fade: resorts build their snow base in November and have mostly finished by mid-December.

So I compare the forecast error on cold nights (below −2 °C in the mountains) with mild nights, first in **November**, then on **11–20 December**. I stop on 20 December because the Christmas shutdown of industry distorts the forecast from the 21st. If snowmaking were missing from the forecast, the cold-night gap would be much bigger in November than in mid-December. A regression makes the comparison within the same winter and the same weekday, for the 13 winters from 2010 to 2022.

## Data

- **Electricity:** APG's actual load and day-ahead forecast, free to download with no account.
- **Temperature:** hourly air temperature at the highest weather stations in Tyrol and Salzburg (GeoSphere Austria, free API).

The notebook downloads both itself. Open it with the Colab button and click **Runtime → Run all**; it takes about five minutes.

## Limits

- A handful of weather stations stand in for every ski area.
- Snow guns depend on humidity as well as temperature; I use temperature only.
- Some resorts keep making snow in December, which would make the November–December difference smaller and a "no" less convincing.

## Reference

Aigner, Steiger & Mayer (2026). *Snowmaking in Austria: resource consumption and greenhouse gas emissions.* Journal of Sustainable Tourism. [Article](https://www.tandfonline.com/doi/full/10.1080/09669582.2026.2656746)
