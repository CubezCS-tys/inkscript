"""Judge stacked letters' highlights before (a full-height band over today's cell: what Chromium draws today) and
after (the same cell, only as tall as the letter's own ink: what Chromium draws with the letter in its own font),
with experiment 18's judge: same model, same two questions (graded, blind), same crop, temperature 0, 8 crops a
request, items of both methods shuffled together, ids that do not name the method.

One change, needed because a highlight can now be shorter than the word: the box is tinted over its own rows (for
the before boxes: the word's full height, as 18 drew it), and both prompts say "a region" instead of "a vertical
band". To keep the comparison paired, the before boxes are asked again with the changed prompt (versions :r2 / :r3,
cached separately from 18's :b2 / :b3); 18/21's own verdicts for the same boxes are kept for comparison.

    ../../.venv/bin/python judge23.py [--dry]        cap $8 (out/spend.jsonl)
"""
import sys, json
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; E18 = HERE.parent / "18_boxes"; E21 = HERE.parent / "21_better_boxes"
sys.path.insert(0, str(E18))
import judge18 as J, run18 as R

OUT = HERE / "out"
J.CACHE = OUT / "judge_cache.jsonl"; J.SPEND = OUT / "spend.jsonl"; J.CAP = 8.0
J.VERSIONS = {"graded": ":r2", "blind": ":r3"}

J.PROMPT = J.PROMPT.replace("Inside that word, a vertical band of the paper is tinted LIGHT BLUE — the highlight.",
                            "Inside that word, a rectangular region of the paper is tinted LIGHT BLUE — the highlight. It may run the word's full height or cover only part of it (a letter written above or below another).").replace("the blue band", "the blue region").replace("the band", "the region")
J.PROMPT_BLIND = J.PROMPT_BLIND.replace("Inside that word, a vertical band of the paper is tinted LIGHT BLUE — the highlight.",
                                        "Inside that word, a rectangular region of the paper is tinted LIGHT BLUE — the highlight. It may run the word's full height or cover only part of it (a letter written above or below another).").replace("the blue band", "the blue region").replace("the band", "the region")
assert "vertical band" not in J.PROMPT and "vertical band" not in J.PROMPT_BLIND


def crop(gray, word_box, cell, ys=None, side=1.6, target_h=110):
    """18's crop; the box is tinted over rows ys (scan px) when given, else over the word's height as in 18."""
    x0, y0, x1, y1 = word_box; h = max(20, y1 - y0); H, W = gray.shape
    top = min(y0, ys[0]) if ys else y0; bot = max(y1, ys[1]) if ys else y1
    cx0, cx1 = max(0, int(x0 - side * h)), min(W, int(x1 + side * h)); cy0, cy1 = max(0, int(top - 0.22 * h)), min(H, int(bot + 0.22 * h))
    g = gray[cy0:cy1, cx0:cx1]; img = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR).astype(np.float32)
    paper = (g.astype(np.float32) / 255.0)[..., None]
    p = max(3, int(0.12 * h)); yy0, yy1 = max(0, y0 - cy0 - p), min(g.shape[0], y1 - cy0 + p)

    def tint(xa, xb, ya, yb, colour, a=0.9):
        xa, xb = max(0, int(round(xa - cx0))), min(g.shape[1], int(round(xb - cx0)))
        if xb <= xa or yb <= ya: return
        sl = (slice(ya, yb), slice(xa, xb)); pp = paper[sl]
        img[sl] = img[sl] * (1 - a * pp) + np.array(colour, np.float32) * a * pp
    tint(x0 - p, x1 + p, yy0, yy1, (150, 240, 255))
    if ys: by0, by1 = max(0, int(round(ys[0] - cy0))), min(g.shape[0], int(round(ys[1] - cy0)))
    else: by0, by1 = yy0, yy1
    tint(cell[0], cell[1], by0, by1, (255, 200, 120), 0.95)
    img = np.clip(img, 0, 255).astype(np.uint8)
    s = target_h / h
    if s > 1.05: img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    return img


def item_image(it):
    return crop(J.J17.page_image(J.scan_of(it["doc"]), it["page"]), it["box"], it["cell"], it.get("ys"))


J.item_image = item_image


def items():
    """Stacked letters of 18's samples: before (21's after-build cell, full height) and after (same cell, own height)."""
    S = json.load(open(E18 / "out/sample.json")); Bx = json.load(open(OUT / "boxes_cell.json")); out = []; ref = {}
    for s, ws in S.items():
        for w in ws:
            b = Bx.get(R.wid(w))
            if not b: continue
            for k, (cell, ys) in enumerate(zip(b["cells"], b["ys"]), 1):
                if not ys: continue
                a, bb = int(round(cell[0])), int(round(cell[1])); y0, y1 = int(round(ys[0])), int(round(ys[1]))
                base = dict(doc=w["doc"], page=w["page"], box=w["box"], cell=[a, bb], letters=list(w["text"]), k=k)
                i0 = f"{R.wid(w)}-{k}-{a}-{bb}"; i1 = f"{i0}-y{y0}-{y1}"
                out += [dict(base, id=i0), dict(base, id=i1, ys=[y0, y1])]
                ref[(s, R.wid(w), k)] = (i0, i1)
    return out, ref


if __name__ == "__main__":
    its, ref = items(); done = J.cached(R.MODEL)
    todo = [it for it in its if not (it["id"] + ":r2" in done and it["id"] + ":r3" in done)]
    print(f"{len(ref)} stacked letters, {len(its)} items, {len(todo)} to ask; estimate ~${len(todo) * 0.0028:.2f} both questions; spent so far ${J.spent():.3f}")
    if "--sheet" in sys.argv:
        tiles = [item_image(it) for it in its[:24]]; h = 120
        tiles = [cv2.resize(t, (int(t.shape[1] * h / t.shape[0]), h)) for t in tiles]
        rows = [np.hstack(tiles[i:i + 2] if len(tiles[i:i + 2]) == 2 else [tiles[i], np.full_like(tiles[i], 255)]) for i in range(0, len(tiles), 2)]
        W = max(r.shape[1] for r in rows); cv2.imwrite(str(OUT / "judge_sheet.png"), np.vstack([cv2.copyMakeBorder(r, 3, 3, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]))
    if "--dry" in sys.argv: sys.exit()
    for mode in ("graded", "blind"):
        J.judge(todo, R.MODEL, tag=f"e23-{mode}", mode=mode, max_usd=min(3.0, 7.5 - J.spent()))
    print("spent", J.spent())
