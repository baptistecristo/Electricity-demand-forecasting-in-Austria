# Fonts

`cmu-serif-{regular,italic,bold}.woff2` are subsets of **CMU Serif** (Computer
Modern Unicode), Knuth's Computer Modern design and the same one Latin Modern
Roman implements. They are here so the paper reads like a paper.

Subset from the [`computer-modern`](https://www.npmjs.com/package/computer-modern)
npm package to this page's own character set (Latin-1 plus the symbols the text
uses), which takes the three faces from 607 KB to 53 KB. `build.py` inlines them
as data URIs, so the deployed page still makes no external request.

Regenerate with `scratchpad/getfonts.py` if the page gains a character outside
that range.

Licensed under the SIL Open Font License 1.1. See `OFL.txt`.
