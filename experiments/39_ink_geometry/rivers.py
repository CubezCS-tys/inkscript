"""Rivers of paper: the white space that separates columns, paragraphs and blocks, found from the ink alone
(no model). Ink is smeared sideways so the words of a line join into one bar; the paper left between the bars
is the river system. Tall, thin rivers are column gutters; wide horizontal ones separate paragraphs or blocks;
the thin gaps between lines of one paragraph don't count. The islands of ink the rivers leave are the blocks.
-> out/rivers/<page>.jpg, out/rivers/summary.json"""
import json, sys
from pathlib import Path
import cv2, fitz, numpy as np
from inkscript.geometry.trace import render_gray

HERE = Path(__file__).parent; OUT = HERE / "out/rivers"; P38 = HERE.parent / "38_parser/out/pages"
FIX = HERE.parents[1] / "tests/fixtures/0582-004-009-012/input/0582-004-009-012.pdf"
PAGES = sys.argv[1:] or ["0582-004-009-012_p002", "0005-055-003-004_p008", "0737-001-020-003_p009", "0299-000-004-010_p002",
                         "0781-010-055-015_p006", "1865-000-143-005_p017", "0924-012-005-007_p002", "0460-009-003-012_p010",
                         "0266-006-002-001_p042", "0747-001-003-001_p006"]
DPI = 100  # coarse is enough for white space


def load(pid):
    if pid.startswith("0582-004-009-012"):
        return render_gray(fitz.open(FIX)[int(pid[-3:]) - 1], DPI)
    return render_gray(fitz.open(P38 / pid / "master" / f"{pid}.pdf")[0], DPI)


def rivers(gray):
    H, W = gray.shape
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] >= 3            # drop dust
    ink = (keep[lab] * 255).astype(np.uint8)
    # the scanner's dark page edge is not content: clear any ink touching the outer 1.5% of the page
    m = int(0.015 * min(H, W)); edge = np.zeros_like(ink); edge[:m] = edge[-m:] = 255; edge[:, :m] = edge[:, -m:] = 255
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    touch = np.unique(lab[(edge > 0) & (ink > 0)]); ink[np.isin(lab, touch[touch > 0])] = 0
    # x-height-ish unit from the ink: median height of the larger islands
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    hs = st[1:, cv2.CC_STAT_HEIGHT]; u = max(4, int(np.median(hs[hs >= np.percentile(hs, 50)]))) if len(hs) else 8
    # smear: words of one line join (a word space is under ~1.2 units), lines stay apart
    bars = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (int(1.6 * u), max(1, u // 3))))
    paper = bars == 0
    # column gutters: paper that stays open along a tall thin strip (at least 8 line-heights tall, 0.6 unit wide)
    v = cv2.morphologyEx(paper.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(2, int(0.6 * u)), 8 * u))) > 0
    # the page's normal gap between lines: vertical runs of paper with ink above and below, shorter than 4 units
    runs = []
    for x in range(0, W, max(1, u)):
        col = bars[:, x] > 0; ys = np.flatnonzero(np.diff(col.astype(np.int8)))
        for a, b in zip(ys[1::2], ys[2::2]):
            if 0 < b - a < 4 * u: runs.append(b - a)
    g = float(np.median(runs)) if runs else u
    # block gaps: paper open along a wide flat strip clearly taller than the normal line gap
    h = cv2.morphologyEx(paper.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (6 * u, max(int(1.1 * u), int(1.7 * g) + 1)))) > 0
    # ruled lines (header rules, table borders, footnote separators) are walls between blocks, like rivers
    k = max(20, int(0.12 * W)); rules = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, k), np.uint8))
    k = max(20, int(0.12 * H)); rules |= cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((k, 1), np.uint8))
    walls = cv2.dilate(rules, np.ones((3, 3), np.uint8)) > 0
    river = v | h | walls
    # blocks: what the rivers cut the ink into
    # lines of one block bridge their normal gaps; the rivers then cut the land into blocks
    land = cv2.morphologyEx((bars > 0).astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (u, int(1.7 * g) + 2)))
    land = land & (~cv2.dilate(river.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(land, connectivity=4)
    blocks = [tuple(int(t) for t in st[i, :4]) for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 2 * u * u]
    # the margins are paper outside the text area; they are rivers too but shown plainly
    ys, xs = np.nonzero(bars); inside = np.zeros_like(paper)
    if len(xs): inside[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = True
    return ink, bars, v & inside, h & inside, walls, blocks, u, g


rng = np.random.default_rng(3); OUT.mkdir(parents=True, exist_ok=True); summ = []
for pid in PAGES:
    gray = load(pid); ink, bars, v, h, walls, blocks, u, g = rivers(gray)
    base = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    # left: the scan with the rivers flooded in colour; right: the blocks the rivers leave
    a = base.copy(); over = a.copy()
    over[h & ~v] = (235, 160, 40)      # horizontal rivers: blue
    over[v] = (40, 60, 230)            # column gutters: red
    over[walls] = (30, 170, 30)        # ruled lines: green
    a = cv2.addWeighted(over, 0.55, a, 0.45, 0); a[ink > 0] = (20, 20, 20)
    b = np.full_like(base, 255); b[bars > 0] = (215, 215, 215); b[ink > 0] = (120, 120, 120)
    for (x, y, w, hh) in blocks:
        col = tuple(int(c) for c in rng.integers(40, 200, 3))
        cv2.rectangle(b, (x, y), (x + w, y + hh), col, 3)
    gap = np.full((base.shape[0], 12, 3), 160, np.uint8)
    cv2.imwrite(str(OUT / f"{pid}.jpg"), np.hstack([base, gap, a, gap, b]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    summ.append(dict(page=pid, unit_px=u, line_gap_px=round(g, 1), blocks=len(blocks), gutter_share=round(float(v.mean()), 4)))
    print(summ[-1], flush=True)
json.dump(summ, open(OUT / "summary.json", "w"), indent=1)
