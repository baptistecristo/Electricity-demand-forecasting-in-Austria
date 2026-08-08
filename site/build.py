#!/usr/bin/env python3
"""Build the single-file arXiv-style preprint page. Images are inlined as data
URLs so the deployed page has no external dependencies."""
from pathlib import Path
import charts

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "index.html"


FIG_MONTH = charts.figure_month()
FIG_BINS = charts.figure_bins()
FIG_COEFS = charts.figure_coefs()
FIG_MDE = charts.mde_chart()

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Snowmaking and the Austrian Day-Ahead Load Forecast: A Pre-Registered Null</title>
<meta name="description" content="A pre-registered test of whether ski-resort snowmaking is a systematic blind spot in Austria's day-ahead electricity load forecast. 780 nights, 13 seasons. Null.">
<style>
:root {{
  --ink:#1a1a1a; --muted:#5a5a5a; --rule:#d8d4cc; --bg:#fdfdfb;
  --accent:#7a2020; --link:#1a4c8b; --panel:#f5f3ee;
}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"Latin Modern Roman","Computer Modern Serif",Georgia,"Times New Roman",serif;
  font-size:17px; line-height:1.62;
}}
.bar{{
  border-bottom:1px solid var(--rule); background:#fff;
  font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:12px; letter-spacing:.04em; color:var(--muted);
}}
.bar .in{{max-width:52rem;margin:0 auto;padding:.6rem 1.5rem;display:flex;
  justify-content:space-between;gap:1rem;flex-wrap:wrap}}
.bar b{{color:var(--accent);font-weight:600}}
main{{max-width:46rem;margin:0 auto;padding:3rem 1.5rem 6rem}}
h1{{font-size:1.95rem;line-height:1.25;margin:0 0 1.1rem;font-weight:600;
  letter-spacing:-.005em;text-wrap:balance}}
.byline{{margin:0 0 .2rem;font-size:1.02rem}}
.affil{{color:var(--muted);font-size:.9rem;margin:0 0 .3rem;font-style:italic}}
.dateline{{color:var(--muted);font-size:.86rem;margin:0 0 2.2rem;
  font-family:ui-sans-serif,system-ui,sans-serif}}
.abstract{{
  background:var(--panel); border:1px solid var(--rule); border-radius:2px;
  padding:1.3rem 1.6rem; margin:0 0 1rem; font-size:.95rem; line-height:1.6;
}}
.abstract h2{{
  font-size:.78rem;text-transform:uppercase;letter-spacing:.14em;
  margin:0 0 .7rem;color:var(--muted);font-weight:600;
  font-family:ui-sans-serif,system-ui,sans-serif;
}}
.abstract p{{margin:0 0 .7rem;text-align:justify;hyphens:auto}}
.abstract p:last-child{{margin-bottom:0}}
.verdict{{
  border-left:3px solid var(--accent); background:#fff; padding:.9rem 1.2rem;
  margin:0 0 2.4rem; font-size:.94rem;
}}
.verdict strong{{color:var(--accent)}}
h2.sec{{
  font-size:1.15rem;margin:2.6rem 0 .8rem;font-weight:600;
  padding-bottom:.3rem;border-bottom:1px solid var(--rule);
}}
h3{{font-size:1rem;margin:1.8rem 0 .5rem;font-weight:600}}
p{{margin:0 0 1rem;text-align:justify;hyphens:auto}}
ul,ol{{margin:0 0 1rem;padding-left:1.3rem}}
li{{margin:.35rem 0}}
a{{color:var(--link);text-decoration:none;border-bottom:1px solid #c5d4e6}}
a:hover{{border-bottom-color:var(--link)}}
code,.mono{{
  font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  font-size:.86em;background:#f0eee9;padding:.1em .35em;border-radius:2px;
}}
pre{{background:var(--panel);border:1px solid var(--rule);border-radius:2px;
  padding:.9rem 1.1rem;overflow-x:auto;font-size:.8rem;line-height:1.5;margin:0 0 1.2rem}}
pre code{{background:none;padding:0}}
figure{{margin:1.8rem 0;text-align:center}}
figure img{{max-width:100%;height:auto;border:1px solid var(--rule);background:#fff}}
figcaption{{
  font-size:.83rem;color:var(--muted);margin-top:.7rem;text-align:left;
  line-height:1.5;
}}
figcaption b{{color:var(--ink)}}
table{{border-collapse:collapse;width:100%;font-size:.85rem;margin:.4rem 0 .5rem}}
th,td{{padding:.42rem .55rem;border-bottom:1px solid var(--rule);text-align:left;
  vertical-align:top}}
thead th{{border-bottom:1.5px solid #b8b2a8;font-weight:600;font-size:.8rem;
  text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;
  font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.82rem}}
tbody tr.hl{{background:#fbf6f6}}
tbody tr.hl td{{font-weight:600}}
.tcap{{font-size:.83rem;color:var(--muted);margin:.9rem 0 .4rem;line-height:1.5}}
.tcap b{{color:var(--ink)}}
.kill{{list-style:none;padding:0}}
.kill li{{padding:.65rem 0 .65rem 2.1rem;position:relative;border-bottom:1px solid var(--rule);
  font-size:.93rem}}
.kill li:before{{position:absolute;left:0;top:.6rem;font-size:1rem}}
.kill li.fired:before{{content:"✕";color:var(--accent);font-weight:700}}
.kill li.notrun:before{{content:"○";color:var(--muted)}}
.kill li.fired em{{color:var(--accent);font-style:normal;font-weight:600}}
.foot{{margin-top:3.5rem;padding-top:1.2rem;border-top:1px solid var(--rule);
  font-size:.82rem;color:var(--muted)}}
.refs{{font-size:.84rem;line-height:1.55}}
.refs li{{margin:.5rem 0}}
@media (max-width:640px){{
  body{{font-size:16px}} main{{padding:2rem 1.1rem 4rem}} h1{{font-size:1.5rem}}
  table{{font-size:.78rem}} th,td{{padding:.35rem .3rem}}
}}
</style>
</head>
<body>

<div class="bar"><div class="in">
  <span><b>preprint</b> &nbsp;·&nbsp; energy economics / load forecasting</span>
  <span>Pre-registered · data and code open</span>
</div></div>

<main>

<h1>Snowmaking is absorbed by the day-ahead load forecast, not missed by it</h1>
<p class="byline">Baptiste Cristofari</p>
<p class="affil">Independent</p>
<p class="dateline">August 2026 &nbsp;·&nbsp;
  <a href="https://github.com/baptistecristo/Electricity-demand-forecasting-in-Austria">code and data</a>
</p>

<div class="abstract">
<h2>Abstract</h2>
<p>Austrian ski resorts consume roughly 281 GWh of electricity per season making
artificial snow, concentrated into a few hundred cold night hours in November and
December. At realistic fleet coincidence that is 0.6–1.1 GW, or 8–15% of Austria's
overnight demand. Snowmaking is a task rather than a weather response: it runs only
below a wet-bulb threshold near −2 °C, it stops once the base layer is built, and it
is front-loaded before opening day. Two identical cold nights therefore draw very
different amounts of power depending on how much snow has already been made.</p>
<p>This paper pre-registers and tests whether that path dependence appears as a
state-dependent error in the published day-ahead load forecast. Using thirteen
seasons of Austrian Power Grid data (113,939 hourly observations, 2010–2022) joined
to a pressure-corrected wet-bulb index built from thirteen alpine stations between
1,221 and 2,327 m, the interaction between the threshold and season-to-date
accumulated cold is <b>+5.1 MW (s.e. 11.9)</b> across 780 November–December nights.
Campaign-start effects are likewise zero. The identical specification on the identical
nights recovers the Christmas industrial shutdown at <b>−274 MW (t = −3.3)</b>, so the
design detects effects of the size snowmaking would have to produce.</p>
<p>The load is not invisible to the forecast; it is absorbed by it. A temperature
coefficient fitted on thirteen years in which cold alpine nights <em>are</em>
snowmaking nights prices in the average response without modelling snowmaking, and
the operator's use of lagged actual load carries a running campaign into the next
day's forecast. Two of three pre-registered kill criteria fired.</p>
</div>

<div class="verdict">
<strong>Result:</strong> null, pre-registered, and not underpowered. Austria is
also close to the best test case in the world by snowmaking-to-system-load ratio,
which makes the null informative rather than a consequence of a poor choice of market.
</div>

<h2 class="sec">1. The question</h2>
<p>Transmission system operators publish a day-ahead load forecast, and both the
forecast and the realised load are free. The difference is the forecast error. If
snowmaking is genuinely invisible to the forecasting model, the error should be
positive on nights when snowmaking runs, and the size of the miss should depend on
the state of the snowpack rather than on temperature alone.</p>
<p>The interest is not the ski industry. It is whether a large, physically lumpy,
path-dependent industrial load can hide inside a production forecast — a structure
that recurs in Spanish irrigation pumping and North American grain drying.</p>

<h2 class="sec">2. How big is the load</h2>
<p>From a 2026 survey of 141 Austrian resorts (30 usable, 4,253 equipped hectares,
34.0% of Austrian ski volume), extrapolated nationally:</p>

<table>
<thead><tr><th>Quantity</th><th class="num">Value</th></tr></thead>
<tbody>
<tr><td>Season electricity, Austria-wide</td><td class="num">281 GWh (260–309)</td></tr>
<tr><td>Share of Austrian electricity consumption</td><td class="num">0.46%</td></tr>
<tr><td>Mean operating hours per snowmaker per season</td><td class="num">184.6 h</td></tr>
<tr><td>Snowmakers per hectare</td><td class="num">2.9</td></tr>
<tr><td>Energy per hectare equipped</td><td class="num">22,449 kWh</td></tr>
<tr><td>Energy per m³ of snow</td><td class="num">3.3 kWh</td></tr>
</tbody></table>
<p class="tcap"><b>Table 1.</b> Published snowmaking figures used throughout.</p>

<p>Instantaneous power follows from energy over operating hours. The fleet-wide
coincident ceiling is 281 GWh ÷ 184.6 h = <b>1.52 GW</b>, implying a mean draw of
41.9 kW per snowmaker while running, which is consistent with a lance and fan-gun mix
plus pumping and compressed air. At 40–70% coincidence the national draw is
0.61–1.07 GW. Austrian weekday overnight load in November and December runs
7.0–7.5 GW, so snowmaking is <b>8–15% of overnight demand</b>.</p>

<h2 class="sec">3. Why a forecast might miss it — and why it might not</h2>
<p>The naive version of the hypothesis is that load forecasts are temperature models
and temperature models have no memory. Two mechanisms argue against it, and both were
written down before the data was opened.</p>
<p><b>A memoryless model still absorbs the average response.</b> The temperature
coefficient is estimated on history in which cold nights are snowmaking nights. The
model need not know snowmaking exists to price it in on average. What remains in the
residual is the deviation from the conditional mean given temperature — the snowmaking
anomaly, not the snowmaking load.</p>
<p><b>Production forecasts are autoregressive.</b> APG publishes at 08:00 for the
following day and lists its inputs as historical actual load, day type including the
holiday calendar, and temperature forecast. Yesterday's actual is already in there, so
any lagged-load term propagates a running campaign into tomorrow's forecast.</p>
<p>Write α for the share of snowmaking load the forecast leaves unexplained. Both
mechanisms push α down, and α turns out to be the binding constraint on the entire
design.</p>

<h2 class="sec">4. Identification</h2>
<p>The obvious test — comparing nights just below the wet-bulb threshold to nights
just above — is contaminated. At 1,800 m, −2 °C wet bulb corresponds to roughly −1 to
0 °C air temperature, and every nonlinearity in heating load lives near freezing:
heat-pump COP collapse and resistive backup cutover, defrost cycles, pipe and road
trace heating. Humidity, which enters wet bulb, is itself a load driver.</p>
<p>The identifying variation is therefore not the threshold crossing but its
interaction with accumulated season-to-date cold:</p>
<pre><code>err ~ below × cum_cold_hours
      + dist + below:dist + holiday
      + doy + doy² + season FE + dow FE

err            = actual load − day-ahead forecast, MW
below          = 1 if alpine wet-bulb index &lt; −2 °C
dist           = wb_index − (−2)
cum_cold_hours = hours below threshold since 1 Oct, current season</code></pre>
<p>Heating load does not care how many cold hours the season has already delivered.
Snowmaking does, because the base gets built and the guns stop. The interaction is the
only coefficient in this design a temperature confound cannot produce.</p>

<h3>4.1 Building the wet-bulb index</h3>
<p>Three choices decide the answer before the econometrics do. Stations are selected
by <b>altitude band</b> (900–2,600 m), because valley stations cross the threshold
hundreds of hours later than the places snow is actually made. Wet bulb is corrected
for <b>station pressure</b> — ISA pressure at 1,800 m is 815 hPa, and assuming sea
level shifts wet bulb by 0.2–0.4 °C, comparable to the regression bandwidth. And the
psychrometric equation is <b>solved</b> rather than approximated: the Stull (2011)
closed form errs by 0.7–1.0 °C below freezing, worse than the effect being tested.
Regions are weighted by state share of Austrian skier visits.</p>
<p>The resulting index draws on Ischgl-Idalpe (2,327 m), Rudolfshütte (2,317 m),
Patscherkofel (2,251 m), Villacher Alpe (2,140 m), Galzig (2,079 m) and
Schmittenhöhe (1,956 m), among thirteen stations in total.</p>

<h2 class="sec">5. Pre-registration</h2>
<p><b>Primary prediction.</b> The <code>below × cum_cold_hours</code> coefficient is
negative and significant at 5%.</p>
<p><b>Supporting predictions.</b> The error spikes on the first night of a cold snap
and decays over 24–48 hours as autoregressive terms catch up; the effect is smaller
after resorts open, conditional on wet bulb and day of season; and the Netherlands and
Denmark, run through the identical pipeline, show nothing.</p>
<p><b>Kill criteria, committed before looking:</b></p>
<ul class="kill">
<li class="fired">The interaction is zero or positive with a tight confidence interval → no memory effect. Stop. <em>— fired</em></li>
<li class="fired">The event-study profile is flat across campaign days → the forecast already absorbs it. Stop. <em>— fired</em></li>
<li class="notrun">A cold, flat placebo country shows the same jump → the result is heating load. Stop. <em>— not run; moot once the first two fired</em></li>
</ul>
<p>All outcomes were committed to publication in advance. A null was named as the
modal outcome.</p>

<h2 class="sec">6. Statistical power</h2>
<figure>
{FIG_MDE}
<figcaption><b>Figure 1.</b> Minimum detectable effect against seasons of data, for
three assumptions about day-ahead forecast error, with the plausible residual signal
overlaid. The pass mark is how much of the ~900 MW snowmaking load the forecast must
leave unexplained. Additional seasons move it very little; α is the binding
constraint.</figcaption>
</figure>
<p>Measured on the actual data, the Austrian day-ahead forecast turned out
substantially noisier than the German-Luxembourg benchmark of 3.14% used to
calibrate this: <b>6.48% MAE</b> on November–December night hours, standard deviation
608 MW raw and 554 MW after fixed effects. That raised the pass mark to
<b>α ≥ 27.4%</b> at thirteen seasons.</p>

<h2 class="sec">7. Results</h2>
<figure>
{FIG_MONTH}
<figcaption><b>Figure 2.</b> Night forecast error by month, 2010–2022, night-level
observations. November is the most under-forecast month of the year at
+131 ± 22 MW. Bars are ±1 s.e.</figcaption>
</figure>

<figure>
{FIG_BINS}
<figcaption><b>Figure 3.</b> The same error in 10-day bins across November and
December. The bias climbs to +223 ± 41 MW in early December and then collapses at
the Christmas industrial shutdown. This is the shape, magnitude and timing snowmaking
would produce — and also what a seasonal heating ramp produces.</figcaption>
</figure>

<p>The unconditional seasonal profile was encouraging. November is the most
under-forecast month of the year, and within November–December the bias climbs to
+223 ± 41 MW in early December before collapsing at Christmas. That is the right
shape, magnitude and timing for snowmaking: too warm to make snow in early November,
a ramp into the opening-day crunch, decline as bases are built. It is also exactly
what a seasonal heating ramp produces.</p>

<p>Conditional on weather, it vanishes.</p>

<figure>
{FIG_COEFS}
<figcaption><b>Figure 4.</b> Coefficients from the primary specification with 95%
intervals. The pre-registered interaction sits on zero. The same model, on the same
nights, places the Christmas shutdown at −274 MW — so the design is not blind to
effects of the size snowmaking would have to produce.</figcaption>
</figure>

<table>
<thead><tr>
  <th>Specification</th><th class="num">n</th>
  <th class="num">below × cum100</th><th class="num">below</th><th class="num">holiday</th>
</tr></thead>
<tbody>
<tr class="hl"><td>Nov–Dec, all nights</td><td class="num">780</td>
  <td class="num">+5.1 (11.9)</td><td class="num">+27.2 (53.2)</td><td class="num">−273.6 (84.0)</td></tr>
<tr><td>Bandwidth |wb+2| ≤ 3 °C</td><td class="num">418</td>
  <td class="num">+4.2 (14.7)</td><td class="num">+39.8 (83.1)</td><td class="num">−210.0 (121.2)</td></tr>
<tr><td>With campaign-start dummies</td><td class="num">780</td>
  <td class="num">+5.4 (12.0)</td><td class="num">+23.1 (55.1)</td><td class="num">−273.7 (84.0)</td></tr>
<tr><td>Seasons 2016–2022 only</td><td class="num">420</td>
  <td class="num">−7.9 (11.5)</td><td class="num">−3.3 (49.5)</td><td class="num">−372.0 (92.7)</td></tr>
</tbody></table>
<p class="tcap"><b>Table 2.</b> Coefficients in MW, HC1 standard errors in
parentheses, night-level observations. The primary coefficient is zero in every
specification. The holiday control is strongly significant in every specification.</p>

<table>
<thead><tr><th>Campaign-start terms</th><th class="num">Coef.</th><th class="num">s.e.</th><th class="num">t</th></tr></thead>
<tbody>
<tr><td>First night of a cold snap</td><td class="num">+6.3</td><td class="num">58.6</td><td class="num">0.11</td></tr>
<tr><td>Second night</td><td class="num">−91.7</td><td class="num">86.7</td><td class="num">−1.06</td></tr>
</tbody></table>
<p class="tcap"><b>Table 3.</b> The scenario where α should be highest, because
autoregressive terms have not yet caught up. Both dummies enter the same
specification. Zero, and the first night carries the wrong sign.</p>

<h3>7.1 Why this is a null rather than an absence of evidence</h3>
<p>The specification is not underpowered for effects of the relevant size. On the same
780 nights, with the same fixed effects and the same standard errors, it recovers the
Christmas industrial shutdown at −274 MW with t = −3.3, rising to −372 MW and
t = −4.0 in recent seasons. A real night-level swing of a few hundred megawatts is
visible to this design. The snowmaking interaction is +5 ± 12.</p>
<p>The most likely explanation is the one anticipated in §3. The +131 MW November
bias survives as a real seasonal feature; it is simply not attributable to snowmaking
by this design.</p>

<h3>7.2 The opening-date test cannot be identified from calendar dates</h3>
<p>Austrian opening dates are tightly clustered — glaciers from late September at
3–5% of equipped capacity, Obergurgl 16 November, Ischgl 25 November, St Anton
1 December, the bulk of the country between 8 and 20 December. Encoding that as a
capacity-open share and interacting it with the threshold gives −301.8 (s.e. 266.6).
The sign is the predicted one and the precision is useless, for a mechanical reason:
regressing the opening curve on the day-of-season controls already in the
specification gives <b>R² = 0.798</b>. A fixed calendar curve is four-fifths
explained by a smooth function of the date.</p>
<p>Identifying it requires season-varying opening dates — resorts open late in bad
snow years and early in good ones, and that variation is orthogonal to the calendar.
This pre-registered test is closed as <em>not identifiable with the data collected</em>,
which is a different statement from tested and null.</p>
<p class="tcap">The two coefficients in this subsection are the only numbers on this
page that the published pipeline does not regenerate: they need per-resort opening
dates, which are not in the repository. They still carry the timezone error described
in 7.3.</p>

<h3>7.3 Correction</h3>
<p>The numbers first published here were computed in a browser JavaScript context,
because the machine that ran the analysis had no route to APG or GeoSphere.
<code>src/apg_pipeline.py</code> is the portable Python reimplementation, and nobody
had run it start to finish until now. Doing so found four defects, and the figures
and tables above report the corrected output.</p>
<p>GeoSphere stamps its timestamps UTC while APG publishes local CET/CEST wall clock,
and both runs joined them on the raw hour string, so every load hour drew the wet bulb
of the following local hour. Correcting it moves the primary interaction from
+1.3 (11.8) to +5.1 (11.9), which is still indistinguishable from zero and still
wrong-signed against the prediction. The season-to-date cold accumulator had also been
built after the night filter, halving it and inflating every coefficient attached to it
by a factor near 2.05. Austria's daylight-saving hour, which APG writes as
<code>2A</code> and <code>2B</code>, crashed the parser outright. And the gate
statistics in section 6 had been measured on a 21:00–05:59 night rather than the
registered 20:00–06:59 one, which is where the earlier 6.50% MAE came from.</p>
<p>None of it changes the verdict. The pre-registration, the kill criteria and the
power calculation are unchanged.</p>

<h2 class="sec">8. Was Austria a badly chosen case?</h2>
<p>A null is only interesting if the test was fair. Ranking systems by snowmaking
energy per gigawatt of winter overnight load puts Austria near the top of the world.</p>
<div class="verdict" style="margin:0 0 1.4rem"><strong>Scope note:</strong> no country
other than Austria was analysed. This section is desk scoping — published or derived
snowmaking energy divided by published system load. No load series, forecast series or
regression was run for any other system. These are targets for replication, not
results.</div>

<table>
<thead><tr><th>System</th><th class="num">GWh/season</th><th class="num">O/n load (GW)</th>
  <th class="num">Ratio</th><th>Free forecast?</th></tr></thead>
<tbody>
<tr><td>ISO-NE Vermont region</td><td class="num">40–90*</td><td class="num">~0.65</td>
  <td class="num">62–140</td><td>Yes, per region</td></tr>
<tr><td>Italy-North</td><td class="num">~560*</td><td class="num">~12–13</td>
  <td class="num">~45</td><td>Yes, Terna</td></tr>
<tr class="hl"><td>Austria (this study)</td><td class="num">281</td><td class="num">~7</td>
  <td class="num">43</td><td>Yes</td></tr>
<tr><td>ISO-NE New Hampshire</td><td class="num">22–54*</td><td class="num">~1.25</td>
  <td class="num">18–43</td><td>Yes</td></tr>
<tr><td>PSCO (Colorado)</td><td class="num">45–70*</td><td class="num">~4</td>
  <td class="num">11–18</td><td>Yes, EIA-930</td></tr>
<tr><td>Switzerland</td><td class="num">60–65</td><td class="num">~8.4</td>
  <td class="num">7.1–7.7</td><td>Yes, Swissgrid</td></tr>
<tr><td>France</td><td class="num">&gt;110</td><td class="num">~60</td>
  <td class="num">1.8</td><td>Yes, ODRÉ</td></tr>
<tr><td>Germany</td><td class="num">≤43†</td><td class="num">~52</td>
  <td class="num">≤0.8</td><td>Yes, SMARD</td></tr>
</tbody></table>
<p class="tcap"><b>Table 4.</b> Worldwide ranking. *Derived by scaling equipped
hectares at the Austrian intensity of 22,449 kWh/ha; no published national total
exists outside Austria, Switzerland and France. †Germany's figure covers lifts and
snowmaking together.</p>

<p>Only two systems plausibly beat Austria, and one is a sub-region rather than a
country. Switzerland is six times worse, France twenty-four, Germany fifty. This is
not the null of a badly chosen case.</p>
<p><b>The best remaining test is Vermont.</b> ISO-NE publishes an hourly demand
forecast per reliability region, and Vermont's ~0.65 GW zonal load sits under a
snowmaking fleet covering close to 100% of trail acreage, because Northeast resorts
snowmake far harder than the Alps where natural snowfall is unreliable. Resort-level
derivations put Northeast intensity at 3–7× the Austrian figure. Rhode Island gives a
same-forecaster, same-weather, zero-snowmaking placebo inside the same feed. One
caveat has to be resolved first: ISO-NE's regional report may allocate a system
forecast to regions by load-share factors rather than forecasting each region
independently, in which case a positive result would mean "no regional model" rather
than "snowmaking is missed."</p>
<p><b>Andorra has the best physics on earth and no data.</b> Snowmaking at Grandvalira
and Pal Arinsal against a 570 GWh national system is plausibly a several-percent share
of national load, but FEDA sits outside ENTSO-E and publishes no hourly series. The
same holds for China's Chongli cluster.</p>

<h2 class="sec">9. Limitations</h2>
<ul>
<li>Roughly 360 relevant hours per season, heavily autocorrelated. Effective sample
size is nights, not hours, which is why estimation is at night level.</li>
<li>The published forecast is the operator's transparency artefact, not the trading
consensus. A bias in it demonstrates a blind spot in APG's forecast, <b>not</b> a
market mispricing. Establishing the latter needs day-ahead price or imbalance as the
outcome.</li>
<li>APG's published load excludes a corridor in Vorarlberg, which carries weight 0.10
in the wet-bulb index while some of its load is absent from the dependent variable.</li>
<li>The index is weighted by state share of skier visits, not equipped hectares.</li>
<li><code>cum_cold_hours</code> proxies snow stock by accumulated hours below
threshold. It ignores melt and counts cold hours whether or not guns actually ran.</li>
<li>The opening-date and placebo tests were not identified and not run respectively.</li>
</ul>

<h2 class="sec">10. Data and reproduction</h2>
<p>No API token is required. Austrian Power Grid publishes both load series back to
2009 as nested per-year ZIP archives with no registration, and GeoSphere Austria's
station API needs no key. A single script reproduces everything:</p>
<pre><code>git clone https://github.com/baptistecristo/Electricity-demand-forecasting-in-Austria
pip install -r requirements.txt
python src/apg_pipeline.py</code></pre>
<p>For cross-country work, energy-charts.info (Fraunhofer ISE) serves day-ahead load
forecast, actual load and day-ahead spot price for most European bidding zones with no
token. Electricity <em>futures</em> settlement history is paywalled at EEX and ICE, so
a futures-lag test is not feasible on free data; day-ahead spot is the honest
substitute.</p>

<h2 class="sec">References</h2>
<ol class="refs">
<li>Aigner, Steiger &amp; Mayer (2026). Snowmaking in Austria: resource consumption and
greenhouse gas emissions. <em>Journal of Sustainable Tourism</em>.
<a href="https://ciss-journal.org/article/view/11546">figures</a></li>
<li>Olefs, Fischer &amp; Lang (2010). Boundary conditions for artificial snow production
in the Austrian Alps. <em>J. Appl. Meteorol. Climatol.</em> 49(6).
<a href="https://journals.ametsoc.org/view/journals/apme/49/6/2010jamc2251.1.xml">link</a></li>
<li>Stull (2011). Wet-bulb temperature from relative humidity and air temperature.
<em>J. Appl. Meteorol. Climatol.</em> 50(11). Used as a benchmark, not in the pipeline.</li>
<li>Austrian Power Grid. <a href="https://markt.apg.at/en/transparency/load/actual-total-load/">Actual total load</a>
and <a href="https://markt.apg.at/en/transparency/load/total-load-forecast/">total load forecast</a>.</li>
<li>GeoSphere Austria. <a href="https://dataset.api.hub.geosphere.at/v1/docs/">Dataset API</a>.</li>
<li>Maldonado et al. <a href="https://ar5iv.labs.arxiv.org/html/2302.11017">arXiv:2302.11017</a>
— DE-LU day-ahead load forecast MAE.</li>
<li>ISO New England. <a href="https://www.iso-ne.com/isoexpress/web/reports/load-and-demand/-/tree/three-day-reliability-region-demand-forecast">Three-day reliability region demand forecast</a>.</li>
<li>Fraunhofer ISE. <a href="https://api.energy-charts.info/">energy-charts API</a>.</li>
</ol>

<div class="foot">
<p>Pre-registration and results are separate commits in the repository; the commit
history establishes that the stopping rules predate the data. Code and figures are
MIT-licensed.</p>
<p><a href="https://github.com/baptistecristo/Electricity-demand-forecasting-in-Austria">github.com/baptistecristo/Electricity-demand-forecasting-in-Austria</a></p>
</div>

</main>
</body>
</html>
"""

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT}  ({len(HTML)/1024:.0f} KB)")
