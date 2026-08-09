#!/usr/bin/env python3
"""Build the single-file arXiv-style preprint page. Images are inlined as data
URLs so the deployed page has no external dependencies."""
import re
from pathlib import Path
import charts

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
OUT = HERE / "index.html"
FIG = HERE / "fig"


def _widget(name: str) -> str:
    """The figure body from one `Rscript site/charts.R` output.

    saveWidget writes a whole HTML document per figure, each pointing at its own
    copy of the ggiraph runtime. Only the widget div and its JSON payload are
    kept here; the runtime is inlined once for the page by _viz_assets(), so
    four figures cost one library rather than four.
    """
    html = (FIG / f"{name}.html").read_text(encoding="utf-8")
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S).group(1)
    return re.sub(r'<script src="[^"]*"></script>', "", body).strip()


def _viz_assets() -> tuple[str, str]:
    """ggiraph's CSS and JS, inlined so the page still makes no request.

    Read from site/fig/lib, which holds the four files this page actually needs,
    copied once. The rest of what saveWidget emits is not kept: ggiraph bundles
    ~19 MB of Liberation fonts per figure, and ships girafe.js twice under two
    names (the two copies are byte-identical). The SVG falls back to the page's
    own font stack, which is what it should be using anyway.

    Refresh site/fig/lib by hand if ggiraph is ever upgraded.
    """
    css = "\n".join((FIG / "lib" / p).read_text(encoding="utf-8")
                    for p in ("fill.css", "girafe.css"))
    js = ";\n".join((FIG / "lib" / p).read_text(encoding="utf-8",
                                                errors="replace")
                    for p in ("htmlwidgets.js", "girafe.js"))
    return css, js


VIZ_CSS, VIZ_JS = _viz_assets()
FIG_MONTH = _widget("month")
FIG_BINS = _widget("bins")
FIG_COEFS = _widget("coefs")
FIG_MDE = _widget("mde")

# Every figure ships a table view, so nothing has to be read off colour alone.
TABLE_MONTH = charts.table_month()
TABLE_BINS = charts.table_bins()
TABLE_COEFS = charts.table_coefs()

# Applied before first paint so a stored dark preference does not flash white.
HEAD_SCRIPT = (
    "<script>try{var s=localStorage.getItem('snowtheme');"
    "if(s)document.documentElement.setAttribute('data-theme',s);}catch(e){}</script>"
)

# Kept out of the f-string below: JavaScript braces would all need doubling.
SCRIPT = r"""<script>
(function () {
  var root = document.documentElement, KEY = 'snowtheme';
  function current() {
    var set = root.getAttribute('data-theme');
    if (set) return set;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  var themeBtn = document.getElementById('themebtn');
  themeBtn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
    themeBtn.setAttribute('aria-label',
      next === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  });

  var navBtn = document.getElementById('navbtn');
  navBtn.addEventListener('click', function () {
    var open = document.body.classList.toggle('nav-open');
    navBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  Array.prototype.forEach.call(document.querySelectorAll('.idx a'), function (a) {
    a.addEventListener('click', function () {
      document.body.classList.remove('nav-open');
      navBtn.setAttribute('aria-expanded', 'false');
    });
  });
})();
</script>"""

MOON = ('<svg class="moon" viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>')
SUN = ('<svg class="sun" viewBox="0 0 24 24" aria-hidden="true">'
       '<circle cx="12" cy="12" r="4.2"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2'
       'M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></svg>')
BARS = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M4 7h16M4 12h16M4 17h16"/></svg>')

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Snowmaking and the Austrian Day-Ahead Load Forecast: A Pre-Registered Null</title>
<meta name="description" content="A pre-registered test of whether ski-resort snowmaking is a systematic blind spot in Austria's day-ahead electricity load forecast. 780 nights, 13 seasons. Null.">
{HEAD_SCRIPT}
<style>
:root {{
  --bg:#ffffff; --fg:#0a0a0a; --muted:#737373; --rule:#e5e5e5;
  --accent:#0079F2; --accent-line:rgba(0,121,242,.18);
  --panel:rgba(0,121,242,.035); --code-bg:#f4f4f5; --hl:rgba(0,121,242,.05);
  --c-blue:#2b6cb0; --c-red:#c05621; --c-green:#276749; --c-grey:#9a9a9a;
  --c-plum:#702459;
  --serif:'Crimson Pro',Georgia,'Times New Roman',serif;
  --sans:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
}}
:root[data-theme="dark"]{{
  --bg:#0a0a0a; --fg:#e5e5e5; --muted:#a3a3a3; --rule:#404040;
  --accent:#3b9eff; --accent-line:rgba(59,158,255,.32);
  --panel:rgba(59,158,255,.07); --code-bg:rgba(255,255,255,.07);
  --hl:rgba(59,158,255,.09);
  --c-blue:#5aa9f0; --c-red:#ee8a4d; --c-green:#4bb07a; --c-grey:#8a8a8a;
  --c-plum:#d571a6;
}}
@media (prefers-color-scheme:dark){{
  :root:not([data-theme="light"]){{
    --bg:#0a0a0a; --fg:#e5e5e5; --muted:#a3a3a3; --rule:#404040;
    --accent:#3b9eff; --accent-line:rgba(59,158,255,.32);
    --panel:rgba(59,158,255,.07); --code-bg:rgba(255,255,255,.07);
    --hl:rgba(59,158,255,.09);
    --c-blue:#5aa9f0; --c-red:#ee8a4d; --c-green:#4bb07a; --c-grey:#8a8a8a;
    --c-plum:#d571a6;
  }}
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{-webkit-text-size-adjust:100%;scroll-behavior:smooth}}
body{{
  background:var(--bg); color:var(--fg); font-family:var(--serif);
  font-size:1.1875rem; line-height:1.8;
  -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale;
}}
:focus-visible{{outline:2px solid var(--accent);outline-offset:3px;border-radius:2px}}

/* ---- sidebar index ---- */
aside{{
  position:fixed; top:0; left:0; height:100vh; width:20rem; z-index:30;
  padding:3rem 2rem; overflow-y:auto; border-right:1px solid var(--rule);
  background:var(--bg);
}}
.idx-eyebrow{{
  font-family:var(--sans); font-size:.72rem; font-weight:600;
  letter-spacing:.18em; text-transform:uppercase; color:var(--muted);
  margin-bottom:2rem;
}}
.idx{{list-style:none}}
.idx li{{margin:0 0 .1rem}}
.idx a{{
  display:flex; gap:1rem; align-items:baseline; text-decoration:none;
  color:var(--muted); font-size:.95rem; line-height:1.45; padding:.42rem 0;
  border:0; transition:color .15s;
}}
.idx a:hover,.idx a:focus-visible{{color:var(--fg)}}
.idx .n{{
  font-family:var(--sans); font-size:.72rem; font-variant-numeric:tabular-nums;
  color:var(--muted); opacity:.7; flex-shrink:0; letter-spacing:.04em;
}}
.idx .grp{{
  font-family:var(--sans); font-size:.68rem; font-weight:600;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted);
  margin:2rem 0 .8rem; opacity:.75;
}}

/* ---- theme toggle ---- */
.toggle{{
  position:fixed; top:1.6rem; right:2rem; z-index:40;
  background:var(--bg); border:1px solid var(--rule); border-radius:999px;
  width:2.5rem; height:2.5rem; display:grid; place-items:center;
  cursor:pointer; color:var(--muted); transition:color .15s,border-color .15s;
}}
.toggle:hover{{color:var(--fg);border-color:var(--muted)}}
.toggle svg{{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.6}}
.toggle .sun{{display:none}}
:root[data-theme="dark"] .toggle .sun{{display:block}}
:root[data-theme="dark"] .toggle .moon{{display:none}}
@media (prefers-color-scheme:dark){{
  :root:not([data-theme="light"]) .toggle .sun{{display:block}}
  :root:not([data-theme="light"]) .toggle .moon{{display:none}}
}}

/* ---- layout ---- */
main{{margin-left:20rem;padding-bottom:6rem}}
.container{{max-width:48rem;margin:0 auto;padding:0 4rem}}

/* ---- masthead ---- */
.masthead{{padding:6rem 0 3rem}}
.kicker{{
  font-family:var(--sans); font-size:.8rem; font-weight:500;
  letter-spacing:.15em; text-transform:uppercase; color:var(--accent);
  margin-bottom:1.6rem;
}}
h1{{
  font-size:3.4rem; line-height:1.1; font-weight:400; letter-spacing:-.01em;
  text-wrap:balance; margin-bottom:1.4rem;
}}
.byline{{font-size:1.05rem;margin-bottom:.15rem}}
.affil{{color:var(--muted);font-size:.95rem;font-style:italic;margin-bottom:.5rem}}
.dateline{{
  font-family:var(--sans); font-size:.85rem; color:var(--muted);
  letter-spacing:.025em; padding-bottom:2.5rem; border-bottom:1px solid var(--rule);
}}

/* ---- the one-minute read ---- */
.tldr{{margin:2.5rem 0 1rem;padding-bottom:2.5rem;
  border-bottom:1px solid var(--rule)}}
.tldr-label{{font-family:var(--sans);font-size:.78rem;font-weight:600;
  letter-spacing:.16em;text-transform:uppercase;color:var(--accent);
  margin-bottom:1.4rem}}
.tldr p{{font-size:1.22rem;line-height:1.72;margin-bottom:1.05rem}}
.tldr p b{{font-weight:600}}
.tldr .lead{{font-family:var(--sans);font-size:.82rem;font-weight:600;
  letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  display:block;margin-bottom:.2rem}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1.6rem;
  margin:2.2rem 0 1.6rem;padding:1.5rem 0;
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}}
.stat .v{{font-size:1.85rem;line-height:1.1;font-weight:400;
  font-variant-numeric:tabular-nums;display:block}}
.stat .k{{font-family:var(--sans);font-size:.74rem;line-height:1.45;
  color:var(--muted);display:block;margin-top:.5rem}}
.stat.key .v{{color:var(--accent)}}
.more{{font-family:var(--sans);font-size:.85rem;color:var(--muted);
  margin-top:1.6rem}}
@media (max-width:640px){{
  .stats{{grid-template-columns:repeat(2,1fr);gap:1.3rem}}
  .tldr p{{font-size:1.1rem}}
  .stat .v{{font-size:1.5rem}}
}}

/* ---- abstract + verdict ---- */
.abstract{{margin:2.5rem 0 1.5rem}}
.abstract h2{{
  font-family:var(--sans); font-size:.78rem; font-weight:600;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted);
  margin-bottom:1rem;
}}
.abstract p{{margin-bottom:1rem;opacity:.9}}
.abstract p:last-child{{margin-bottom:0}}
.verdict{{
  background:var(--panel); border:1px solid var(--accent-line); border-radius:8px;
  padding:1.6rem 1.8rem; margin:2rem 0 3rem;
  font-family:var(--sans); font-size:.95rem; line-height:1.65;
}}
.verdict strong{{color:var(--accent);font-weight:600}}

/* ---- sections ---- */
article{{margin-bottom:5rem}}
.chapter-label{{
  font-family:var(--sans); font-size:.82rem; font-weight:500;
  letter-spacing:.15em; text-transform:uppercase; color:var(--accent);
  opacity:.85; display:block; margin-bottom:.9rem;
}}
h2.sec{{font-size:2.6rem;line-height:1.15;font-weight:400;margin-bottom:1.8rem;
  letter-spacing:-.01em;text-wrap:balance}}
h3{{font-size:1.4rem;line-height:1.3;font-weight:600;margin:2.8rem 0 1.1rem}}
p{{margin-bottom:1.15rem}}
ul,ol{{margin:0 0 1.2rem;padding-left:1.4rem}}
li{{margin:.45rem 0}}
a{{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent-line)}}
a:hover{{border-bottom-color:var(--accent)}}
code,.mono{{
  font-family:var(--mono); font-size:.84em; background:var(--code-bg);
  padding:.12em .38em; border-radius:4px;
}}
pre{{background:var(--code-bg);border:1px solid var(--rule);border-radius:8px;
  padding:1.1rem 1.3rem;overflow-x:auto;font-size:.82rem;line-height:1.6;
  margin-bottom:1.4rem;font-family:var(--mono)}}
pre code{{background:none;padding:0}}

/* ---- figures ---- */
figure{{margin:2.4rem 0}}
figure svg{{display:block;margin:0 auto;max-width:100%;height:auto}}
figure img{{max-width:100%;height:auto;border:1px solid var(--rule);border-radius:8px}}
figcaption{{
  font-family:var(--sans); font-size:.82rem; color:var(--muted);
  margin-top:1rem; line-height:1.6;
}}
figcaption b{{color:var(--fg);font-weight:600}}

/* ---- tables ---- */
.twrap{{overflow-x:auto;margin:1rem 0 .5rem}}
table{{border-collapse:collapse;width:100%;font-family:var(--sans);font-size:.86rem}}
th,td{{padding:.6rem .7rem;border-bottom:1px solid var(--rule);text-align:left;
  vertical-align:top;line-height:1.5}}
thead th{{
  border-bottom:1px solid var(--muted); font-weight:600; font-size:.72rem;
  text-transform:uppercase; letter-spacing:.09em; color:var(--muted);
}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
tbody tr.hl{{background:var(--hl)}}
tbody tr.hl td{{font-weight:600}}
.tcap{{font-family:var(--sans);font-size:.82rem;color:var(--muted);
  margin:1rem 0 .4rem;line-height:1.6}}
.tcap b{{color:var(--fg);font-weight:600}}

/* ---- kill criteria ---- */
.kill{{list-style:none;padding:0}}
.kill li{{padding:.8rem 0 .8rem 2.2rem;position:relative;
  border-bottom:1px solid var(--rule);font-size:1.02rem}}
.kill li:before{{position:absolute;left:0;top:.85rem;font-size:1rem;
  font-family:var(--sans)}}
.kill li.fired:before{{content:"✕";color:var(--accent);font-weight:700}}
.kill li.notrun:before{{content:"○";color:var(--muted)}}
.kill li.fired em{{color:var(--accent);font-style:normal;font-weight:600}}

/* ---- footer ---- */
.foot{{margin-top:4rem;padding-top:1.6rem;border-top:1px solid var(--rule);
  font-family:var(--sans);font-size:.82rem;color:var(--muted);line-height:1.7}}
.foot p{{margin-bottom:.7rem}}
.refs{{font-size:.92rem;line-height:1.6}}
.refs li{{margin:.6rem 0}}

/* ---- mobile ---- */
.navbtn{{display:none;position:fixed;top:1.6rem;left:1.25rem;z-index:40;
  background:var(--bg);border:1px solid var(--rule);border-radius:999px;
  width:2.5rem;height:2.5rem;place-items:center;cursor:pointer;color:var(--muted)}}
.navbtn svg{{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.7}}
@media (max-width:1100px){{
  aside{{transform:translateX(-100%);transition:transform .25s ease;
    box-shadow:0 0 40px rgba(0,0,0,.18);
    padding-top:5.6rem}}   /* clear the fixed menu button */
  body.nav-open aside{{transform:none}}
  .navbtn{{display:grid}}
  main{{margin-left:0}}
  .container{{padding:0 1.6rem}}
  .masthead{{padding:5rem 0 2.5rem}}
}}
@media (max-width:640px){{
  body{{font-size:1.06rem;line-height:1.75}}
  h1{{font-size:2.2rem}} h2.sec{{font-size:1.75rem}} h3{{font-size:1.2rem}}
  .container{{padding:0 1.15rem}}
  .toggle{{right:1.25rem}}
  .verdict{{padding:1.2rem 1.3rem}}
}}
@media (prefers-reduced-motion:reduce){{
  html{{scroll-behavior:auto}}
  *{{transition:none!important;animation:none!important}}
}}

/* ---- R / ggiraph figures ---- */
.girafe_container_std{{width:100%!important;margin:0 auto}}
.girafe_container_std svg{{width:100%!important;height:auto!important}}
.dtable{{margin:.6rem 0 0}}
.dtable summary{{font-family:var(--sans);font-size:.8rem;color:var(--muted);
  cursor:pointer;padding:.35rem 0}}
.dtable summary:hover{{color:var(--fg)}}
.dtable[open] summary{{margin-bottom:.5rem}}
</style>
<style>{VIZ_CSS}</style>
</head>
<body>

<button class="navbtn" id="navbtn" aria-label="Open contents" aria-expanded="false">{BARS}</button>
<button class="toggle" id="themebtn" aria-label="Switch colour theme">{MOON}{SUN}</button>

<aside id="sidebar">
<div class="idx-eyebrow">Index</div>
<!--NAV-->
</aside>

<main>
<div class="container">

<header class="masthead">
<div class="kicker">Pre-registered · tested · null</div>
<h1>Snowmaking is absorbed by the day-ahead load forecast, not missed by it</h1>
<p class="byline">Baptiste Cristofari</p>
<p class="affil">Independent</p>
<p class="dateline">August 2026 &nbsp;·&nbsp; Energy economics / load forecasting &nbsp;·&nbsp;
  <a href="https://github.com/baptistecristo/Electricity-demand-forecasting-in-Austria">code and data</a>
</p>
</header>

<section class="tldr">
<div class="tldr-label">In one minute</div>

<p><span class="lead">The question</span>
Austrian ski resorts burn about <b>281 GWh</b> a season making artificial snow,
almost all of it on cold November and December nights — <b>8–15% of the country's
overnight demand</b>. Snowmaking is a task, not a weather response. It runs only
below a wet-bulb temperature near −2 °C, and it stops once the base layer is
built. Two identical cold nights can therefore draw very different amounts of
power. A forecast that does not know this should be visibly wrong on exactly
those nights.</p>

<p><span class="lead">What was done</span>
The prediction and the conditions for abandoning it were written down and
committed to the repository <b>before any load data was opened</b>. Then thirteen
seasons of Austrian grid data, 780 November–December nights, tested against a
wet-bulb index built from thirteen alpine weather stations between 1,221 and
2,327 m.</p>

<p><span class="lead">The answer</span>
<b>No.</b> The effect is <b>+5.1 MW, give or take 11.9</b> — indistinguishable
from zero, and pointing the opposite way to the prediction. Two of the three
pre-registered stopping rules fired.</p>

<p><span class="lead">Why that is believable</span>
The same model, on the same nights, finds the Christmas industrial shutdown at
<b>−274 MW</b>. It can see effects of the size snowmaking would have to produce.
It simply does not see snowmaking. The load is real; it is <b>absorbed</b> by
the forecast rather than missed by it, because thirteen years of cold alpine
nights <em>are</em> snowmaking nights, so the forecast's temperature response
already prices it in.</p>

<p><span class="lead">Then the same test, run elsewhere</span>
Italy-North gives the same answer: <b>+4.3 ± 10.2</b>. Switzerland is reported as
unreadable, because the arithmetic says it could never have found the effect even
if it were there. And Vermont — the one market with real room to spare, able to
detect <b>10.9 MW</b> against a fleet drawing thirty to a hundred and ten —
finds a significant effect <b>pointing the wrong way</b>. Three follow-up tests
trace it to how ISO-NE splits New England's demand between north and south, not
to snow guns.</p>

<div class="stats">
  <div class="stat"><span class="v">281</span>
    <span class="k">GWh per season of Austrian snowmaking</span></div>
  <div class="stat"><span class="v">8–15%</span>
    <span class="k">of overnight demand, at realistic coincidence</span></div>
  <div class="stat key"><span class="v">+5.1</span>
    <span class="k">MW ± 11.9 — the effect looked for, and not found</span></div>
  <div class="stat"><span class="v">4</span>
    <span class="k">markets tested; none supports the prediction</span></div>
</div>

<p class="more">Everything below is the long version: how the load was sized, how
the test was designed to separate snowmaking from heating, what was committed in
advance, the result, a correction, and three replications.</p>
</section>

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
{TABLE_MONTH}
</figure>

<figure>
{FIG_BINS}
<figcaption><b>Figure 3.</b> The same error in 10-day bins across November and
December. The bias climbs to +223 ± 41 MW in early December and then collapses at
the Christmas industrial shutdown. This is the shape, magnitude and timing snowmaking
would produce — and also what a seasonal heating ramp produces.</figcaption>
{TABLE_BINS}
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
{TABLE_COEFS}
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
<div class="verdict" style="margin:0 0 1.4rem"><strong>Scope note:</strong> the table
below is desk scoping — published or derived snowmaking energy divided by published
system load. Three of its rows have since been tested for real, in section 8.1.
Everything still in the table is a target for replication, not a result.</div>

<table>
<thead><tr><th>System</th><th class="num">GWh/season</th><th class="num">O/n load (GW)</th>
  <th class="num">Ratio</th><th>Free forecast?</th></tr></thead>
<tbody>
<tr><td>ISO-NE Vermont region <em>(tested)</em></td><td class="num">40–90*</td>
  <td class="num">0.59</td><td class="num">68–153</td><td>Yes, per region</td></tr>
<tr class="hl"><td>Austria (this study)</td><td class="num">281</td>
  <td class="num">6.6</td><td class="num">43</td><td>Yes</td></tr>
<tr><td>Italy-North <em>(tested)</em></td><td class="num">~560*</td>
  <td class="num">16.2</td><td class="num">~35</td><td>Yes, Terna</td></tr>
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
<p><b>The best test was Vermont, and it has now been run.</b> ISO-NE publishes an
hourly demand forecast per reliability region, and Vermont's 0.59 GW measured
zonal night load sits under a snowmaking fleet covering close to 100% of trail
acreage, because Northeast resorts snowmake far harder than the Alps where natural
snowfall is unreliable. Resort-level derivations put Northeast intensity at 3–7×
the Austrian figure. Rhode Island gives a same-forecaster, same-weather,
zero-snowmaking placebo inside the same feed. The caveat this row carried has been
resolved rather than assumed away: ISO-NE's regional report might have allocated a
system forecast by fixed load-share factors, which would leave it structurally
blind to anything Vermont-specific. It does not. The shares move by hour and
season and are revised on their own cycle, so the share is the thing being
modelled, and the share is what the test targets.</p>
<p><b>Andorra has the best physics on earth and no data.</b> Snowmaking at Grandvalira
and Pal Arinsal against a 570 GWh national system is plausibly a several-percent share
of national load, but FEDA sits outside ENTSO-E and publishes no hourly series. The
same holds for China's Chongli cluster.</p>

<h3>8.1 Three of those rows were then tested</h3>
<p>Same specification, same wet-bulb solver with the station-pressure correction,
same 20:00&ndash;06:59 night, same fixed effects. Only the load and weather sources
change.</p>

<table>
<thead><tr><th>System</th><th class="num">Seasons</th><th class="num">Nights</th>
  <th class="num">below &times; cum100</th><th class="num">Detectable vs fleet</th>
  <th>Verdict</th></tr></thead>
<tbody>
<tr class="hl"><td>Austria</td><td class="num">13</td><td class="num">780</td>
  <td class="num">+5.1 (11.9)</td><td class="num">427 vs 427 MW</td>
  <td>Null, at the edge of what it could see</td></tr>
<tr><td>Italy-North (Terna)</td><td class="num">7</td><td class="num">420</td>
  <td class="num">+4.3 (10.2)</td><td class="num">&mdash;</td>
  <td>Null, but uncertified</td></tr>
<tr><td>Vermont (ISO-NE)</td><td class="num">5</td><td class="num">297</td>
  <td class="num">&minus;2.5 (0.9)</td><td class="num">10.9 vs 30&ndash;110 MW</td>
  <td>Rejected, wrong sign</td></tr>
<tr><td>Switzerland</td><td class="num">9</td><td class="num">540</td>
  <td class="num">&minus;42.5 (14.3)</td><td class="num">314 vs ~200 MW</td>
  <td>Not interpretable</td></tr>
</tbody></table>
<p class="tcap"><b>Table 5.</b> Replications. Coefficients in MW, HC1 standard
errors in parentheses. Vermont's outcome is the regional <em>share</em>; its native
coefficient is &minus;0.0211 percentage points per 100 cold hours, converted here
at the 120 MW one point of share is worth.</p>

<p><b>Italy-North replicates the null.</b> Two different TSOs, two different
weather networks, and the pre-registered interaction sits in the same place, with
the predicted negative sign absent in both.</p>

<p><b>The Christmas sanity gate turns out to be an Austrian regularity.</b> Section
7.1 leans on recovering the shutdown at &minus;274 MW to show the design can see a
real effect. That works because APG's night MAE is 6.48%. Terna's is 2.17%, and its
forecast predicts &minus;4,461 MW of a &minus;4,482 MW shutdown, leaving 0.4% in the
error. Switzerland is the same story at &minus;202 against &minus;207. A competent
calendar model absorbs Christmas entirely and removes the reference effect the gate
depends on, so the Italian null carries only a paper-power bound. Any future
replication against a good forecaster needs a different reference effect.</p>

<p><b>Switzerland could never have detected the effect.</b> The minimum detectable
effect is 314 MW against a plausible Swiss coincident snowmaking load near 200 MW,
so the required &alpha; is 157% &mdash; above the ceiling. Its primary coefficient
is significant and correctly signed, and is reported as a confound rather than a
finding: it implies a swing in the load level larger than the entire Swiss fleet,
and the Swiss night-level calibration slope of 0.71 passes load&ndash;weather
structure straight into the residual.</p>

<p><b>Vermont rejects the prediction, with the sign reversed.</b> On five usable
seasons and 297 nights the interaction is &minus;0.0211 percentage points of system
share per 100 cold hours (HC1 0.0073, p = 0.004), about &minus;16 &plusmn; 11 MW at
the coldest point of a season. Positive was predicted. Rhode Island, the
no-snowmaking placebo in the same feed, stays null.</p>

<p>Three follow-ups, all run after seeing that coefficient and all labelled
post-hoc where they print, say this is ISO-NE's regional temperature response
rather than snow guns. Swapping the eight Vermont road stations for the Mount
Washington summit at 1,910 m &mdash; colder, purer, and the index a physical
reading of the hypothesis would prefer &mdash; collapses it to &minus;0.0057
(0.0056). Across all eight reliability regions the coefficients line up almost
monotonically with latitude, Spearman &minus;0.886: every northern zone negative,
every southern zone but Rhode Island positive, with Vermont the most negative of
eight rather than different in kind from Maine or New Hampshire. And moving only
the outcome window from the night to the following afternoon drops the estimate
sixfold, but the afternoon is 2.3&times; noisier and its interval still contains the
night estimate, so that placebo is reported as inconclusive rather than as
support.</p>

<p>One Vermont result points the other way and is reported without being leaned on:
the campaign-start dummy, the first night of a cold snap, is +0.076 pp
(s.e. 0.031), about +9 &plusmn; 7 MW, with a null placebo. It rests on 27 campaign
starts, carries no multiplicity correction, and is a tenth of the fleet's plausible
draw.</p>

<p><b>Why Vermont's answer weighs more than the other three.</b> Its minimum
detectable effect is 10.9 MW against a fleet drawing an estimated 30&ndash;110 MW:
powered by a factor of three to ten. Austria sits exactly at its own limit,
Switzerland is five times short. Vermont is the one place in this project where the
instrument was sharp enough that the answer is about the world rather than about
the instrument.</p>

<h2 class="sec">9. Limitations</h2>
<ul>
<li>Roughly 360 relevant hours per season, heavily autocorrelated. Effective sample
size is nights, not hours, which is why estimation is at night level.</li>
<li>The published forecast is the operator's transparency artefact, not the trading
consensus. A bias in it demonstrates a blind spot in APG's forecast, <b>not</b> a
market mispricing. Establishing the latter needs day-ahead price or imbalance as the
outcome, which is pre-registered separately in <code>src/price/</code> and run on the
day-ahead spot auction in all four markets.</li>
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

</div>
</main>
<script>{VIZ_JS}</script>
{SCRIPT}
</body>
</html>
"""


def build_index(html: str) -> str:
    """Give every section an anchor, an eyebrow, and an entry in the sidebar.

    The index is derived from the headings themselves rather than maintained by
    hand, so it cannot drift out of step with the paper.
    """
    import re

    seen = []

    def tag(m):
        title = m.group(1)
        num = re.match(r"^(\d+)\.\s*(.*)$", title)
        slug = f"sec-{len(seen) + 1}"
        if num:
            n, rest = num.group(1), num.group(2)
            seen.append((f"{int(n):02d}", rest, slug))
            eyebrow = f'<span class="chapter-label">Section {int(n):02d}</span>'
            return f'{eyebrow}<h2 class="sec" id="{slug}">{rest}</h2>'
        seen.append(("", title, slug))
        return f'<h2 class="sec" id="{slug}">{title}</h2>'

    html = re.sub(r'<h2 class="sec">(.*?)</h2>', tag, html)

    rows = []
    for n, title, slug in seen:
        num = f'<span class="n">{n}</span>' if n else '<span class="n">&nbsp;</span>'
        rows.append(f'<li><a href="#{slug}">{num}<span>{title}</span></a></li>')
    return html.replace("<!--NAV-->", '<ul class="idx">' + "".join(rows) + "</ul>")


def wrap_tables(html: str) -> str:
    """Tables scroll inside their own box so the page never scrolls sideways."""
    return (html.replace("<table>", '<div class="twrap"><table>')
                .replace("</table>", "</table></div>"))


PAGE = wrap_tables(build_index(HTML))
OUT.write_text(PAGE, encoding="utf-8")
print(f"wrote {OUT}  ({len(PAGE)/1024:.0f} KB)")
