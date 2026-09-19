"""The document's own letters as the reference. Every letter cut along the pen path is drawn on a common
canvas (scaled by its line's rise, its baseline on a fixed row); the pixel-wise median of a letter-form's
examples is that form's reference shape; each cut letter is then scored against its reference, and a piece
by its worst letter. Sheets: the atlas, the worst-scoring pieces, the best-scoring pieces.

    python atlas.py <azure.json> <scan.pdf> <pages> <out_prefix>
"""
import sys
from collections import defaultdict
import numpy as np, cv2, fitz
from penpath import collect, COLS, picture
from inkscript.geometry.letters import form, _base

C = 72; BASE = 46; RISE = 26                                          # canvas, baseline row, pixels per line rise
FONT = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"


def letter_masks(g):
    F, G, n = g["F"], g["G"], g["n"]; bounds = [0] + list(g["cuts"]) + [G["W"]]; out = []
    for k in range(n):
        a, b = bounds[n - 1 - k], bounds[n - k]; m = (g["ink_s"] >= a) & (g["ink_s"] < b)
        for (s, above), lab_id in zip(G["dots"], F["dot_labels"]):
            if a <= s < b: m |= F["lab"] == lab_id
        out.append(m)
    return out


def canvas(m, g):
    ys, xs = np.where(m)
    if len(xs) < 4: return None
    sc = RISE / g["line"]["rise"]; base = g["line"]["baseline"] - g["off"][1]; cx = (xs.min() + xs.max()) / 2
    M = np.float32([[sc, 0, C / 2 - sc * cx], [0, sc, BASE - sc * base]])
    return cv2.warpAffine(m.astype(np.float32), M, (C, C), flags=cv2.INTER_AREA)


def score(img, ref):
    best = 0.0
    for dx in range(-4, 5):
        for dy in (-2, 0, 2):
            sh = cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (C, C))
            best = max(best, float(np.minimum(sh, ref).sum() / max(1e-6, np.maximum(sh, ref).sum())))
    return best


def label(text, h=C):
    d = fitz.open(); p = d.new_page(width=C, height=24); p.insert_text((4, 17), text.split()[0], fontfile=FONT, fontname="ar", fontsize=13); p.insert_text((22, 16), " ".join(text.split()[1:]), fontsize=9)
    pm = p.get_pixmap(dpi=72, colorspace=fitz.csRGB); return np.frombuffer(pm.samples, np.uint8).reshape(pm.h, pm.w, 3)[:, :C].copy()


def sheet(tiles, path, width=2400):
    h = max(t.shape[0] for t in tiles); rows = []; row = []; ws = 0
    for t in tiles:
        t = cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        if ws + t.shape[1] > width and row: rows.append(np.hstack(row)); row = []; ws = 0
        row.append(t); ws += t.shape[1]
    if row: rows.append(np.hstack(row))
    wm = max(r.shape[1] for r in rows); cv2.imwrite(path, np.vstack([cv2.copyMakeBorder(r, 0, 0, 0, wm - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]))


def main(azure, scan, pages, prefix):
    got, tried = collect(azure, scan, pages); ex = defaultdict(list)
    for g in got:
        g["imgs"] = [canvas(m, g) for m in letter_masks(g)]
        for k, im in enumerate(g["imgs"]):
            if im is not None: ex[(_base(g["units"][k]), form(k, g["n"]))].append(im)
    ref = {key: np.median(np.stack(v), 0) for key, v in ex.items() if len(v) >= 5}
    for rnd in range(2):                                              # second round: references from the examples that agree with the first
        sc_all = {}
        for g in got:
            g["scores"] = [score(im, ref[key]) if im is not None and (key := (_base(g["units"][k]), form(k, g["n"]))) in ref else None for k, im in enumerate(g["imgs"])]
        if rnd == 0:
            keep = defaultdict(list)
            for g in got:
                for k, (im, s) in enumerate(zip(g["imgs"], g["scores"])):
                    if s is not None and s >= 0.5: keep[(_base(g["units"][k]), form(k, g["n"]))].append(im)
            ref = {key: np.median(np.stack(v), 0) if len(v) >= 5 else ref[key] for key in ref for v in [keep.get(key, [])]}
    judged = [g for g in got if all(s is not None for s in g["scores"])]
    for g in judged: g["worst"] = min(g["scores"])
    judged.sort(key=lambda g: g["worst"]); ws = np.array([g["worst"] for g in judged])
    print(f"pieces cut: {len(got)} of {tried}; letter-forms with a reference: {len(ref)}; pieces every letter of which has one: {len(judged)}")
    print("worst-letter score, share of pieces: " + ", ".join(f"<{t}: {100 * np.mean(ws < t):.0f}%" for t in (0.3, 0.4, 0.5, 0.6)))
    tiles = []
    for key in sorted(ref, key=lambda k: (k[0], ["iso", "init", "med", "fin"].index(k[1]))):
        im = cv2.cvtColor((255 - np.clip(ref[key], 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR); cv2.line(im, (0, BASE), (C, BASE), (200, 220, 255), 1)
        lab = label(f"{key[0]} {key[1]} {len(ex[key])}"); tiles.append(cv2.copyMakeBorder(np.vstack([lab, im]), 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(225, 225, 225)))
    sheet([cv2.resize(t, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC) for t in tiles], prefix + "_atlas.png")

    def tile(g):
        im = picture(g["F"], g["ink_s"], g["cuts"], g["G"], g["n"], up=4); cv2.putText(im, f"{g['worst']:.2f}", (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        return cv2.copyMakeBorder(im, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    sheet([tile(g) for g in judged[:60]], prefix + "_worst.png"); sheet([tile(g) for g in judged[-60:]], prefix + "_best.png")
    for rank, g in enumerate(judged):
        if g["text"] in ("لعين", "تنظيم"): print(g["text"], "page", g["page"], [round(s, 2) for s in g["scores"]], "rank", rank, "of", len(judged))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], [int(p) for p in sys.argv[3].split(",")], sys.argv[4])
