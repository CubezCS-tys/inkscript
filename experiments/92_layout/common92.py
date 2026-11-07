"""Experiment 92 (layout, stage 1): shared pieces.

Paths, the locked-test guard, Argon's per-page structure (blocks in reading order over Azure's `p:i` line ids),
Azure's lines and paragraphs, page renders, the coarse label set of experiment 39's layout model, box geometry and a
right-to-left recursive XY-cut reading order.  Standard library + numpy (+ cv2 / pypdfium2 where a function says so).
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parent
OUT = HERE / "out"
sys.path.insert(0, str(E / "88_truth_and_lock"))
from locked_old import assert_not_locked, is_locked_any  # noqa: E402,F401  (both locked tests: exp 84 + exp 88)

SPLIT = E / "76_finetune_pilot/out/split76.json"
INV = E / "76_finetune_pilot/out/inventory76.jsonl"
Y39 = E / "39_ink_geometry"
WEIGHTS = {"r1": Y39 / "out/gpu/out/run/weights/best.pt", "r2": Y39 / "out/gpu2/out/run/weights/best.pt"}
LABELS = ["furniture", "heading", "body", "list", "verse", "footnote", "references", "caption", "table", "equation",
          "other"]                                           # experiment 39's classes, in its index order
# Argon block type -> experiment 39's label (as experiment 41's COARSE, with the types Argon added later)
COARSE = {"title": "heading", "heading": "heading", "byline": "heading", "paragraph": "body", "quote": "body",
          "abstract": "body", "keywords": "body", "boxed": "body", "list_item": "list", "reference": "references",
          "endnote": "references", "footnote": "footnote", "verse": "verse", "table": "table", "equation": "equation",
          "caption": "caption", "figure": "other", "other": "other", "other_article": "other", "scoped_box": "other",
          "header": "furniture", "footer": "furniture"}
DPI = 250
LID = re.compile(r"(\d+):(\d+)")


def heldout_codes() -> set[str]:
    return set(json.loads(SPLIT.read_text())["test"])


def era_of(year) -> str:
    try:
        y = int(str(year)[:4])
    except (TypeError, ValueError):
        return "unknown"
    return "pre-1950" if y < 1950 else ("1950-1999" if y < 2000 else "2000+")


def fixpath(p) -> Path:
    return Path(str(p).replace("/home/yassine/", "/home/appuser/"))


# ------------------------------------------------------------------------------------------------ Argon

ARGON_SETS = [("v2_55", E / "43_rehearsal/out/v2_55/raw"), ("v33_300", E / "43_rehearsal/out/v33_300/raw"),
              ("v33_300b", E / "43_rehearsal/out/v33_300b/raw"), ("j0097", E / "74_gate2_full/out/0097/j0097/raw")]


def _block_lines(b: dict) -> list[str]:
    """The line ids of one Argon block in its printed order (table cells row by row, verse half-lines)."""
    ids = []
    if b.get("type") == "table":
        for row in b.get("rows") or []:
            for cell in row or []:
                ids += (cell or {}).get("lines") or [] if isinstance(cell, dict) else []
    elif b.get("type") == "verse":
        for h in b.get("hemistichs") or []:
            ids += h if isinstance(h, list) else [h]
    for k in ("lines", " lines"):
        ids += b.get(k) or []
    if b.get("type") == "scoped_box":
        for bb in b.get("blocks") or []:
            ids += _block_lines(bb)
    return [x for x in ids if isinstance(x, str)]


def argon_pages(raw_dir: Path, stem: str) -> dict[int, list[dict]]:
    """{page: [{type, coarse, level, ids: [i, ...] (Azure non-empty line numbers, in order)}]} for one article."""
    out = {}
    for f in sorted(raw_dir.glob(f"{stem}_c*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        ans = d.get("answer")
        if not isinstance(ans, dict):
            continue
        for pg in ans.get("pages") or []:
            p = pg.get("page")
            if not isinstance(p, int):
                continue
            blocks = []
            for b in pg.get("blocks") or []:
                if not isinstance(b, dict):
                    continue
                T = str(b.get("type", "other")).strip()
                ids = []
                for x in _block_lines(b):
                    m = LID.match(x)
                    if m and int(m.group(1)) == p:
                        ids.append(int(m.group(2)))
                blocks.append(dict(type=T, coarse=COARSE.get(T, "other"), level=b.get("level"), ids=ids))
            out[p] = blocks
    return out


# ------------------------------------------------------------------------------------------------ Azure

@lru_cache(maxsize=64)
def azure_result(path: str) -> dict:
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    return r.get("analyzeResult", r)


def azure_lines(path: str, p: int) -> tuple[list[dict], float, float]:
    """Azure's non-empty lines of page p (1-based), numbered 1.. as experiments 41/43/76 do: [{i, text, poly (page
    units), box [x0,y0,x1,y1] (page units), span}], page width, page height (page units)."""
    r = azure_result(str(path))
    pg = r["pages"][p - 1]
    out = []
    for ln in pg.get("lines", []):
        t = (ln.get("content") or "").strip()
        if not t or not ln.get("polygon"):
            if t:
                out.append(dict(i=len(out) + 1, text=t, poly=None, box=None, span=None))
            continue
        xs, ys = ln["polygon"][0::2], ln["polygon"][1::2]
        sp = (ln.get("spans") or [{}])[0]
        out.append(dict(i=len(out) + 1, text=t, poly=ln["polygon"], box=[min(xs), min(ys), max(xs), max(ys)],
                        span=(sp.get("offset"), sp.get("length"))))
    return out, pg["width"], pg["height"]


def azure_paragraph_of(path: str, p: int, lines: list[dict]) -> dict[int, tuple[int, str | None]]:
    """{line i: (paragraph index in Azure's order, role)} from span containment (prebuilt-read: role is mostly None,
    sometimes 'title')."""
    r = azure_result(str(path))
    paras = []
    for k, pa in enumerate(r.get("paragraphs") or []):
        br = pa.get("boundingRegions") or []
        if not any(b.get("pageNumber") == p for b in br):
            continue
        for sp in pa.get("spans") or []:
            paras.append((sp["offset"], sp["offset"] + sp["length"], k, pa.get("role")))
    out = {}
    for ln in lines:
        if not ln["span"] or ln["span"][0] is None:
            continue
        o = ln["span"][0]
        for a, b, k, role in paras:
            if a <= o < b:
                out[ln["i"]] = (k, role)
                break
    return out


# ------------------------------------------------------------------------------------------------ render

def render_gray(pdf_path: str, p: int, dpi: int = DPI):
    """Grey uint8 render of page p (1-based) with pypdfium2 5.12.1, as experiments 77/81/89 render."""
    import numpy as np
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        bm = pdf[p - 1].render(scale=dpi / 72, grayscale=True)
        a = bm.to_numpy()
        if a.ndim == 3:
            a = a[..., 0]
        return np.ascontiguousarray(a)
    finally:
        pdf.close()


# ------------------------------------------------------------------------------------------------ geometry

def area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def inter(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def iou(a, b) -> float:
    i = inter(a, b)
    return i / max(1e-9, area(a) + area(b) - i)


def xycut_order(boxes: list[list[float]], rtl: bool = True) -> list[int]:
    """Reading order of boxes (any units) for a right-to-left page: recursive XY-cut.  At each level the group is cut
    once, at its widest white gap: a horizontal band (read top to bottom) or a vertical gutter (read right to left);
    a gap counts when it is at least 0.3 (horizontal) or 0.5 (vertical) of the median box height.  With no gap left,
    top to bottom by centre, then right to left.  rtl=False: the same for a left-to-right page (columns left first)."""
    import numpy as np
    if not boxes:
        return []
    B = np.array(boxes, dtype=float)
    mh = float(np.median(np.maximum(1e-6, B[:, 3] - B[:, 1])))

    def widest_gap(ix, a, b):
        iv = sorted((B[i, a], B[i, b]) for i in ix)
        best, end = None, iv[0][1]
        for lo, hi in iv[1:]:
            if lo > end and (best is None or lo - end > best[1] - best[0]):
                best = (end, lo)
            end = max(end, hi)
        return best

    def rec(ix):
        if len(ix) <= 1:
            return ix
        h = widest_gap(ix, 1, 3)
        v = widest_gap(ix, 0, 2)
        hw = (h[1] - h[0]) / mh if h else 0
        vw = (v[1] - v[0]) / mh if v else 0
        if h and hw >= 0.3 and (hw >= vw or vw < 0.5):
            c = (h[0] + h[1]) / 2
            top = [i for i in ix if (B[i, 1] + B[i, 3]) / 2 < c]
            bot = [i for i in ix if (B[i, 1] + B[i, 3]) / 2 >= c]
            if top and bot:
                return rec(top) + rec(bot)
        if v and vw >= 0.5:
            c = (v[0] + v[1]) / 2
            right = [i for i in ix if (B[i, 0] + B[i, 2]) / 2 >= c]
            left = [i for i in ix if (B[i, 0] + B[i, 2]) / 2 < c]
            if right and left:
                return rec(right) + rec(left) if rtl else rec(left) + rec(right)
        return sorted(ix, key=lambda i: ((B[i, 1] + B[i, 3]) / 2, -B[i, 2] if rtl else B[i, 0]))

    return rec(list(range(len(boxes))))


def kendall_tau(x: list[float], y: list[float]) -> float | None:
    """Kendall tau-b between two rankings of the same items (None for fewer than 2 items or no variation)."""
    n = len(x)
    if n < 2:
        return None
    c = d = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b = x[i] - x[j], y[i] - y[j]
            if a == 0 and b == 0:
                continue
            if a == 0:
                tx += 1
            elif b == 0:
                ty += 1
            elif (a > 0) == (b > 0):
                c += 1
            else:
                d += 1
    den = ((c + d + tx) * (c + d + ty)) ** 0.5
    return (c - d) / den if den else None


def page_is_rtl(texts) -> bool:
    """A page reads right to left unless its Latin letters outnumber its Arabic ones."""
    t = " ".join(texts)
    ar = len(re.findall("[\u0620-\u064A\u0671-\u06D3\u06FA-\u06FF]", t))
    la = len(re.findall("[A-Za-z\u00C0-\u024F]", t))
    return ar >= la
