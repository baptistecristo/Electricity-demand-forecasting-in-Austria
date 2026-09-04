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
    body = re.sub(r'<script src="[^"]*"></script>', "", body).strip()
    return _theme_svg(body)


# ggiraph bakes colour into the SVG as uppercase hex presentation attributes.
# Left alone that makes the figures theme-blind, and theme-blind here means
# broken rather than merely inconsistent: the ink is #0A0A0A, so in dark mode
# every error bar, zero line and direct label is near-black on a near-black
# page and simply disappears. Swapping the four non-series colours for CSS
# custom properties makes the figures follow the toggle. var() is legal in an
# SVG presentation attribute, and the series hues are deliberately not touched
# so a bar keeps its identity in both modes.
_SVG_TOKENS = {
    "#0A0A0A": "var(--fig-ink)",     # labels, error bars, zero lines
    "#5A5A5A": "var(--fig-mut)",     # axis text and titles
    "#E5E5E5": "var(--fig-rule)",    # grid
    "#FFFFFF": "var(--fig-bg)",      # the surface ring around overlapping marks
}


def _theme_svg(body: str) -> str:
    for hex_, token in _SVG_TOKENS.items():
        body = body.replace(f"'{hex_}'", f"'{token}'")
    return body


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


def _font_css() -> str:
    """CMU Serif, inlined so the page still makes no external request.

    Computer Modern Unicode Serif is Knuth's design, the same one Latin Modern
    Roman implements and the one a LaTeX paper is set in. The three faces here
    are subset to this page's own character set by
    site/fonts/subset.py: 607 KB of full faces become 53 KB, which is small
    enough to embed without making the single-file page absurd.

    Regenerate with `python site/fonts/subset.py` if the page ever gains a
    character outside Latin-1 plus the symbol list it carries.
    """
    import base64
    faces = []
    for style, weight, fname in (("normal", 400, "cmu-serif-regular.woff2"),
                                 ("italic", 400, "cmu-serif-italic.woff2"),
                                 ("normal", 700, "cmu-serif-bold.woff2")):
        b64 = base64.b64encode((HERE / "fonts" / fname).read_bytes()).decode()
        faces.append(
            "@font-face{font-family:'CMU Serif';"
            f"font-style:{style};font-weight:{weight};font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "\n".join(faces)


FONT_CSS = _font_css()
VIZ_CSS, VIZ_JS = _viz_assets()
FIG_MONTH = _widget("month")
FIG_BINS = _widget("bins")
FIG_COEFS = _widget("coefs")
FIG_MDE = _widget("mde")

# Every figure ships a table view, so nothing has to be read off colour alone.
TABLE_MONTH = charts.table_month()
TABLE_BINS = charts.table_bins()
TABLE_COEFS = charts.table_coefs()

# The two replication gates. Both were tables only, and both are really one
# comparison against a threshold, which a bar against a rule shows and a row of
# numbers does not. Drawn by charts.py rather than R: they need no data beyond
# the four figures each, and this keeps them buildable without an R toolchain.
FIG_ALPHA = charts.alpha_chart()
TABLE_ALPHA = charts.table_alpha()
FIG_PRICE = charts.price_chart()
TABLE_PRICE = charts.table_price()

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
<title>Snowmaking and Day-Ahead Load Forecasts: A Pre-Registered Test in Four Markets</title>
<meta name="description" content="A pre-registered test of whether ski-resort snowmaking is a systematic blind spot in day-ahead electricity load forecasts. Austria: 780 nights, 13 seasons, null. Replicated in Italy-North, Switzerland and Vermont, where one market does not agree.">
{HEAD_SCRIPT}
<style>
{FONT_CSS}
:root {{
  --bg:#ffffff; --fg:#0a0a0a; --muted:#737373; --rule:#e5e5e5;
  --accent:#0079F2; --accent-line:rgba(0,121,242,.18);
  --panel:rgba(0,121,242,.035); --code-bg:#f4f4f5; --hl:rgba(0,121,242,.05);
  --c-blue:#2b6cb0; --c-red:#c05621; --c-green:#276749; --c-grey:#9a9a9a;
  --c-plum:#702459;
  /* Series hues for the charts.py figures, matching charts.R exactly so the
     Python and R figures on this page read as one set. Like the R figures,
     these are deliberately not redefined for dark mode: a bar keeps its
     identity in both themes, and only the non-series --fig-* tokens flip. */
  --c1:#2a78d6; --c2:#eb6834; --c3:#1baf7a; --c-neutral:#8a8a8a;
  --fig-ink:#0a0a0a; --fig-mut:#5a5a5a; --fig-rule:#e5e5e5; --fig-bg:#ffffff;
  --serif:'CMU Serif',Charter,'Bitstream Charter',Cambria,
    'Liberation Serif',Georgia,'Times New Roman',serif;
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
  --fig-ink:#e5e5e5; --fig-mut:#a3a3a3; --fig-rule:#404040; --fig-bg:#0a0a0a;
}}
@media (prefers-color-scheme:dark){{
  :root:not([data-theme="light"]){{
    --bg:#0a0a0a; --fg:#e5e5e5; --muted:#a3a3a3; --rule:#404040;
    --accent:#3b9eff; --accent-line:rgba(59,158,255,.32);
    --panel:rgba(59,158,255,.07); --code-bg:rgba(255,255,255,.07);
    --hl:rgba(59,158,255,.09);
    --c-blue:#5aa9f0; --c-red:#ee8a4d; --c-green:#4bb07a; --c-grey:#8a8a8a;
    --c-plum:#d571a6;
    --fig-ink:#e5e5e5; --fig-mut:#a3a3a3; --fig-rule:#404040; --fig-bg:#0a0a0a;
  }}
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{-webkit-text-size-adjust:100%;scroll-behavior:smooth}}
body{{
  background:var(--bg); color:var(--fg); font-family:var(--serif);
  font-size:1.115rem; line-height:1.68;
  font-variant-numeric:lining-nums;
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
.container{{max-width:56rem;margin:0 auto;padding:0 3rem}}

/* ---- masthead ---- */
.masthead{{padding:6rem 0 3rem}}
.kicker{{
  font-family:var(--sans); font-size:.8rem; font-weight:500;
  letter-spacing:.15em; text-transform:uppercase; color:var(--accent);
  margin-bottom:1.6rem;
}}
h1{{
  font-size:2.05rem; line-height:1.22; font-weight:600; letter-spacing:-.005em;
  text-wrap:balance; margin-bottom:1.1rem;
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
.tldr p{{font-size:1.02rem;line-height:1.62;margin-bottom:.95rem}}
.tldr p b{{font-weight:600}}
.tldr .lead{{font-family:var(--sans);font-size:.82rem;font-weight:600;
  letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  display:block;margin-bottom:.2rem}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1.6rem;
  margin:2.2rem 0 1.6rem;padding:1.5rem 0;
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}}
.stat .v{{font-size:1.45rem;line-height:1.1;font-weight:600;
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
h2.sec{{font-size:1.42rem;line-height:1.3;font-weight:600;margin-bottom:1.1rem;
  letter-spacing:0;text-wrap:balance}}
h3{{font-size:1.08rem;line-height:1.35;font-weight:600;margin:2.2rem 0 .8rem}}
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
  body{{font-size:1rem;line-height:1.6}}
  h1{{font-size:1.6rem}} h2.sec{{font-size:1.22rem}} h3{{font-size:1rem}}
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
<div class="kicker">Pre-registered · tested in four markets</div>
<h1>Austria's load forecast absorbs snowmaking. Vermont's may not.</h1>
<p class="byline">Baptiste Cristofari</p>
<p class="affil">Independent</p>
<p class="dateline">August 2026 &nbsp;·&nbsp; Energy economics / load forecasting &nbsp;·&nbsp;
  <a href="https://github.com/baptistecristo/Electricity-demand-forecasting-in-Austria">code and data</a>
</p>
</header>

<section class="tldr">
<div class="tldr-label">In one minute</div>

<p><span class="lead">The question</span>
Austrian ski resorts burn about <b>281 GWh</b> a season making artificial snow, almost all
of it on cold November and December nights: <b>8–15% of overnight demand</b>. The guns run
only below a wet-bulb temperature near −2 °C and stop once the base layer is built, so how
much power a cold night draws depends on how much snow has already been made. A forecast
that does not know this should be wrong on exactly those nights.</p>

<p><span class="lead">The answer</span>
<b>No.</b> The prediction and the conditions for abandoning it were committed to the
repository <b>before any load data was opened</b>. On thirteen seasons and 780 nights the
effect is <b>+5.1 MW, give or take 11.9</b>, and two of three stopping rules fired. The
same model on the same nights finds the Christmas industrial shutdown at <b>−274 MW</b>,
so it can see effects of the size snowmaking would have to produce. The load is
<b>absorbed</b> by the forecast rather than missed by it.</p>

<div class="stats">
  <div class="stat"><span class="v">281</span>
    <span class="k">GWh per season of Austrian snowmaking</span></div>
  <div class="stat"><span class="v">8–15%</span>
    <span class="k">of overnight demand, at realistic coincidence</span></div>
  <div class="stat key"><span class="v">+5.1</span>
    <span class="k">MW ± 11.9, the effect looked for in Austria and not found</span></div>
  <div class="stat"><span class="v">1 of 4</span>
    <span class="k">markets where the predicted effect does show up</span></div>
</div>

<p><span class="lead">Elsewhere, and in the market</span>
Italy-North agrees at <b>+4.3 ± 10.2</b>. Switzerland could never have found the effect.
Vermont finds what was predicted but sits on its own detection threshold and does not
survive a change of weather station. A pre-registered price test cannot tell either:
overnight the supply stack is so flat that Austria's entire fleet is worth about
<b>€14/MWh</b> against a spread whose swings are three times that.</p>
</section>

<div class="abstract">
<h2>Abstract</h2>
<p>Snowmaking runs only below a wet-bulb threshold near −2 °C and stops once the base
layer is built, so how much power a cold night draws depends on how much snow has already
been made. This paper pre-registers and tests whether that path dependence appears as a
state-dependent error in the published day-ahead load forecast. On thirteen seasons of
Austrian Power Grid data joined to a pressure-corrected alpine wet-bulb index, the
interaction between the threshold and season-to-date accumulated cold is
<b>+5.1 MW (s.e. 11.9)</b> across 780 nights, while the identical specification recovers
the Christmas shutdown at <b>−274 MW (t = −3.3)</b>. The load is absorbed by the forecast,
not invisible to it. Italy-North reproduces the null, Switzerland could not have detected
the effect at any size, and Vermont returns the predicted sign but sits on its own
detection threshold.</p>
</div>

<h2 class="sec">1. The question</h2>
<p>Transmission system operators publish a day-ahead load forecast, and both it and the
realised load are free. If snowmaking is invisible to the model, that error should be
positive on nights when snowmaking runs, and the size of the miss should depend on the
snowpack rather than on temperature alone. The interest is not the ski industry but whether
a large, lumpy, path-dependent industrial load can hide inside a production forecast, a
structure that recurs in Spanish irrigation pumping and North American grain drying.</p>

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

<p>Instantaneous power follows from energy over operating hours. The coincident ceiling
is 281 GWh ÷ 184.6 h = <b>1.52 GW</b>, a mean 41.9 kW per snowmaker while running. At
40–70% coincidence the national draw is 0.61–1.07 GW against a November–December overnight
load of 7.0–7.5 GW, so snowmaking is <b>8–15% of overnight demand</b>.</p>

<h2 class="sec">3. Why a forecast might miss it, and why it might not</h2>
<p>The naive version of the hypothesis is that load forecasts are temperature models and
temperature models have no memory. Two mechanisms argue against it, both written down
before the data was opened. <b>A memoryless model still absorbs the average response:</b>
the temperature coefficient is fitted on history in which cold nights are snowmaking
nights, so the residual holds the snowmaking anomaly rather than the snowmaking load.
<b>Production forecasts are autoregressive:</b> APG publishes at 08:00 on historical actual
load, day type and temperature, so a lagged-load term carries a running campaign into
tomorrow. Both push α, the share left unexplained, down, and α binds the whole design.</p>

<h2 class="sec">4. Identification</h2>
<p>The obvious test, comparing nights just below the wet-bulb threshold to nights just
above, is contaminated. At 1,800 m, −2 °C wet bulb is roughly −1 to 0 °C air temperature,
and every nonlinearity in heating load lives near freezing: heat-pump COP collapse, defrost
cycles, trace heating. Humidity, which enters wet bulb, is itself a load driver.</p>
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
<p>Three choices decide the answer before the econometrics do. Stations are selected by
<b>altitude band</b> (900–2,600 m), because valley stations cross the threshold hundreds of
hours later than the places snow is made. Wet bulb is corrected for <b>station
pressure</b>, since ISA pressure at 1,800 m is 815 hPa and assuming sea level shifts it by
0.2–0.4 °C. And the psychrometric equation is <b>solved</b> rather than approximated,
because the Stull (2011) closed form errs by 0.7–1.0 °C below freezing.</p>

<h2 class="sec">5. Pre-registration</h2>
<p><b>Primary prediction.</b> The <code>below × cum_cold_hours</code> coefficient is
<b>negative</b> and significant at 5%.</p>
<p><b>Negative, not positive, and the direction is the whole test.</b> Snowmaking adds
load, so a cold night on its own should push the forecast error up. What identifies
snowmaking rather than heating is that the push <em>fades</em>: by late December the base is
built and the guns are off, so the same weather draws far less power than in November. A
fade is a negative number, and a positive interaction is the wrong shape rather than a
bigger effect. Supporting predictions: the error spikes on the first night of a cold snap
and decays over 24–48 hours, and the Netherlands and Denmark show nothing.</p>
<p><b>Kill criteria, committed before looking:</b></p>
<ul class="kill">
<li class="fired">The interaction is zero or positive with a tight confidence interval → no memory effect. Stop. <em>· fired</em></li>
<li class="fired">The event-study profile is flat across campaign days → the forecast already absorbs it. Stop. <em>· fired</em></li>
<li class="notrun">A cold, flat placebo country shows the same jump → the result is heating load. Stop. <em>· not run, moot once the first two fired</em></li>
</ul>
<p>All outcomes were committed to publication in advance. A null was named as the
modal outcome.</p>

<h2 class="sec">6. Statistical power</h2>
<figure>
{FIG_MDE}
<figcaption><b>Figure 1.</b> Minimum detectable effect against seasons of data, for
three assumptions about day-ahead forecast error, with the plausible residual signal
overlaid. The pass mark is how much of the ~900 MW snowmaking load the forecast must
leave unexplained. Additional seasons barely move it; α is the binding
constraint.</figcaption>
</figure>
<p>Measured on the data, the Austrian forecast is noisier than the German-Luxembourg
benchmark of 3.14% used to calibrate this: <b>6.48% MAE</b> on November–December night
hours, 554 MW after fixed effects, raising the pass mark to <b>α ≥ 27.4%</b>. Section 8.1
redoes it on fitted standard errors, which puts the real Austrian bar at 47%.</p>

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
would produce, and also what a seasonal heating ramp produces.</figcaption>
{TABLE_BINS}
</figure>

<p>The unconditional seasonal profile was encouraging. November is the most
under-forecast month of the year and the bias climbs to +223 ± 41 MW in early December
before collapsing at Christmas: the right shape and timing for snowmaking, and also what a
seasonal heating ramp produces. Conditional on weather, it vanishes.</p>

<figure>
{FIG_COEFS}
<figcaption><b>Figure 4.</b> Coefficients from the primary specification with 95%
intervals. The pre-registered interaction sits on zero. The same model, on the same
nights, places the Christmas shutdown at −274 MW, so the design is not blind to
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

<div class="verdict" style="margin:1.4rem 0"><strong>The estimated equation is not
the registered one, so both were run.</strong> The registered version uses hourly rows
with hour fixed effects and date-clustered errors, a 21:00&ndash;05:59 night, a
&plusmn;3 °C bandwidth, and no holiday or day-of-season controls. Run unchanged it
gives <b>&minus;1.3 (12.3), p = 0.91</b> against the <b>+5.1 (11.9)</b> above: the
same null at the same precision, carrying the predicted negative sign at a ninth of
its own standard error.</div>

<table>
<thead><tr><th>Campaign-start terms</th><th class="num">Coef.</th><th class="num">s.e.</th><th class="num">t</th></tr></thead>
<tbody>
<tr><td>First night of a cold snap</td><td class="num">+6.3</td><td class="num">58.6</td><td class="num">0.11</td></tr>
<tr><td>Second night</td><td class="num">−91.7</td><td class="num">86.7</td><td class="num">−1.06</td></tr>
</tbody></table>
<p class="tcap"><b>Table 3.</b> The scenario where α should be highest, because
autoregressive terms have not yet caught up. Both dummies enter the same
specification. The profile is flat, which is what the kill criterion names. The
first night's +6.3 is in the predicted direction and is a ninth of its own
standard error; the second night is wrong-signed and equally insignificant.</p>

<h3>7.1 Why this is a null rather than an absence of evidence</h3>
<p>The specification is not underpowered for effects of the relevant size. On the same
780 nights it recovers the Christmas shutdown at −274 MW with t = −3.3, and the snowmaking
interaction is +5 ± 12. The +131 MW November bias survives as a real seasonal feature not
attributable to snowmaking. Two limits: the Christmas argument works because APG leaves the
shutdown in its residual, which Terna and Swissgrid do not, and it is a claim about 274 MW.
The smallest seasonal swing the fitted model could have detected at 80% power is 426 MW
against a fleet drawing an estimated 900 MW, so Austria could only ever have caught a
forecaster missing 47% or more.</p>

<h2 class="sec">8. Was Austria a badly chosen case?</h2>
<p>A null is only interesting if the test was fair. Ranking systems by snowmaking
energy per gigawatt of winter overnight load puts Austria near the top of the world.</p>
<div class="verdict" style="margin:0 0 1.4rem"><strong>Scope note:</strong> the table
below is desk scoping: published or derived snowmaking energy divided by published
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
country: Switzerland is six times worse, France twenty-four, Germany fifty. <b>The best
test was Vermont</b>, where ISO-NE publishes an hourly demand forecast per reliability
region, a 0.59 GW zonal night load sits under a fleet covering close to 100% of trail
acreage, and Rhode Island gives a same-forecaster, zero-snowmaking placebo in the same
feed. Had ISO-NE allocated that forecast by fixed load-share factors it would be blind to
anything Vermont-specific. It does not, and the share is what the test targets.</p>

<h3>8.1 Three of those rows were then tested</h3>
<p>Same specification, same wet-bulb solver with the station-pressure correction,
same 20:00&ndash;06:59 night, same fixed effects. Only the load and weather sources
change.</p>

<table>
<thead><tr><th>System</th><th class="num">Seasons</th><th class="num">Nights</th>
  <th class="num">below &times; cum100</th><th class="num">Swing found</th>
  <th class="num">Detectable</th><th class="num">Needs &alpha;</th>
  <th>Verdict</th></tr></thead>
<tbody>
<tr><td>Italy-North (Terna)</td><td class="num">7</td><td class="num">420</td>
  <td class="num">+4.3 (10.2)</td><td class="num">+61</td>
  <td class="num">403</td><td class="num">27%*</td>
  <td>Null, and uncertified</td></tr>
<tr class="hl"><td>Vermont (ISO-NE)</td><td class="num">5</td><td class="num">297</td>
  <td class="num">&minus;2.5 (0.9)</td><td class="num">&minus;25</td>
  <td class="num">24</td><td class="num">34%</td>
  <td>Predicted sign, on its own threshold</td></tr>
<tr class="hl"><td>Austria</td><td class="num">13</td><td class="num">780</td>
  <td class="num">+5.1 (11.9)</td><td class="num">+65</td>
  <td class="num">426</td><td class="num">47%</td>
  <td>Null</td></tr>
<tr><td>Switzerland</td><td class="num">9</td><td class="num">540</td>
  <td class="num">&minus;42.5 (14.3)</td><td class="num">&minus;427</td>
  <td class="num">402</td><td class="num">201%</td>
  <td>Not interpretable</td></tr>
</tbody></table>
<p><b>How to read the power columns.</b> The coefficient is per 100 accumulated cold
hours and a season delivers about a thousand, so the seasonal swing is what has to be
detectable, and "needs &alpha;" is that divided by each market's coincident snowmaking
draw. Austria's 900 MW comes from a published survey of 141 resorts and Italy's 1,500 MW is
a desk derivation, so a five-point gap there is not a real difference.</p>
<p><b>No test here could see a forecaster missing less than about a quarter of the
snowmaking load, and Austria, on the best-grounded fleet estimate of the four,
could not see one missing less than half.</b> That is the finding behind all the
individual findings.</p>
<p class="tcap"><b>Table 5.</b> Replications. Coefficients in MW, HC1 standard
errors in parentheses. Vermont's outcome is the regional <em>share</em>; its native
coefficient is &minus;0.0211 percentage points per 100 cold hours, converted here
at the 120 MW one point of share is worth.</p>

<figure>
{FIG_ALPHA}
<figcaption><b>Figure 5.</b> The detection threshold, market by market: how much
of its own snowmaking fleet a forecaster has to be missing before this design can
see anything. Switzerland sits past the 100% ceiling, so a Swiss forecaster
modelling none of Swiss snowmaking would still be invisible to the test. Austria,
on the only fleet figure from a published survey, needs 47%.</figcaption>
{TABLE_ALPHA}
</figure>

<p><b>Italy-North replicates the null</b> at +4.3 (10.2) against Austria's +5.1 (11.9).
<b>The Christmas sanity gate is an Austrian regularity</b>, working only because APG's night
MAE is 6.48%; Terna's is 2.17% and its forecast predicts &minus;4,461 MW of a &minus;4,482 MW
shutdown, so the Italian null carries only a paper-power bound. <b>Switzerland could never
have detected the effect</b> at a required &alpha; of 201%, and its significant, correctly
signed coefficient implies a swing larger than the entire Swiss fleet, so it is a
confound.</p>

<p><b>Vermont meets the prediction, then fails to hold it.</b> On five seasons the
interaction is &minus;0.0211 percentage points of system share per 100 cold hours
(HC1 0.0073, p = 0.004), about 25 MW of decay, with Rhode Island null at +0.0019 (0.0037).
But Mount Washington in place of the eight road stations gives &minus;0.0058 (0.0068), the
effect sits on its noise floor at &minus;25 MW against 24 MW detectable, and ISO-NE's own
zonal report drops it to &minus;0.0281 (0.0188) while firing the Rhode Island placebo.
Vermont is suggestive rather than confirmation, and the Austrian null stands: 43 GWh per
gigawatt of overnight load against Vermont's 68&ndash;153.</p>

<h3>8.2 The price test: overnight, those megawatts are worth almost nothing</h3>
<p>A load forecast error is the grid operator's error, not the market's, so a null
on load does not rule out a price effect. That test is pre-registered and run in
<code>src/price/</code>. It is on the <b>day-ahead spot auction</b>, the only
instrument that clears on a snowmaking decision's eighteen-hour horizon. A
quarterly baseload futures contract averages away the day-to-day wet-bulb
variation the design runs on, so no futures contract is tested. The outcome is the
night-minus-midday price spread, which differences out the fuel cost that dominates
the level through the crisis winters; the right-hand side is the load test's,
unchanged.</p>

<table>
<thead><tr><th>Market</th><th class="num">Seasons</th><th class="num">Nights</th>
  <th class="num">Supply slope</th><th class="num">Fleet</th>
  <th class="num">Worth</th><th class="num">Detectable</th>
  <th class="num">Short by</th></tr></thead>
<tbody>
<tr class="hl"><td>Austria</td><td class="num">5</td><td class="num">300</td>
  <td class="num">+15.6</td><td class="num">900 MW</td><td class="num">+14.0</td>
  <td class="num">18.0</td><td class="num">1.3×</td></tr>
<tr><td>Italy-North</td><td class="num">7</td><td class="num">420</td>
  <td class="num">+3.5</td><td class="num">1,500 MW</td><td class="num">+5.3</td>
  <td class="num">14.4</td><td class="num">2.7×</td></tr>
<tr><td>Switzerland</td><td class="num">9</td><td class="num">540</td>
  <td class="num">+7.7</td><td class="num">200 MW</td><td class="num">+1.55</td>
  <td class="num">5.9</td><td class="num">3.8×</td></tr>
<tr><td>Vermont (ISO-NE, USD)</td><td class="num">6</td><td class="num">344</td>
  <td class="num">+23.9</td><td class="num">70 MW</td><td class="num">+1.67</td>
  <td class="num">6.7</td><td class="num">4.0×</td></tr>
</tbody></table>
<p class="tcap"><b>Table 6.</b> The price power gate, which prints before any
coefficient by design. Supply slope in €/MWh per GW, estimated from each market's
own night residual load. Everything else in €/MWh.</p>

<figure>
{FIG_PRICE}
<figcaption><b>Figure 6.</b> Why the price test cannot answer the question. In
every market the grey bar is longer than the orange one: the smallest price effect
the test could have detected is larger than what the entire snowmaking fleet is
worth at the overnight margin. Austria comes closest, short by 1.3×, and gains a
season of price data every winter.</figcaption>
{TABLE_PRICE}
</figure>

<p><b>All four come back underpowered.</b> The overnight merit order is nearly flat, so
Austria's own night data prices a 900 MW fleet at about &euro;14/MWh at the margin against a
night-day spread with a &euro;43/MWh standard deviation. A load test can find a few hundred
megawatts because load is measured in megawatts; a price test has to find what they are
worth. Austria is the near miss at 1.3&times;, and its panel grows by a winter a year. The
Christmas gate fails here for a second, independent reason: Christmas removes midday and
night demand at once, so an outcome built to ignore common demand shocks ignores the
reference effect too.</p>

<p><b>In Vermont a placebo settled it.</b> Vermont's price interaction is
<b>&minus;1.47 (0.54), p = 0.007</b>, the predicted sign, and Rhode Island, which makes no
snow, returns <b>&minus;1.33 (0.52), p = 0.011</b>. That is a New England&ndash;wide
relationship between accumulated cold and the spread, not a Vermont signal. It bites where
the load placebo could not, because the eight regional shares sum to zero by construction
and force a genuine Vermont effect to push Rhode Island the other way.</p>

<h2 class="sec">9. Limitations</h2>
<ul>
<li><b>The published forecast is the operator's transparency artefact, not the trading
consensus.</b> A bias in it shows a blind spot in APG's forecast, <b>not</b> a market
mispricing, and §8.2 shows the price version cannot settle it either.</li>
<li><b>The treatment is a switch and the physics is a staircase.</b> Olefs et al. (2010),
the source of the &minus;2 °C threshold, defines a <em>relationship between wet-bulb
temperature and snowmaking capacity</em> alongside it, and SUFAG's Taurus 2.0 auto-selects
among eight temperature-indexed thresholds. A binary treatment discards the intensity
margin, and much of the megawattage lives there.</li>
<li><b>Water temperature mimics the predicted effect.</b> Production at the margin needs
water below about +2 °C and reservoir water cools through the season, so an identical wet
bulb is more productive in late December than in early November. That runs in the same
direction as the base-building fade and needs no path dependence at all. Nothing here rules
it out, in Vermont least of all.</li>
<li><b>There is no working sensitivity check outside Austria.</b> The Christmas control
certifies the Austrian load test and nothing else, so every replication after the first
carries a paper power calculation and no proof its instrument can see anything.</li>
<li><code>cum_cold_hours</code> ignores melt and says nothing about water remaining;
operators skip marginal nights just below threshold; APG's load excludes a Vorarlberg
corridor carrying weight 0.10 in the index; the opening-date test was not identifiable from
calendar dates (R&sup2; = 0.798) and the NL/DK placebo was not run.</li>
</ul>

<h2 class="sec">10. Data and reproduction</h2>
<p>No API token is required. Austrian Power Grid publishes both load series back to 2009
as nested per-year ZIP archives with no registration, and GeoSphere Austria's station API
needs no key. One script reproduces everything:</p>
<pre><code>git clone https://github.com/baptistecristo/Electricity-demand-forecasting-in-Austria
pip install -r requirements.txt
python src/apg_pipeline.py</code></pre>
<p>For cross-country work, energy-charts.info serves day-ahead forecast, load and spot price
for most European bidding zones with no token. Futures settlement history is paywalled at
EEX and ICE, so day-ahead spot is the honest substitute.</p>

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
, DE-LU day-ahead load forecast MAE.</li>
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
