"""Inline SVG chart generators for the preprint page.

Charts are emitted as vector SVG rather than raster images: they stay crisp,
scale on mobile, and keep the deployed page small enough to ship in one piece.
All numbers come from src/apg_pipeline.py.

Colour is not eyeballed. The categorical slots below were checked with the
dataviz palette validator against this page's own surfaces (#ffffff light,
#0a0a0a dark) and pass the lightness band, chroma floor, colour-vision
separation and normal-vision floor in both modes. The one light-mode contrast
warning (aqua at 2.82:1) is discharged the way the rule requires: every figure
ships direct labels and a table view, so no reading depends on colour alone.

The figures read the page's CSS custom properties directly, which is what keeps
them legible in both themes without shipping two copies of every chart.
"""

INK, MUTED, RULE = "var(--fg)", "var(--muted)", "var(--rule)"
C1, C2, C3 = "var(--c1)", "var(--c2)", "var(--c3)"   # blue, orange, aqua
NEUTRAL = "var(--c-neutral)"

FONT = ("font-family:var(--sans),ui-sans-serif,system-ui,sans-serif")


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _svg(w, h, body, label):
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
            f'aria-label="{_esc(label)}" style="max-width:{w}px;{FONT}">'
            + body + "</svg>")


def _round_top(x, y, w, h, r=4):
    """Bar with rounded data-end. Negative bars round at the bottom instead."""
    if h >= 0:
        r = min(r, w / 2, max(h, 0.1))
        return (f'M{x:.1f},{y+h:.1f} L{x:.1f},{y+r:.1f} Q{x:.1f},{y:.1f} '
                f'{x+r:.1f},{y:.1f} L{x+w-r:.1f},{y:.1f} Q{x+w:.1f},{y:.1f} '
                f'{x+w:.1f},{y+r:.1f} L{x+w:.1f},{y+h:.1f} Z')
    h = -h
    r = min(r, w / 2, max(h, 0.1))
    return (f'M{x:.1f},{y-h:.1f} L{x:.1f},{y-r:.1f} Q{x:.1f},{y:.1f} '
            f'{x+r:.1f},{y:.1f} L{x+w-r:.1f},{y:.1f} Q{x+w:.1f},{y:.1f} '
            f'{x+w:.1f},{y-r:.1f} L{x+w:.1f},{y-h:.1f} Z')


def bar_chart(labels, values, errors, colors, *, w=680, h=320, pad_l=54,
              pad_b=52, pad_t=22, pad_r=14, ylab="", unit="MW", emphasise=(),
              label_fmt="{:+.0f}", aria=""):
    """Vertical bars with symmetric error bars, hover values and direct labels.

    `emphasise` indexes the bars that carry a printed value, so the chart labels
    what the argument turns on instead of numbering every bar.
    """
    lo = min(v - e for v, e in zip(values, errors))
    hi = max(v + e for v, e in zip(values, errors))
    span = (hi - lo) or 1
    lo -= span * 0.14
    hi += span * 0.16
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    def y(v):
        return pad_t + ph * (hi - v) / (hi - lo)

    slot = pw / len(values)
    bw = min(slot - 6, slot * 0.62)          # >=2px surface gap between bars
    out = []

    step = 10 ** len(str(int(abs(span) / 4))) if span > 4 else 1
    for m in (1, 2, 2.5, 5, 10):
        if span / (step * m) <= 6:
            step *= m
            break
    t = (int(lo / step) - 1) * step
    while t <= hi:
        if lo <= t <= hi:
            out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{y(t):.1f}" '
                       f'y2="{y(t):.1f}" stroke="{RULE}" stroke-width="1"/>')
            out.append(f'<text x="{pad_l-8}" y="{y(t)+3.5:.1f}" text-anchor="end" '
                       f'font-size="10.5" fill="{MUTED}">{int(t)}</text>')
        t += step

    if lo < 0 < hi:
        out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{y(0):.1f}" '
                   f'y2="{y(0):.1f}" stroke="{INK}" stroke-width="1.2"/>')

    base = y(0) if lo < 0 < hi else y(max(lo, 0))
    for i, (lab, v, e, c) in enumerate(zip(labels, values, errors, colors)):
        cx = pad_l + slot * (i + 0.5)
        flat = str(lab).replace("|", " ")
        out.append(f'<path d="{_round_top(cx-bw/2, base, bw, y(v)-base)}" '
                   f'fill="{c}"/>')
        out.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(v-e):.1f}" '
                   f'y2="{y(v+e):.1f}" stroke="{INK}" stroke-width="1.6" '
                   f'stroke-linecap="round" opacity=".75"/>')
        if i in emphasise:
            up = v >= 0
            out.append(f'<text x="{cx:.1f}" y="{(y(v+e)-9) if up else (y(v-e)+16):.1f}" '
                       f'text-anchor="middle" font-size="11.5" font-weight="600" '
                       f'fill="{INK}">{label_fmt.format(v)}</text>')
        for k, line in enumerate(str(lab).split("|")):
            out.append(f'<text x="{cx:.1f}" y="{h-pad_b+17+k*12}" '
                       f'text-anchor="middle" font-size="10.5" '
                       f'fill="{MUTED}">{_esc(line)}</text>')
        # Hit target spans the whole slot, not just the bar.
        out.append(f'<rect class="hit" x="{pad_l+slot*i:.1f}" y="{pad_t}" '
                   f'width="{slot:.1f}" height="{ph:.1f}" fill="transparent" '
                   f'tabindex="0" role="button" '
                   f'data-k="{_esc(flat)}" '
                   f'data-v="{v:+.1f} &#177; {e:.0f} {unit}"/>')

    if ylab:
        out.append(f'<text transform="translate(14,{pad_t+ph/2}) rotate(-90)" '
                   f'text-anchor="middle" font-size="10.5" fill="{MUTED}">'
                   f'{_esc(ylab)}</text>')
    return _svg(w, h, "".join(out), aria or ylab)


def coef_plot(terms, coefs, ses, colors, *, w=680, h=260, pad_l=178, pad_r=64,
              pad_t=20, pad_b=42, xlab="Coefficient (MW), 95% confidence interval",
              aria=""):
    """Horizontal dot-and-interval plot with a dashed zero line."""
    los = [c - 1.96 * s for c, s in zip(coefs, ses)]
    his = [c + 1.96 * s for c, s in zip(coefs, ses)]
    lo, hi = min(los), max(his)
    span = (hi - lo) or 1
    lo -= span * 0.10
    hi += span * 0.10
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    def x(v):
        return pad_l + pw * (v - lo) / (hi - lo)

    slot = ph / len(terms)
    out = []
    step = 100 if span > 300 else 50
    t = (int(lo / step) - 1) * step
    while t <= hi:
        if lo <= t <= hi:
            out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{pad_t}" '
                       f'y2="{pad_t+ph}" stroke="{RULE}" stroke-width="1"/>')
            out.append(f'<text x="{x(t):.1f}" y="{pad_t+ph+18}" '
                       f'text-anchor="middle" font-size="10.5" '
                       f'fill="{MUTED}">{int(t)}</text>')
        t += step

    out.append(f'<line x1="{x(0):.1f}" x2="{x(0):.1f}" y1="{pad_t}" '
               f'y2="{pad_t+ph}" stroke="{INK}" stroke-width="1.4" '
               f'stroke-dasharray="4 3"/>')

    for i, (term, c, s, col) in enumerate(zip(terms, coefs, ses, colors)):
        cy = pad_t + slot * (i + 0.5)
        lo_i, hi_i = c - 1.96 * s, c + 1.96 * s
        out.append(f'<line x1="{x(lo_i):.1f}" x2="{x(hi_i):.1f}" y1="{cy:.1f}" '
                   f'y2="{cy:.1f}" stroke="{INK}" stroke-width="2" '
                   f'stroke-linecap="round" opacity=".8"/>')
        # 2px surface ring so the marker stays readable over the interval line
        out.append(f'<circle cx="{x(c):.1f}" cy="{cy:.1f}" r="6.5" '
                   f'fill="{col}" stroke="var(--bg)" stroke-width="2"/>')
        out.append(f'<text x="{w-pad_r+8}" y="{cy+4:.1f}" font-size="11.5" '
                   f'font-weight="600" fill="{INK}">{c:+.1f}</text>')
        lines = term.split("|")
        for k, line in enumerate(lines):
            out.append(f'<text x="{pad_l-16}" y="'
                       f'{cy+4-((len(lines)-1)*6)+k*12:.1f}" text-anchor="end" '
                       f'font-size="11" fill="{INK}">{_esc(line)}</text>')
        out.append(f'<rect class="hit" x="{pad_l}" y="{cy-slot/2:.1f}" '
                   f'width="{pw:.1f}" height="{slot:.1f}" fill="transparent" '
                   f'tabindex="0" role="button" '
                   f'data-k="{_esc(term.replace("|", " "))}" '
                   f'data-v="{c:+.2f} MW (s.e. {s:.2f}) &#183; 95% CI '
                   f'[{lo_i:+.0f}, {hi_i:+.0f}]"/>')

    out.append(f'<text x="{pad_l+pw/2:.1f}" y="{h-6}" text-anchor="middle" '
               f'font-size="10.5" fill="{MUTED}">{_esc(xlab)}</text>')
    return _svg(w, h, "".join(out), aria or xlab)


def mde_chart(*, w=680, h=330, pad_l=56, pad_r=158, pad_t=18, pad_b=44):
    """Minimum detectable effect vs seasons, three forecast-error scenarios."""
    import math
    seasons = list(range(2, 13))
    series = [("MAE 1.5% (optimistic)", 132, C1),
              ("MAE 3.14% (DE-LU)", 275, C2),
              ("MAE 6.48% (measured AT)", 568, C3)]

    def mde(ns, sd):
        return 2.80 * sd * math.sqrt(0.7 + 0.3 / 8) * math.sqrt(2 / (ns * 9 / 2))

    lo, hi = 0, 660
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    def x(s): return pad_l + pw * (s - 2) / 10
    def y(v): return pad_t + ph * (hi - v) / (hi - lo)

    out = []
    for t in range(0, 661, 100):
        out.append(f'<line x1="{pad_l}" x2="{pad_l+pw}" y1="{y(t):.1f}" '
                   f'y2="{y(t):.1f}" stroke="{RULE}" stroke-width="1"/>')
        out.append(f'<text x="{pad_l-8}" y="{y(t)+3.5:.1f}" text-anchor="end" '
                   f'font-size="10.5" fill="{MUTED}">{t}</text>')
    for s in seasons:
        if s % 2 == 0:
            out.append(f'<text x="{x(s):.1f}" y="{pad_t+ph+18}" '
                       f'text-anchor="middle" font-size="10.5" '
                       f'fill="{MUTED}">{s}</text>')

    for sig, val in [(450, "half the load unmodelled"), (225, "a quarter"),
                     (90, "a tenth")]:
        out.append(f'<line x1="{pad_l}" x2="{pad_l+pw}" y1="{y(sig):.1f}" '
                   f'y2="{y(sig):.1f}" stroke="{MUTED}" stroke-width="1.2" '
                   f'stroke-dasharray="5 4" opacity=".8"/>')
        out.append(f'<text x="{pad_l+pw+8}" y="{y(sig)+3.5:.1f}" font-size="10" '
                   f'fill="{MUTED}">{sig} MW &#183; {val}</text>')

    for lab, sd, col in series:
        pts = " ".join(f"{x(s):.1f},{y(mde(s,sd)):.1f}" for s in seasons)
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" '
                   f'stroke-width="2" stroke-linejoin="round"/>')
        out.append(f'<circle cx="{x(13-1):.1f}" cy="{y(mde(12,sd)):.1f}" r="4.5" '
                   f'fill="{col}" stroke="var(--bg)" stroke-width="2"/>')
        for s in seasons:
            out.append(f'<rect class="hit" x="{x(s)-13:.1f}" '
                       f'y="{y(mde(s,sd))-13:.1f}" width="26" height="26" '
                       f'fill="transparent" tabindex="0" role="button" '
                       f'data-k="{_esc(lab)} &#183; {s} seasons" '
                       f'data-v="minimum detectable effect '
                       f'{mde(s,sd):.0f} MW"/>')

    # Legend: three series, so identity never rests on colour alone.
    for i, (lab, sd, col) in enumerate(series):
        ly = pad_t + 8 + i * 17
        out.append(f'<line x1="{pad_l+pw+8}" x2="{pad_l+pw+26}" y1="{ly}" '
                   f'y2="{ly}" stroke="{col}" stroke-width="2.4"/>')
        out.append(f'<text x="{pad_l+pw+31}" y="{ly+3.5}" font-size="9.8" '
                   f'fill="{INK}">{_esc(lab)}</text>')

    out.append(f'<text transform="translate(14,{pad_t+ph/2}) rotate(-90)" '
               f'text-anchor="middle" font-size="10.5" fill="{MUTED}">'
               f'Minimum detectable effect (MW)</text>')
    out.append(f'<text x="{pad_l+pw/2:.1f}" y="{h-6}" text-anchor="middle" '
               f'font-size="10.5" fill="{MUTED}">Seasons of data</text>')
    return _svg(w, h, "".join(out),
                "Minimum detectable effect against seasons of data, three "
                "forecast-error scenarios")


def data_table(headers, rows, caption):
    """The table view every figure ships, so no reading depends on colour."""
    th = "".join(f'<th class="num">{_esc(h)}</th>' if i else f"<th>{_esc(h)}</th>"
                 for i, h in enumerate(headers))
    tr = "".join("<tr>" + "".join(
        f'<td class="num">{_esc(c)}</td>' if i else f"<td>{_esc(c)}</td>"
        for i, c in enumerate(r)) + "</tr>" for r in rows)
    return (f'<details class="dtable"><summary>{_esc(caption)}</summary>'
            f'<div class="twrap"><table><thead><tr>{th}</tr></thead>'
            f"<tbody>{tr}</tbody></table></div></details>")


# --- the actual numbers, from src/apg_pipeline.py -----------------------
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_BIAS = [108, 21, 8, -30, -30, 8, -65, 25, -14, 70, 131, -10]
MONTH_SE = [24, 16, 14, 16, 15, 14, 13, 16, 20, 16, 22, 30]

BINS = ["Nov|1–10", "Nov|11–20", "Nov|21–30",
        "Dec|1–10", "Dec|11–20", "Dec|21–30"]
BIN_BIAS = [80, 90, 223, 223, 134, -383]
BIN_SE = [25, 37, 48, 41, 47, 54]

TERMS = ["below × cum100|(PRE-REGISTERED)", "below", "campaign start",
         "holiday (Christmas)"]
COEFS = [5.1, 27.2, 6.3, -273.6]
SES = [11.9, 53.2, 58.6, 84.0]


def figure_month():
    cols = [C2 if m == "Nov" else C1 for m in MONTHS]
    return bar_chart(MONTHS, MONTH_BIAS, MONTH_SE, cols,
                     ylab="Night forecast error (MW)",
                     emphasise=(10,),
                     aria="Night forecast error by month; November is the "
                          "highest at plus 131 megawatts")


def table_month():
    return data_table(
        ["Month", "Night bias (MW)", "s.e."],
        [[m, f"{v:+d}", f"{e}"] for m, v, e in
         zip(MONTHS, MONTH_BIAS, MONTH_SE)],
        "Show the monthly figures as a table")


def figure_bins():
    cols = [C2 if v > 150 else (NEUTRAL if v < 0 else C1) for v in BIN_BIAS]
    return bar_chart(BINS, BIN_BIAS, BIN_SE, cols, h=340, pad_b=64,
                     ylab="Night forecast error (MW)",
                     emphasise=(3, 5),
                     aria="Night forecast error in ten-day bins; it peaks in "
                          "early December then collapses at Christmas")


def table_bins():
    return data_table(
        ["10-day bin", "Night bias (MW)", "s.e."],
        [[b.replace("|", " "), f"{v:+d}", f"{e}"] for b, v, e in
         zip(BINS, BIN_BIAS, BIN_SE)],
        "Show the 10-day bins as a table")


def figure_coefs():
    return coef_plot(TERMS, COEFS, SES, [C3, NEUTRAL, NEUTRAL, C2],
                     aria="The pre-registered interaction sits on zero while "
                          "the Christmas control is far from it")


def table_coefs():
    return data_table(
        ["Term", "Coefficient (MW)", "s.e.", "95% CI"],
        [[t.replace("|", " "), f"{c:+.1f}", f"{s:.1f}",
          f"[{c-1.96*s:+.0f}, {c+1.96*s:+.0f}]"]
         for t, c, s in zip(TERMS, COEFS, SES)],
        "Show the coefficients as a table")
