# 08 — Letter joins inside a connected run (first measurement)

Roadmap item 4: selection inside a word is per piece of ink; letters
joined along the baseline are one glyph. Where could a piece be cut into
letters without guessing?

First criterion (`joins.py`): a join column is one whose ink lies entirely
within a thin band around the baseline stroke (the row with the most ink,
± the median stroke width). A run of such columns at least half a stroke
wide, away from the piece's ends, gives one cut at its midpoint. A piece is
"clean" when cuts = letters − 1 (marks dropped, lam-alef one letter; only
unvowelled words whose ink is one connected component).

Fixture document (test set), 399 pieces: **99 clean (24.8%)**, 14 over-cut,
286 under-cut. `joins.png` shows twelve examples (red = cut, blue = the
baseline row). Regular body type cuts well (`يمكن` 3/3, `عملت` 3/3,
`بمنتصف` 5/5); under-cuts come from bold display type (the stroke band
swallows the letters) and from bowls that swoop under the neighbouring
letter (`ج ح خ` medial forms, `ي` tails), which hide the join under the
strict "nothing outside the band" test.

Next: score columns by ink height relative to the piece (local minima of
the column's top-to-bottom extent), not by a fixed band; treat the upper
and lower contours separately so a bowl below the baseline does not hide a
join above it; verify a cut against pdfium (per-letter glyphs copy out
identically to the whole word, so a wrong cut changes only what a drag
selects, never the text). Adopt cuts only where the count matches.

Second criterion (the baseline band from the ink row profile at half its
peak, instead of ± a stroke width): 30.6% clean (122 / 399; 25 over, 252
under); allowing ink below the band (a bowl swooping under the next
letter): 32.8% (131; 47 over, 221 under). The under-cuts that remain are
mostly tooth letters (`ب ت ث ن ي س ش` in medial form), whose bodies are
themselves small bumps on the baseline stroke: the join between two teeth
is not lower than the teeth. Height alone cannot find those; the dots
above and below (separate components, currently ignored) and the tooth
rhythm would have to be read. That is the actual research problem behind
roadmap item 4, and it is where this stops for now.
