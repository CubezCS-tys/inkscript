"""Experiment 87, stage 1b: letter programs recovered from fonts with exp 82's learned centre line.

For every glyph a font uses on our texts (HarfBuzz-shaped: contextual forms, ligatures, marks), the glyph alone is
rasterised at exp 82's scale (62 px per em, the 96-px line), exp 82's U-Net (out/learned/u1/model.pt) predicts its
centre line, and the line is cut into its edges (end point / junction to the next; closed loops whole), each a pen
stroke run right to left.  Each point keeps the ink's half-width there (distance transform) as r0.  (exp 79/82's
walk was tried first: its spur pruning drops the short teeth and tails a single glyph is made of, so 20-40% of a
glyph's ink had no stroke; the edges keep all of it.)  An ink piece the network left without a line (a dot) is
thinned instead.  Small pieces off the body (dots, hamza) are flagged as marks.

    python fontprog87.py texts            # out/programs/texts.txt: every text the writer will need (no truth used)
    python fontprog87.py build [fonts..]  # out/programs/font_<name>.json   (CPU, 2 threads, nice)
    python fontprog87.py look <name>      # a specimen: the font's own ink beside the written programs

Licences: every modern face is SIL OFL 1.1 (the *_OFL.txt next to it in 78_synthetic_lines/out/fonts); the traced
faces are ours (traced from our own scans, exp 78); faces whose code is a locked journal would be refused.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
PROG = OUT / "programs"
sys.path.insert(0, str(E / "82_path_accuracy"))
sys.path.insert(0, str(E / "88_truth_and_lock"))
from locked_old import is_locked_any  # noqa: E402

FONTS = E / "78_synthetic_lines/out/fonts"
EXCLUDE = json.loads((FONTS / "traced/exclude.json").read_text(encoding="utf-8"))
MODERN = ["amiri_Amiri-Regular.ttf", "amiri_Amiri-Bold.ttf", "scheherazadenew_ScheherazadeNew-Regular.ttf",
          "scheherazadenew_ScheherazadeNew-Bold.ttf", "notonaskharabic_NotoNaskhArabic[wght].ttf",
          "lateef_Lateef-Regular.ttf", "markazitext_MarkaziText[wght].ttf", "harmattan_Harmattan-Regular.ttf",
          "mirza_Mirza-Regular.ttf", "notosansarabic_NotoSansArabic[wdth_wght].ttf",
          "ibmplexsansarabic_IBMPlexSansArabic-Regular.ttf", "vazirmatn_Vazirmatn[wght].ttf", "tajawal_Tajawal-Regular.ttf"]
TRACED = sorted(f"traced/{p.name}" for p in (FONTS / "traced").glob("*.ttf")
                if EXCLUDE.get(p.stem) != "DROP" and p.stem in EXCLUDE)
for f in TRACED:                       # a traced face is named Mand<journal code>y<year>
    assert not is_locked_any(Path(f).stem[4:8]), f"traced face from a locked journal: {f}"
PX = 62.0                              # px per em, exp 82's scale on its 96-px lines
HC, BASE = 176, 104                    # canvas height and baseline row (room for ascenders and descenders)


def name_of(font: str) -> str:
    return Path(font).stem.replace("[", "_").replace("]", "").replace(",", "_")


def licence_of(font: str) -> str:
    if font.startswith("traced/"):
        return "ours: traced from our own scans (exp 11/78)"
    fam = font.split("_")[0]
    lic = FONTS / f"{fam}_OFL.txt"
    return "SIL Open Font License 1.1 (" + lic.name + ")" if lic.exists() else "UNKNOWN"


def texts():
    """Every text the writer may be asked to write: pool lines, held-out readings (every reader) and planted
    variants' words come from these too; plus a sample of exp 78's corpus for coverage."""
    T = set()
    for l in open(OUT / "data/pool.jsonl", encoding="utf-8"):
        T.add(json.loads(l)["text"])
    X = E / "81_heldout_scale/out"
    keys = {json.loads(l)["key"] for l in open(OUT / "data/held.jsonl", encoding="utf-8")}
    for l in open(X / "readings81.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["key"] in keys:
            T.update(v for v in d["readings"].values() if isinstance(v, str))
    for f in ("answers.jsonl",):
        for l in open(X / "judge" / f, encoding="utf-8"):
            d = json.loads(l)
            if d["key"] in keys and d.get("reading"):
                T.add(d["reading"])
    with gzip.open(E / "78_synthetic_lines/out/text/text78.jsonl.gz", "rt", encoding="utf-8") as f:
        for i, l in enumerate(f):
            if i % 200 == 11:
                T.add(json.loads(l)["t"])
            if len(T) > 40000:
                break
    (PROG / "texts.txt").write_text("\n".join(sorted(t.replace("\n", " ") for t in T)), encoding="utf-8")
    print(len(T), "texts")


def glyphs_used(font_path: Path, T):
    import uharfbuzz as hb
    f = hb.Font(hb.Face(hb.Blob.from_file_path(str(font_path))))
    used = set()
    for t in T:
        buf = hb.Buffer()
        buf.add_str(t)
        buf.guess_segment_properties()
        hb.shape(f, buf, {})
        used.update(i.codepoint for i in buf.glyph_infos)
    return sorted(used)


_M = None


def model():
    global _M
    if _M is None:
        import torch
        from net82 import UNet
        torch.set_num_threads(int(os.environ.get("THREADS", 2)))
        m = UNet()
        m.load_state_dict(torch.load(E / "82_path_accuracy/out/learned/u1/model.pt", map_location="cpu")["model"])
        _M = m.eval()
    return _M


def glyph_program(font_path: Path, gid: int):
    """-> (strokes [dict(pts [[x,y,r0]...] em, mark)], ink mask, origin x) for one glyph."""
    import path82
    import synth79 as S
    from net82 import decode, predict
    font, gs, order, upm = S.load_font(font_path)
    name = order[gid]
    polys = S.glyph_polys(font_path, gs, name)
    if not polys:
        return [], None, 0
    s = PX / upm
    P = np.vstack(polys)
    x0, x1 = P[:, 0].min() * s, P[:, 0].max() * s
    ox = 16 - x0
    W = int(x1 - x0 + 32)
    ink = S.glyph_mask(polys, (HC, W), ox, BASE, s)
    if ink.sum() < 3:
        return [], ink, ox
    grey = cv2.GaussianBlur(np.where(ink, 25, 245).astype(np.uint8), (3, 3), 0.6)
    cl = decode(predict(model(), grey))
    dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
    res = []
    # the centre line: the network's inside the ink, joined into one line per piece; any ink piece the network left
    # without a line (a dot, a thin tail) gets its own thinned line, so every piece of ink has a program
    from sig79 import thin
    n, lab = cv2.connectedComponents(ink.astype(np.uint8), connectivity=8)
    area_max = max(1, max((lab == k).sum() for k in range(1, n))) if n > 1 else 1
    for k in range(1, n):
        mk = lab == k
        c = cl & mk
        if c.sum() < 3 or c.sum() < 0.5 * thin(mk.astype(np.uint8)).astype(bool).sum():
            c = thin(mk.astype(np.uint8)).astype(bool)
        else:
            c = thin((c | (thin(mk.astype(np.uint8)).astype(bool) & ~cv2.dilate(c.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool))).astype(np.uint8)).astype(bool)
        is_mark = mk.sum() < 0.12 * area_max and (np.nonzero(mk)[0].max() < BASE - 0.12 * PX or np.nonzero(mk)[0].min() > BASE + 0.05 * PX)
        for path in trace_edges(c):
            q = np.array(path, float)
            r = np.maximum(dt[q[:, 0].astype(int), q[:, 1].astype(int)], 0.8) / PX
            X = (q[:, 1] + 0.5 - ox) / PX
            Y = (BASE - q[:, 0] - 0.5) / PX
            P = np.column_stack([X, Y, r])
            if len(P) > 3:                      # light smoothing of the pixel staircase, ends kept
                Pm = P.copy()
                Pm[1:-1, :2] = (P[:-2, :2] + 2 * P[1:-1, :2] + P[2:, :2]) / 4
                P = Pm[::2] if len(Pm) > 6 else Pm
                if len(Pm) > 6 and not np.allclose(P[-1], Pm[-1]):
                    P = np.vstack([P, Pm[-1:]])
            res.append(dict(pts=np.round(P, 4).tolist(), mark=bool(is_mark)))
    return res, ink, ox


def trace_edges(sk: np.ndarray):
    """A 1-px skeleton -> its edges as ordered pixel paths [(y, x)...]: node to node (end points, junctions), and
    closed loops; each path runs right to left (its first point is its rightmost, ties: topmost) like a pen."""
    ys, xs = np.nonzero(sk)
    S = set(zip(ys.tolist(), xs.tolist()))
    nb = lambda p: [(p[0] + a, p[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a or b) and (p[0] + a, p[1] + b) in S]
    deg = {p: len(nb(p)) for p in S}
    nodes = {p for p, d in deg.items() if d != 2}
    seen = set()
    paths = []
    for n0 in sorted(nodes):
        for q in nb(n0):
            e = frozenset((n0, q))
            if e in seen:
                continue
            path, prev, cur = [n0], n0, q
            seen.add(e)
            while True:
                path.append(cur)
                if cur in nodes:
                    break
                nx = [r for r in nb(cur) if r != prev and frozenset((cur, r)) not in seen]
                if not nx:
                    break
                seen.add(frozenset((cur, nx[0])))
                prev, cur = cur, nx[0]
            paths.append(path)
    rest = S - {p for P in paths for p in P}
    while rest:                                              # loops with no node
        p0 = max(rest, key=lambda p: (p[1], -p[0]))
        path, prev, cur = [p0], None, p0
        while True:
            nx = [r for r in nb(cur) if r != prev and r in rest and r not in path]
            if not nx:
                break
            prev, cur = cur, nx[0]
            path.append(cur)
        path.append(p0)
        rest -= set(path)
        paths.append(path)
    if not paths and S:
        paths = [[p] for p in S]
    out = []
    for P in paths:
        a, b = P[0], P[-1]
        if (b[1], -b[0]) > (a[1], -a[0]):
            P = P[::-1]
        out.append(P)
    out.sort(key=lambda P: -max(p[1] for p in P))
    return out


def build(fonts):
    T = (PROG / "texts.txt").read_text(encoding="utf-8").split("\n")
    for font in fonts:
        fp = FONTS / font
        nm = name_of(font)
        dst = PROG / f"font_{nm}.json"
        if dst.exists():
            print("have", nm)
            continue
        if font.startswith("traced/"):
            e = EXCLUDE.get(Path(font).stem, {})
            bad = set(e.get("chars", "")) if isinstance(e, dict) else set()
            T2 = [t for t in T if not (set(t) & bad)]
        else:
            T2 = T
        gids = glyphs_used(fp, T2)
        G = {}
        for g in gids:
            strokes, _, _ = glyph_program(fp, g)
            G[g] = strokes
        meta = dict(font=font, name=nm, path=str(fp), licence=licence_of(font), px_per_em=PX, n_glyphs=len(G),
                    exclude=EXCLUDE.get(Path(font).stem) if font.startswith("traced/") else None, glyphs=G)
        dst.write_text(json.dumps(meta))
        print(nm, len(G), "glyphs", sum(len(v) for v in G.values()), "strokes", flush=True)


def look(nm: str):
    sys.path.insert(0, str(HERE))
    import torch
    torch.set_num_threads(2)
    import writer87 as W
    import synth79 as S
    d = json.loads((PROG / f"font_{nm}.json").read_text())
    rows = []
    for t in ["كان من توفيق الله على أن أغرمت بالرحلات", "لديها ثلاثة أبناء وجميعهم في المدرسة",
              "ظاهرة غريبة ضحك خفيف صوت شجرة"]:
        S.H = 110
        grey, _, ink = S.render(t, Path(d["path"]), px_per_em=56.0)
        g, inst, w = W.write_line(t, "font:" + nm, dict(size=56.0, x0=0.35 * 110 - 0.0), H=110)
        Wm = max(grey.shape[1], g.shape[1])
        pad = lambda a: np.hstack([np.full((a.shape[0], Wm - a.shape[1]), 255, np.uint8), a])
        rows += [pad(grey), pad(g), np.full((6, Wm), 200, np.uint8)]
    Wm = max(r.shape[1] for r in rows)
    img = np.vstack([np.hstack([np.full((r.shape[0], Wm - r.shape[1]), 255, np.uint8), r]) for r in rows])
    cv2.imwrite(str(OUT / f"look/font_{nm}.png"), img)
    print(OUT / f"look/font_{nm}.png")


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "texts":
        texts()
    elif c == "build":
        build(sys.argv[2:] or (MODERN + TRACED))
    elif c == "look":
        look(sys.argv[2])
