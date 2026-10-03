#!/usr/bin/env python3
"""Screenshot the six figures of the built page as PNGs for the PDF.

Renders site/index.html in the local Chrome (light theme, captions and data
tables hidden) and saves each <figure> as site/pdf/fig/fig<n>.png at 3x, so
the Word document gets the same figures the web page shows.

Run after `python site/build.py`:  python site/pdf/figures.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PAGE = HERE.parent / "index.html"
OUT = HERE / "fig"

HIDE = """
figcaption, .dtable, .toggle, .navbtn, aside { display:none !important }
main { margin-left:0 !important }
figure { margin:0 !important; padding:8px 0 !important; background:#fff }
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 900, "height": 1200},
                                device_scale_factor=3, color_scheme="light")
        page.goto(PAGE.as_uri())
        page.evaluate("document.documentElement.setAttribute('data-theme','light')")
        page.add_style_tag(content=HIDE)
        page.wait_for_timeout(1500)   # let the htmlwidgets render
        figs = page.query_selector_all("figure")
        for i, fig in enumerate(figs, 1):
            fig.screenshot(path=str(OUT / f"fig{i}.png"))
        browser.close()
    print(f"wrote {len(figs)} figures to {OUT}")


if __name__ == "__main__":
    main()
