#!/usr/bin/env python3
"""Download CMU Serif and subset it to the glyphs this page actually uses.

CMU (Computer Modern Unicode) Serif is Knuth's design, the same one Latin Modern
Roman implements and the one a LaTeX paper is set in. The three full faces are
~600 KB, which is too much to inline; subsetting to the page's own character set
brings that to ~53 KB, and build.py embeds the result as data URIs.

Run from anywhere:  python site/fonts/subset.py
Needs fonttools and brotli. Re-run whenever the page gains a character outside
Latin-1 plus the symbol list below, then rebuild with `python site/build.py`.
"""
import re
import urllib.request
from pathlib import Path

from fontTools.subset import main as subset_main

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
CACHE = HERE / ".src"

BASE = "https://cdn.jsdelivr.net/npm/computer-modern@0.1.2/fonts/"
FACES = {
    "regular": "cmu-serif-500-roman.woff2",
    "italic": "cmu-serif-500-italic.woff2",
    "bold": "cmu-serif-700-roman.woff2",
}


def main() -> None:
    CACHE.mkdir(exist_ok=True)

    # Everything the built page contains, plus a Latin-1 floor so a later edit
    # that introduces an accented name does not silently lose its glyph.
    page = (SITE / "index.html").read_text(encoding="utf-8")
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S)
    chars = set(re.sub(r"<[^>]+>", " ", page))
    chars |= {chr(c) for c in range(0x20, 0x7F)}
    chars |= {chr(c) for c in range(0xA0, 0x100)}
    chars |= set("−×±≈≤≥→…·§€°²³½¼¾αβγΔΣμ‰′″“”‘’–—†‡")
    chars = {c for c in chars if c.isprintable() and ord(c) > 0x1F}
    unicodes = ",".join(f"U+{ord(c):04X}" for c in sorted(chars))
    print(f"subsetting to {len(chars)} characters")

    raw = sub = 0
    for style, fname in FACES.items():
        src = CACHE / fname
        if not src.exists():
            with urllib.request.urlopen(BASE + fname, timeout=60) as r:
                src.write_bytes(r.read())
        dst = HERE / f"cmu-serif-{style}.woff2"
        subset_main([
            str(src),
            f"--unicodes={unicodes}",
            "--flavor=woff2",
            "--layout-features=kern,liga,ccmp,locl,mark,mkmk",
            "--no-hinting",
            "--desubroutinize",
            f"--output-file={dst}",
        ])
        raw += src.stat().st_size
        sub += dst.stat().st_size
        print(f"  {style:8s} {src.stat().st_size:7,d} -> {dst.stat().st_size:6,d} B")

    print(f"total {raw:,} -> {sub:,} B ({100 * sub / raw:.0f}% of original)")


if __name__ == "__main__":
    main()
