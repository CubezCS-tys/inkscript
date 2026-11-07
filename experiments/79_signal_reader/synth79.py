"""Experiment 79, step 2: synthetic lines whose letters are KNOWN, and the pen path's truth derived from them.

    PYTHONPATH=data/pylib nice -n 19 ionice -c3 python synth79.py [N=20]

A line of text (experiment 78's corpus, read only) is shaped by HarfBuzz (uharfbuzz, installed under data/pylib)
in one of experiment 78's fonts (OFL fonts and the typefaces traced from our own old scans); every glyph's outline is
filled on its own, so every ink pixel knows its letter.

The truth path: the letters in reading order; each letter's body walked along its centre line from where it joins
the letter before (its right) to where it joins the next (its left); its dots and marks right after its piece.  It is
the truth of WHICH LETTER the pen is in at every moment and which letter owns every dot (the part a reader needs);
it is not the truth of a calligrapher's hand inside a letter, which no font holds (that needs stroke definitions such
as ArabicMetafont's, see PLAN.md).

The reconstruction (sig79.line_signal, which does not know the letters) is then run on the same ink, and every point
it produces is looked up in the letter map.  Measured per line:
  letter order error   = edit distance between the letters met along the reconstructed main strokes (consecutive
                         repeats collapsed, retraces skipped) and the true letter sequence, over the number of letters
                         that have a body (the part of reconstruction that matters to a reader);
  back-steps           = how often the reconstructed path steps back to an earlier letter (not counting retraces);
  dot ownership        = share of marks the reconstruction puts in the piece that holds their true letter.
Writes out/synth/<n>.png (truth path above, reconstruction below), out/synth/sheet.png, out/synth/scores.jsonl.
"""
from __future__ import annotations

import gzip
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "data/pylib"))
import uharfbuzz as hb  # noqa: E402
from fontTools.pens.basePen import BasePen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

from sig79 import E, OUT, components, draw, line_metrics, line_signal, resample, skeleton_graph, smooth, walk  # noqa: E402

cv2.setNumThreads(1)
FONTS = E / "78_synthetic_lines/out/fonts"
TEXT = E / "78_synthetic_lines/out/text/text78.jsonl.gz"
PICK = ["amiri_Amiri-Regular.ttf", "scheherazadenew_ScheherazadeNew-Regular.ttf", "notonaskharabic_NotoNaskhArabic[wght].ttf",
        "lateef_Lateef-Regular.ttf", "markazitext_MarkaziText[wght].ttf", "harmattan_Harmattan-Regular.ttf",
        "mirza_Mirza-Regular.ttf", "amiri_Amiri-Bold.ttf", "notosansarabic_NotoSansArabic[wdth_wght].ttf",
        "traced/Mand0737y1937.ttf", "traced/Mand0300y1957.ttf", "traced/Mand0484y1958.ttf"]
ARABIC = set(chr(c) for c in range(0x0621, 0x064B))
import os
H = int(os.environ.get("H79", 96))         # the crop height (96 = twice experiment 77's 48, as real79 cuts)


class Flat(BasePen):
    """Outline -> closed polygons (curves flattened)."""

    def __init__(self, gs):
        super().__init__(gs)
        self.polys, self.cur = [], []

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for t in np.linspace(0, 1, 9)[1:]:
            a = (1 - t) ** 3
            self.cur.append(tuple(a * np.array(p0) + 3 * (1 - t) ** 2 * t * np.array(p1) + 3 * (1 - t) * t * t * np.array(p2) + t ** 3 * np.array(p3)))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for t in np.linspace(0, 1, 7)[1:]:
            self.cur.append(tuple((1 - t) ** 2 * np.array(p0) + 2 * (1 - t) * t * np.array(p1) + t * t * np.array(p2)))

    def _closePath(self):
        if len(self.cur) > 2:
            self.polys.append(np.array(self.cur, float))
        self.cur = []

    _endPath = _closePath


def glyph_mask(polys, shape, ox, oy, s):
    """Fill a glyph's contours by winding (outer contours add, holes subtract) at pen origin (ox, oy), scale s."""
    acc = np.zeros(shape, np.int16)
    for P in polys:
        q = np.c_[ox + P[:, 0] * s, oy - P[:, 1] * s]
        area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
        m = np.zeros(shape, np.uint8)
        cv2.fillPoly(m, [np.round(q * 4).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=2)
        acc += (1 if area > 0 else -1) * m.astype(np.int16)
    return acc != 0


_FONTS: dict = {}
_POLYS: dict = {}


def load_font(font_path):
    k = str(font_path)
    if k not in _FONTS:
        font = hb.Font(hb.Face(hb.Blob.from_file_path(k)))
        tt = TTFont(k)
        _FONTS[k] = (font, tt.getGlyphSet(), tt.getGlyphOrder(), tt["head"].unitsPerEm)
    return _FONTS[k]


def covers(font_path, text: str) -> bool:
    font = load_font(font_path)[0]
    return all(font.get_nominal_glyph(ord(c)) for c in text if not c.isspace())


def glyph_polys(font_path, gs, name):
    k = (str(font_path), name)
    if k not in _POLYS:
        pen = Flat(gs)
        gs[name].draw(pen)
        _POLYS[k] = pen.polys
    return _POLYS[k]


def render(text: str, font_path: Path, px_per_em: float | None = None):
    """Shaped line -> (grey crop, owner map: pixel -> letter index or -1, letters [(char index, char)])."""
    px_per_em = px_per_em or 62.0 * H / 96
    font, gs, order, upm = load_font(font_path)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    s = px_per_em / upm
    infos, poss = buf.glyph_infos, buf.glyph_positions
    width = sum(p.x_advance for p in poss) * s
    W = int(width + 0.7 * H)
    base_y = int(0.62 * H)
    owner = np.full((H, W), -1, np.int32)
    ink = np.zeros((H, W), bool)
    x = W - 0.35 * H - width                                           # glyphs come left to right (visual order)
    for gi, (inf, ps) in enumerate(zip(infos, poss)):
        polys = glyph_polys(font_path, gs, order[inf.codepoint])
        if polys:
            m = glyph_mask(polys, (H, W), x + ps.x_offset * s, base_y - ps.y_offset * s, s)
            owner[m] = inf.cluster                                     # cluster = index of its first character
            ink |= m
        x += ps.x_advance * s
    grey = np.where(ink, 25, 245).astype(np.uint8)
    grey = cv2.GaussianBlur(grey, (3, 3), 0.6)
    return grey, owner, ink


def letters_of(text: str):
    """Character index -> letter number (only Arabic letters with a body count; marks and spaces map to -1)."""
    num, k = {}, 0
    for i, c in enumerate(text):
        if c in ARABIC:
            num[i] = k
            k += 1
    return num, k


def truth_path(ink, owner, text):
    """The truth path: letters in reading order, each walked from its right join to its left one; letters of one
    joined piece follow each other without a pen lift (the reconstruction never sees letter boundaries either); a
    piece's dots and marks after the piece, right to left (the reconstruction's rule)."""
    num, n = letters_of(text)
    M = line_metrics(ink)
    step = max(1.0, 0.12 * M["rise"])
    _, piece_of = cv2.connectedComponents(ink.astype(np.uint8), connectivity=8)
    strokes, pending, cur = [], [], None

    def flush():
        for m in sorted(pending, key=lambda m: -m["pts"][:, 1].mean()):
            strokes.append(m)
        pending.clear()

    for c in sorted({int(c) for c in np.unique(owner) if c >= 0}):
        m = owner == c
        k = num.get(c, -1)
        nl, lab, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
        if nl < 2:
            continue
        parts = sorted(range(1, nl), key=lambda j: -st[j][4])
        main_j = parts[0]
        small = st[main_j][4] < 1.2 * M["stroke"] ** 2 * 2 and k < 0      # a lone mark glyph (e.g. a separate haraka)
        for j in parts:
            comp = lab == j
            G = skeleton_graph(comp, spur=1.6 * M["stroke"])
            segs = walk(G, "baseline", M, 0.0)
            if not segs:
                continue
            P = [resample(sg, step) for sg, _ in segs]
            pts = np.vstack(P)
            rt = np.concatenate([np.full(len(q), t) for q, (_, t) in zip(P, segs)])
            if j == main_j and not small:
                vals = piece_of[comp]
                pc = int(np.bincount(vals[vals > 0]).argmax()) if (vals > 0).any() else -1
                if cur is not None and pc != cur:
                    flush()
                strokes.append(dict(kind="main", pts=smooth(pts), retrace=rt, letter=k, cont=(pc == cur)))
                cur = pc
            else:
                if len(pts) > 1 and pts[0][1] < pts[-1][1]:
                    pts, rt = pts[::-1], rt[::-1]
                pending.append(
                    dict(kind="mark", pts=pts, retrace=np.zeros(len(pts), int), letter=k,
                         above=bool(cen[j][1] < M["baseline"] - 0.3 * M["rise"])))
    flush()
    from sig79 import add_thickness
    return add_thickness(dict(strokes=strokes, M=M, n_letters=n), ink)


def score(rec, owner, text, ink):
    """Letter order error, back-steps and dot ownership of a reconstruction against the letter map."""
    num, n = letters_of(text)
    H_, W_ = owner.shape
    # owner of a centre-line point: the letter of the nearest ink pixel (the centre line lies inside the ink)
    dil_owner = owner.copy()
    for _ in range(3):
        grown = cv2.dilate((dil_owner + 1).astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.int32) - 1
        dil_owner = np.where(dil_owner >= 0, dil_owner, grown)

    def at(p):
        y, x = int(round(p[0])), int(round(p[1]))
        if 0 <= y < H_ and 0 <= x < W_:
            c = dil_owner[y, x]
            return num.get(int(c), -1) if c >= 0 else -1
        return -1

    seq, back, last = [], 0, -1
    piece_letters = []
    for s in rec["strokes"]:
        if s["kind"] != "main":
            continue
        L = set()
        for p, r in zip(s["pts"], s["retrace"]):
            k = at(p)
            if k < 0:
                continue
            L.add(k)
            if r:
                continue
            if not seq or seq[-1] != k:
                if seq and k < seq[-1] and k not in seq:
                    pass
                if seq and k < last:
                    back += 1
                seq.append(k)
                last = max(last, k)
        piece_letters.append(L)
    # collapse to first visits
    first = []
    for k in seq:
        if k not in first:
            first.append(k)
    truth = sorted({num[c] for c in num if (owner == c).any()})
    from rapidfuzz.distance import Levenshtein
    err = Levenshtein.distance(first, truth) / max(1, len(truth))
    # dots: the reconstruction's marks, each by the letter of its ink
    good = tot = 0
    pi = -1
    for s in rec["strokes"]:
        if s["kind"] == "main":
            pi += 1
            continue
        ks = [at(p) for p in s["pts"]]
        ks = [k for k in ks if k >= 0]
        if not ks or pi < 0:
            continue
        tot += 1
        good += int(max(set(ks), key=ks.count) in piece_letters[pi])
    return dict(letters=len(truth), order_err=round(err, 3), back_steps=back, dots=tot,
                dot_own=round(good / tot, 3) if tot else None)


def draw_truth(grey, tp, scale=2):
    """The truth: each letter's stretch in its own colour (alternating), marks with the colour of their letter."""
    h, w = grey.shape
    img = cv2.cvtColor(cv2.resize((255 - (255 - grey) * 0.35).astype(np.uint8), (w * scale, h * scale),
                                  interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
    n = max(1, tp["n_letters"])
    for s in tp["strokes"]:
        k = s["letter"]
        hue = int(170 * (k / n)) if k >= 0 else 0
        col = cv2.cvtColor(np.uint8([[[hue, 255, 220 if k % 2 else 150]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
        p = s["pts"] * scale
        for i in range(1, len(p)):
            cv2.line(img, (int(p[i - 1][1]), int(p[i - 1][0])), (int(p[i][1]), int(p[i][0])), col, 3, cv2.LINE_AA)
        if len(p) == 1:
            cv2.circle(img, (int(p[0][1]), int(p[0][0])), 3, col, -1)
        if len(p) and s["kind"] == "main" and k >= 0:
            cv2.putText(img, str(k + 1), (int(p[0][1]) - 4, int(p[0][0]) + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
    return img


def main(n=20, seed=79):
    od = OUT / ("synth" if H == 96 else f"synth_h{H}")
    od.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    lines = []
    with gzip.open(TEXT, "rt", encoding="utf-8") as f:
        for i, l in enumerate(f):
            if i > 20000:
                break
            t = json.loads(l)["t"]
            if sum(c in ARABIC for c in t) > 0.8 * len(t.replace(" ", "")):
                lines.append(t)
    rng.shuffle(lines)
    ex = json.loads((FONTS / "traced/exclude.json").read_text(encoding="utf-8"))
    rows, tiles = [], []
    for j in range(n):
        fp = PICK[j % len(PICK)]
        e = ex.get(Path(fp).stem, {})
        bad = set(e.get("chars", "")) if isinstance(e, dict) and fp.startswith("traced") else set()

        def cut(x):
            out = ""
            for w_ in x.split():
                if len(out) + len(w_) > 30:
                    break
                out = (out + " " + w_).strip()
            return out
        t = next(x for x in lines if not (set(x) & bad) and len(cut(x)) >= 16
                 and (not fp.startswith("traced") or set(cut(x).replace(" ", "")) <= ARABIC))
        lines.remove(t)
        t = cut(t)
        grey, owner, ink = render(t, FONTS / fp)
        tp = truth_path(ink, owner, t)
        rec = line_signal(grey, start_rule="top", ink=ink)
        sc = score(rec, owner, t, ink)
        sc.update(n=j, font=Path(fp).stem, text=t)
        rows.append(sc)
        a = draw_truth(grey, tp)
        b = draw(grey, rec, scale=2, label=f"{j}  {Path(fp).stem}  letter order error {sc['order_err']}  back-steps {sc['back_steps']}  dots in right piece {sc['dot_own']}")
        bar = np.full((20, a.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, "truth (letter by letter, colour = letter, number = letter order)", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        tile = np.vstack([bar, a, b])
        cv2.imwrite(str(od / f"{j:02d}.png"), tile)
        tiles.append(tile)
        print(json.dumps(sc, ensure_ascii=False), flush=True)
    with open(od / "scores.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    Wm = max(t.shape[1] for t in tiles)
    cv2.imwrite(str(od / "sheet.png"), np.vstack([np.pad(t, ((0, 8), (0, Wm - t.shape[1]), (0, 0)), constant_values=255) for t in tiles]))
    oe = [r["order_err"] for r in rows]
    do = [r["dot_own"] for r in rows if r["dot_own"] is not None]
    print(f"mean letter order error {np.mean(oe):.3f}  median {np.median(oe):.3f}  lines with 0 error {sum(e == 0 for e in oe)}/{len(oe)}  dot ownership {np.mean(do):.3f}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
