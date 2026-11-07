"""Experiment 78: shared pieces, copied unchanged from experiment 77 (common77.py, 2026-11-04) so that crops, labels and the right-to-left mapping are identical.  Experiment 77's header follows.

Standard library + numpy + cv2 + pypdfium2 (the repo venv).  The GPU host only needs `rtl.py`-style functions, which
are duplicated in train77.py so that file runs on its own there.
"""
from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parent
OUT = HERE / "out"
OUT77 = E / "77_scratch_reader/out"
sys.path.insert(0, str(ROOT / "src"))

INV = E / "76_finetune_pilot/out/inventory76.jsonl"
SPLIT = E / "76_finetune_pilot/out/split76.json"

H = 48              # crop height in pixels (the text band after padding)
DPI = 250           # page render resolution
PAD_V = 0.22        # padding above and below, as a share of the line's polygon height (dots and marks)
PAD_H = 0.35        # padding left and right, as a share of the line's polygon height
MAX_W = 2400        # crops wider than this (after scaling to H) are dropped


def fixpath(p: str) -> Path:
    return Path(str(p).replace("/home/yassine/", "/home/appuser/"))


def test_codes() -> set[str]:
    return set(json.loads(SPLIT.read_text())["test"])


def azure_pages(f: Path) -> list[dict]:
    r = json.loads(Path(f).read_text(encoding="utf-8"))
    return r.get("analyzeResult", r)["pages"]


def nonempty_lines(pg: dict) -> list[dict]:
    """Azure's non-empty lines of a page, numbered 1.. in Azure's order (the `p:i` ids of experiments 41/43/76)."""
    out = []
    for ln in pg.get("lines", []):
        t = (ln.get("content") or "").strip()
        if t:
            out.append(dict(i=len(out) + 1, text=t, poly=ln.get("polygon")))
    return out


# ------------------------------------------------------------------------------------------------ labels

_PRES = re.compile("[ﭐ-﷿ﹰ-ﻼ]")
_WS = re.compile(r"\s+")


def clean_label(s: str) -> str:
    """The training label: Azure's line in the scorer's `faithful` form (NFC, presentation forms decomposed,
    tatweel removed, whitespace collapsed).  Marks, hamza, ى/ي, digits and punctuation are kept as Azure gives them."""
    s = unicodedata.normalize("NFC", s or "")
    if _PRES.search(s):
        s = _PRES.sub(lambda m: unicodedata.normalize("NFKC", m.group()) if m.group() != "ﷺ" else m.group(), s)
    s = s.replace("ـ", "")
    return _WS.sub(" ", s).strip()


# Right-to-left.  The crop is flipped left-right before it reaches the network, so the network reads the line from
# its right edge to its left edge, i.e. in Arabic logical order.  Runs that are printed left-to-right inside an Arabic
# line appear reversed in that scan, so the TARGET reverses exactly those runs (an approximation of the Unicode bidi
# algorithm, enough for print):
#   - a Latin run: from a Latin letter to the last Latin letter or digit before the next Arabic letter
#     ("SPSS 22", "Journal of Education");
#   - a number: digits joined by . , : / - (no spaces), with a trailing % ("2023/11/04", "3.5", "50%", "١٩٣٧").
# A line with no Arabic letter at all is a left-to-right line: its target is simply reversed.
# Spaces between two numbers are NOT joined: the bidi algorithm lays "1998، 2001" or "12 34" out right to left.
# Decoding is from_visual(v) = reverse(to_visual(reverse(v))); tested to round-trip on the training labels.
_LAT = "A-Za-z\u00C0-\u024F"
_DIG = "0-9\u0660-\u0669\u06F0-\u06F9"
_RUNS = re.compile(rf"[{_LAT}](?:[^\u0600-\u06FF\n]*[{_LAT}{_DIG}])?|%?[{_DIG}]+(?:[.,:/\-\u066B\u066C][{_DIG}]+)*%?")
_ARABIC = re.compile("[\u0620-\u064A\u0671-\u06D3\u06FA-\u06FF]")


def to_visual(s: str) -> str:
    if not _ARABIC.search(s):          # no Arabic letter: a left-to-right line, read whole from its right end
        return s[::-1]
    return _RUNS.sub(lambda m: m.group()[::-1], s)


def from_visual(v: str) -> str:
    return to_visual(v[::-1])[::-1]


# ------------------------------------------------------------------------------------------------ crops

def render_page(pdf, page_index: int, dpi: int = DPI) -> np.ndarray:
    """Grey uint8 render of one PDF page (pypdfium2 5.12.1, as the lab renders)."""
    page = pdf[page_index]
    bm = page.render(scale=dpi / 72, grayscale=True)
    a = bm.to_numpy()
    if a.ndim == 3:
        a = a[..., 0]
    return np.ascontiguousarray(a)


def line_geometry(poly: list[float], sx: float, sy: float):
    """(centre, angle in radians, width, height) in pixels of Azure's 4-point line polygon (TL, TR, BR, BL)."""
    p = np.array(poly[:8], dtype=np.float64).reshape(4, 2) * [sx, sy]
    top, bot = p[1] - p[0], p[2] - p[3]
    ang = math.atan2(top[1] + bot[1], top[0] + bot[0])
    w = (np.linalg.norm(top) + np.linalg.norm(bot)) / 2
    h = (np.linalg.norm(p[3] - p[0]) + np.linalg.norm(p[2] - p[1])) / 2
    c = p.mean(axis=0)
    return c, ang, w, h


def cut_line(img: np.ndarray, poly: list[float], sx: float, sy: float, H: int = H, test: bool = False):
    """Cut one line: rotate the polygon's box upright, pad it (PAD_V above/below, PAD_H at the ends), scale to height
    H.  Returns (uint8 crop or None, info).  test=True: never drop a line for its angle or width."""
    import cv2
    c, ang, w, h = line_geometry(poly, sx, sy)
    if h < 6 or w < 4:
        return None, dict(reason="tiny", h=h, w=w)
    if abs(ang) > math.radians(8) and not test:        # test lines are all cut (no line is dropped from a test)
        return None, dict(reason="rotated", ang=math.degrees(ang))
    ph, pw = h * (1 + 2 * PAD_V), w + 2 * PAD_H * h
    s = H / ph
    W = int(round(pw * s))
    if W > MAX_W and not test:
        return None, dict(reason="too wide", W=W)
    if W < 8:
        return None, dict(reason="too narrow", W=W)
    ca, sa = math.cos(ang), math.sin(ang)
    # destination (u, v) -> source: x = c + R(ang) * ((u - W/2)/s, (v - H/2)/s)
    M = np.array([[ca / s, -sa / s, 0], [sa / s, ca / s, 0]], dtype=np.float64)
    M[:, 2] = c - M[:, :2] @ np.array([W / 2, H / 2])
    crop = cv2.warpAffine(img, M, (W, H), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    return crop, dict(h=round(h, 1), w=round(w, 1), ang=round(math.degrees(ang), 2), W=W)


def encode(crop: np.ndarray, q: int = 80) -> bytes:
    import cv2
    ok, b = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, q])
    assert ok
    return b.tobytes()


# ------------------------------------------------------------------------------------------------ experiment 80

M80 = E / "80_old_print_pull/data/manifest80.jsonl"


def pages80() -> list[dict]:
    """Experiment 80's old-print pull (580 documents, 1924-1999, training-pool journals) as pages77-style rows."""
    held = test_codes()
    out = []
    for l in open(M80, encoding="utf-8"):
        m = json.loads(l)
        if not (m.get("pdf") and m.get("json")) or m["jcode"] in held:
            continue
        d = E / "80_old_print_pull/data/fetch" / m["id"]
        for k in range(1, (m.get("azure_pages") or 0) + 1):
            out.append(dict(stem=m["id"], jcode=m["jcode"], year=m.get("year"), page=k, lines=None,
                            azure=str(d / f"{m['id']}.json"), pdf=str(d / f"{m['id']}.pdf")))
    return out
