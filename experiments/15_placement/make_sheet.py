"""Milestone 2: do the letter boxes sit on the right letters? Judged blind, against the free baseline.

    python make_sheet.py <built_dir> <stem> --page 2 [--azure DIR] [--scan DIR] [--limit 120]

Coverage says 97.8% of words have a box per letter. It does NOT say the boxes sit right, and the one proxy
measurement (experiments/09_pen_path/vs_equal.py) tied with equal slicing. This asks a reader instead.

Each row shows the SAME word twice, tinted band by band the way Chrome highlights a letter: once cut along the
pen path, once sliced into equal parts — the free baseline every method must beat (docs/decisions.md, D7).
Which is which is decided by a coin flip per word and not shown, so the judgement is blind. The answer is
recorded against the true identity only in the exported file.

One keypress a word: left better, right better, the same, or both wrong.
"""
from __future__ import annotations
import argparse, base64, json, random, re, sys, unicodedata
from pathlib import Path
import numpy as np, cv2, fitz, pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from inkscript.text import MARKS
DPI = 300
LIG = ("لا", "لأ", "لإ", "لآ")
BANDS = [(70, 130, 220), (235, 150, 40)]          # two tints, alternating, so neighbours are told apart


def n_letters(t: str) -> int:
    t = MARKS.sub("", t); t = re.sub(r"[^؀-ۿ]", "", t)
    for l in LIG: t = t.replace(l, "L")
    return len(t)


def png(a, target_h=110) -> str:
    """Scaled up to a readable height: a body word is ~70 px tall at 300 dpi, too small on screen to see
    whether a band's edge falls on a join or through a letter."""
    if a.shape[0] and a.shape[0] < target_h:
        f = min(3.0, target_h / a.shape[0])
        a = cv2.resize(a, (int(a.shape[1] * f), int(a.shape[0] * f)), interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def tint(gray_crop, edges, x0):
    """The word's ink with each letter's cell tinted — what a drag-select would cover."""
    im = cv2.cvtColor(gray_crop, cv2.COLOR_GRAY2BGR).astype(np.float32)
    H, W = gray_crop.shape
    for k in range(len(edges) - 1):
        a = int(round(edges[k] - x0)); b = int(round(edges[k + 1] - x0))
        a, b = max(0, min(W, a)), max(0, min(W, b))
        if b <= a:
            continue
        col = np.array(BANDS[k % 2], np.float32)
        im[:, a:b] = im[:, a:b] * 0.62 + col * 0.38
    return im.astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("built"); ap.add_argument("stem")
    ap.add_argument("--page", type=int, default=0, help="0 = every page")
    ap.add_argument("--azure", default=str(Path.home() / "Desktop/OCR_gem_json/output/s3_night/azure"))
    ap.add_argument("--scan", default=None)
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    built = Path(a.built); stem = a.stem
    shapes = json.load(open(built / f"{stem}.shapes.json"))
    scan = (Path(a.scan) / f"{stem}.pdf") if a.scan else (Path(a.azure) / stem / f"{stem}.pdf")
    pages = sorted({p["page"] for p in shapes["placements"]}) if not a.page else [a.page]
    rng = random.Random(a.seed)
    rows = []
    for pn in pages:
        place = [p for p in shapes["placements"] if p["page"] == pn and not p.get("rot")]
        if not place:
            continue
        src = fitz.open(scan)
        pix = src[pn - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()
        src.close()
        d = pdfium.PdfDocument(str(built / f"{stem}_vector.pdf")); pg = d[pn - 1]
        _, Hpt = pg.get_size(); tp = pg.get_textpage(); t = tp.get_text_range()
        cb = [tp.get_charbox(i) for i in range(len(t))]
        tp.close(); pg.close(); d.close()
        s = DPI / 72.0
        words = []; cur = []
        for i, c in enumerate(t):
            if c.isspace():
                if cur: words.append(cur); cur = []
            else: cur.append(i)
        if cur: words.append(cur)
        by_text = {}
        for w in words:
            # char -> its own box, taken together, so a band can be labelled with the letter it claims
            cells = sorted([(cb[i][0] * s, cb[i][2] * s, t[i]) for i in w])
            by_text.setdefault("".join(t[i] for i in w), []).append(cells)

        for p in place:
            txt = p["text"].strip()
            n = n_letters(txt)
            if n < 3 or MARKS.search(txt) or txt not in by_text:
                continue
            cands = [b for b in by_text[txt] if len(b) == n]
            if len(cands) != 1:
                continue                                    # cannot pair this word unambiguously
            cells = cands[0]
            x0, y0, x1, y1 = p["box"]
            if x1 - x0 < 20 or y1 - y0 < 12:
                continue
            crop = gray[y0:y1, x0:x1]
            mine = [cells[0][0]] + [(cells[k][1] + cells[k + 1][0]) / 2 for k in range(len(cells) - 1)] + [cells[-1][1]]
            equal = [x0 + (x1 - x0) * k / n for k in range(n + 1)]
            ours_img, eq_img = tint(crop, mine, x0), tint(crop, equal, x0)
            flip = rng.random() < 0.5                       # which pane holds which, hidden from the reader
            # the letters each band claims, in the order the bands appear on the page (left to right), so a
            # label can sit over its own band; the reading order is right to left, hence the reversal
            span = max(1e-6, mine[-1] - mine[0])
            ours_cells = [dict(ch=c[2], w=round(100 * (mine[k + 1] - mine[k]) / span, 3))
                          for k, c in enumerate(cells)]
            letters_rtl = [c[2] for c in cells][::-1]
            eq_cells = [dict(ch=ch, w=round(100 / n, 3)) for ch in letters_rtl[::-1]]
            rows.append(dict(i=len(rows), text=txt, page=pn, box=[x0, y0, x1, y1], letters=n,
                             left=png(eq_img if flip else ours_img),
                             right=png(ours_img if flip else eq_img),
                             left_cells=(eq_cells if flip else ours_cells),
                             right_cells=(ours_cells if flip else eq_cells),
                             ours="right" if flip else "left"))
        del gray
        if len(rows) >= a.limit:
            break
    rng.shuffle(rows)
    rows = rows[:a.limit]
    for k, r in enumerate(rows): r["i"] = k

    out = Path(a.out) if a.out else Path(__file__).parent / "out" / f"{stem}_placement.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    tpl = (Path(__file__).parent / "sheet.html").read_text(encoding="utf-8")
    out.write_text(tpl.replace("__DATA__", json.dumps(dict(stem=stem, seed=a.seed, words=rows), ensure_ascii=False))
                      .replace("__TITLE__", f"{stem} · which cut is better?"), encoding="utf-8")
    print(f"{len(rows)} words -> {out.resolve()}")
    print(f"  serve it:  python3 -m http.server 8734 --bind 127.0.0.1 --directory {out.parent.resolve()}")
    print(f"  then open: http://127.0.0.1:8734/{out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
