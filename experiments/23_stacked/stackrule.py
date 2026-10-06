"""The rule, shared by the post-processor (post.py, on finished PDFs) and the type3 patch (patch.py).

Input: one line's glyphs in stream order (left to right), each a dict with
  word  - an id shared by the glyphs of one word,
  text  - its text (a cut letter has one character),
  paths - its outline polygons, [[x, y], ...] in any one unit, x growing right, y growing UP,
  d1    - its declared box [wx, 0, llx, lly, urx, ury] in glyph units, origin = x0 of its advance,
  x0, y0, k - its origin in the paths' unit, and the paths' unit per glyph unit (to convert).
Output: {index: new d1 box [llx, lly, urx, ury]} for the stacked letters only.

Stacked: two neighbouring one-letter glyphs of the same word whose BODIES (the largest outline: dots and holes
left out) overlap horizontally by at least 40% of the narrower body, with vertical centres apart by at least a
quarter of the pair's joint height. Then each of the two gets a box of its own height:
  VARIANT "cell": x = its advance (as today: neighbours tile the word), y = its own whole ink (FontBBox only);
  VARIANT "ink":  x and y = its own ink (boxes may overlap in x; they then differ in y).
"""
VARIANT = "cell"
OVERLAP, APART = 0.4, 0.25


def _bbox(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; return min(xs), min(ys), max(xs), max(ys)


def body(g):
    bbs = [_bbox(p) for p in g["paths"] if len(p) >= 3]
    return max(bbs, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])) if bbs else None


def ink(g):
    bbs = [_bbox(p) for p in g["paths"] if len(p) >= 3]
    return (min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs)) if bbs else None


def stacked(gs):
    """Indices i (of gs) that are stacked with a neighbour."""
    out = set()
    for i in range(len(gs) - 1):
        a, b = gs[i], gs[i + 1]
        if a["word"] != b["word"] or len(a["text"]) != 1 or len(b["text"]) != 1: continue
        A, B = body(a), body(b)
        if A is None or B is None: continue
        ov = min(A[2], B[2]) - max(A[0], B[0]); nw = min(A[2] - A[0], B[2] - B[0])
        h = max(A[3], B[3]) - min(A[1], B[1])
        if nw > 0 and ov >= OVERLAP * nw and abs((A[1] + A[3]) - (B[1] + B[3])) / 2 >= APART * h:
            out |= {i, i + 1}
    return out


def boxes(gs, variant=None):
    variant = variant or VARIANT; res = {}
    for i in sorted(stacked(gs)):
        g = gs[i]; d1 = g["d1"]
        if variant == "ink":
            x0, y0, x1, y1 = ink(g); k = g["k"]
            llx, urx = (x0 - g["x0"]) / k, (x1 - g["x0"]) / k
            res[i] = [round(llx), d1[3], round(urx), d1[5]]          # y: today's d1 height (own ink, clipped at the neighbouring lines)
        else:
            # x: today's d1 (the advance); y: the letter's whole ink, NOT clipped at the neighbouring lines. Only the
            # font's FontBBox gets this height (Chromium draws the highlight's height from it); d1, which pdfium uses
            # to build lines, keeps today's clipped height, so the line rules are untouched.
            x0, y0, x1, y1 = ink(g); k = g["k"]; oy = g.get("y0", 0.0)
            res[i] = [d1[2], round((y0 - oy) / k), d1[4], round((y1 - oy) / k)]
    return res
