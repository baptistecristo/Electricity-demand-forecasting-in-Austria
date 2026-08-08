"""Inline SVG chart generators for the preprint page.

Charts are emitted as vector SVG rather than raster images: they stay crisp,
scale on mobile, and keep the deployed page small enough to ship in one piece.
All numbers come from src/apg_pipeline.py.
"""

INK, MUTED, RULE = "#1a1a1a", "#5a5a5a", "#d8d4cc"
BLUE, RED, GREY, GREEN = "#2b6cb0", "#c05621", "#9a9a9a", "#276749"


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bar_chart(labels, values, errors, colors, *, w=680, h=300,
              pad_l=52, pad_b=42, pad_t=14, pad_r=10, ylab="", zero_line=True):
    """Vertical bars with symmetric error bars, auto y-scale through zero."""
    lo = min(v - e for v, e in zip(values, errors))
    hi = max(v + e for v, e in zip(values, errors))
    span = hi - lo or 1
    lo -= span * 0.10
    hi += span * 0.10
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    def y(v):
        return pad_t + ph * (hi - v) / (hi - lo)

    n = len(values)
    slot = pw / n
    bw = slot * 0.58
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
           f'style="max-width:{w}px;font-family:ui-sans-serif,system-ui,sans-serif">']

    # y gridlines
    step = 10 ** len(str(int(abs(span) / 4))) if span > 4 else 1
    for m in (1, 2, 2.5, 5, 10):
        if span / (step * m) <= 6:
            step = step * m
            break
    t = (int(lo / step) - 1) * step
    while t <= hi:
        if lo <= t <= hi:
            yy = y(t)
            out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" '
                       f'stroke="{RULE}" stroke-width="1"/>')
            out.append(f'<text x="{pad_l-7}" y="{yy+3.5:.1f}" text-anchor="end" '
                       f'font-size="10" fill="{MUTED}">{int(t)}</text>')
        t += step

    if zero_line and lo < 0 < hi:
        out.append(f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{y(0):.1f}" y2="{y(0):.1f}" '
                   f'stroke="{INK}" stroke-width="1.2"/>')

    base = y(0) if lo < 0 < hi else y(max(lo, 0))
    for i, (lab, v, e, c) in enumerate(zip(labels, values, errors, colors)):
        cx = pad_l + slot * (i + 0.5)
        top, bot = min(y(v), base), max(y(v), base)
        out.append(f'<rect x="{cx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                   f'height="{max(bot-top,0.5):.1f}" fill="{c}"/>')
        out.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(v-e):.1f}" y2="{y(v+e):.1f}" '
                   f'stroke="#333" stroke-width="1.1"/>')
        for yy in (y(v - e), y(v + e)):
            out.append(f'<line x1="{cx-3.5:.1f}" x2="{cx+3.5:.1f}" y1="{yy:.1f}" '
                       f'y2="{yy:.1f}" stroke="#333" stroke-width="1.1"/>')
        for k, line in enumerate(str(lab).split("|")):
            out.append(f'<text x="{cx:.1f}" y="{h-pad_b+15+k*11}" text-anchor="middle" '
                       f'font-size="10" fill="{INK}">{_esc(line)}</text>')

    if ylab:
        out.append(f'<text transform="translate(13,{pad_t+ph/2}) rotate(-90)" '
                   f'text-anchor="middle" font-size="10.5" fill="{MUTED}">{_esc(ylab)}</text>')
    out.append("</svg>")
    return "".join(out)


def coef_plot(terms, coefs, ses, colors, *, w=680, h=250, pad_l=170,
              pad_r=22, pad_t=16, pad_b=40, xlab="Coefficient (MW), 95% CI"):
    """Horizontal dot-and-interval plot with a dashed zero line."""
    los = [c - 1.96 * s for c, s in zip(coefs, ses)]
    his = [c + 1.96 * s for c, s in zip(coefs, ses)]
    lo, hi = min(los), max(his)
    span = hi - lo or 1
    lo -= span * 0.08
    hi += span * 0.08
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    def x(v):
        return pad_l + pw * (v - lo) / (hi - lo)

    n = len(terms)
    slot = ph / n
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
           f'style="max-width:{w}px;font-family:ui-sans-serif,system-ui,sans-serif">']

    step = 100 if span > 300 else 50
    t = (int(lo / step) - 1) * step
    while t <= hi:
        if lo <= t <= hi:
            xx = x(t)
            out.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{pad_t}" y2="{pad_t+ph}" '
                       f'stroke="{RULE}" stroke-width="1"/>')
            out.append(f'<text x="{xx:.1f}" y="{pad_t+ph+16}" text-anchor="middle" '
                       f'font-size="10" fill="{MUTED}">{int(t)}</text>')
        t += step

    out.append(f'<line x1="{x(0):.1f}" x2="{x(0):.1f}" y1="{pad_t}" y2="{pad_t+ph}" '
               f'stroke="{INK}" stroke-width="1.2" stroke-dasharray="4 3"/>')

    for i, (term, c, s, col) in enumerate(zip(terms, coefs, ses, colors)):
        cy = pad_t + slot * (i + 0.5)
        out.append(f'<line x1="{x(c-1.96*s):.1f}" x2="{x(c+1.96*s):.1f}" '
                   f'y1="{cy:.1f}" y2="{cy:.1f}" stroke="#333" stroke-width="1.6"/>')
        for xx in (x(c - 1.96 * s), x(c + 1.96 * s)):
            out.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{cy-4:.1f}" '
                       f'y2="{cy+4:.1f}" stroke="#333" stroke-width="1.4"/>')
        out.append(f'<circle cx="{x(c):.1f}" cy="{cy:.1f}" r="5" fill="{col}"/>')
        for k, line in enumerate(term.split("|")):
            out.append(f'<text x="{pad_l-12}" y="{cy+3.5-((len(term.split("|"))-1)*5.5)+k*11:.1f}" '
                       f'text-anchor="end" font-size="10.5" fill="{INK}">{_esc(line)}</text>')

    out.append(f'<text x="{pad_l+pw/2:.1f}" y="{h-6}" text-anchor="middle" '
               f'font-size="10.5" fill="{MUTED}">{_esc(xlab)}</text>')
    out.append("</svg>")
    return "".join(out)


def mde_chart(*, w=680, h=310, pad_l=54, pad_r=150, pad_t=16, pad_b=40):
    """Minimum detectable effect vs seasons, three error scenarios."""
    seasons = list(range(2, 13))
    series = [
        ("MAE 1.5% (optimistic)", 132, BLUE), ("MAE 3.14% (DE-LU)", 275, RED),
        ("MAE 5% (small zone)", 439, "#702459"),
    ]
    import math
    def mde(ns, sd):
        return 2.80 * sd * math.sqrt(0.7 + 0.3 / 8) * math.sqrt(2 / (ns * 9 / 2))
    lo, hi = 0, 520
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    x = lambda s: pad_l + pw * (s - 2) / 10
    y = lambda v: pad_t + ph * (hi - v) / (hi - lo)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" '
           f'style="max-width:{w}px;font-family:ui-sans-serif,system-ui,sans-serif">']
    for t in range(0, 501, 100):
        out.append(f'<line x1="{pad_l}" x2="{pad_l+pw}" y1="{y(t):.1f}" y2="{y(t):.1f}" '
                   f'stroke="{RULE}" stroke-width="1"/>')
        out.append(f'<text x="{pad_l-7}" y="{y(t)+3.5:.1f}" text-anchor="end" '
                   f'font-size="10" fill="{MUTED}">{t}</text>')
    for s in seasons:
        if s % 2 == 0:
            out.append(f'<text x="{x(s):.1f}" y="{pad_t+ph+16}" text-anchor="middle" '
                       f'font-size="10" fill="{MUTED}">{s}</text>')
    for sig, val, ls in [(450, "half unmodelled", "none"), (225, "quarter", "5 4"),
                         (90, "tenth", "2 3")]:
        out.append(f'<line x1="{pad_l}" x2="{pad_l+pw}" y1="{y(sig):.1f}" y2="{y(sig):.1f}" '
                   f'stroke="{GREEN}" stroke-width="1.3" stroke-dasharray="{ls}"/>')
        out.append(f'<text x="{pad_l+pw+7}" y="{y(sig)+3.5:.1f}" font-size="9.5" '
                   f'fill="{GREEN}">{sig} MW · {val}</text>')
    for i, (lab, sd, col) in enumerate(series):
        pts = " ".join(f"{x(s):.1f},{y(mde(s,sd)):.1f}" for s in seasons)
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.9"/>')
        # legend inside the empty lower-right region, below the 90 MW guide
        lx = pad_l + pw * 0.44
        yy = y(66 - i * 22)
        out.append(f'<line x1="{lx:.1f}" x2="{lx+16:.1f}" y1="{yy:.1f}" y2="{yy:.1f}" '
                   f'stroke="{col}" stroke-width="1.9"/>')
        out.append(f'<text x="{lx+21:.1f}" y="{yy+3.5:.1f}" font-size="9.5" fill="{INK}">'
                   f'{_esc(lab)}</text>')
    out.append(f'<text transform="translate(13,{pad_t+ph/2}) rotate(-90)" text-anchor="middle" '
               f'font-size="10.5" fill="{MUTED}">Minimum detectable effect (MW)</text>')
    out.append(f'<text x="{pad_l+pw/2:.1f}" y="{h-6}" text-anchor="middle" font-size="10.5" '
               f'fill="{MUTED}">Seasons of data</text>')
    out.append("</svg>")
    return "".join(out)


# --- the actual numbers, from src/apg_pipeline.py -----------------------
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
MONTH_BIAS = [108, 21, 7, -30, -30, 8, -65, 25, -14, 70, 131, -10]
MONTH_SE   = [24, 16, 14, 16, 15, 14, 13, 16, 20, 16, 22, 30]

BINS      = ["Nov|1–10","Nov|11–20","Nov|21–30","Dec|1–10","Dec|11–20","Dec|21–30"]
BIN_BIAS  = [78, 81, 222, 228, 146, -383]
BIN_SE    = [24, 37, 47, 43, 46, 54]

TERMS = ["below × cum100|(PRE-REGISTERED)", "below", "campaign start", "holiday (Christmas)"]
COEFS = [1.3, 3.4, -19.5, -277.3]
SES   = [11.8, 52.6, 70.2, 84.1]


def figure_month():
    cols = [RED if m == "Nov" else BLUE for m in MONTHS]
    return bar_chart(MONTHS, MONTH_BIAS, MONTH_SE, cols,
                     ylab="Night forecast error (MW)")


def figure_bins():
    cols = [RED if v > 150 else (GREY if v < 0 else BLUE) for v in BIN_BIAS]
    return bar_chart(BINS, BIN_BIAS, BIN_SE, cols, h=310, pad_b=54,
                     ylab="Night forecast error (MW)")


def figure_coefs():
    return coef_plot(TERMS, COEFS, SES, [GREEN, GREY, GREY, RED])
