"""Experiment 94 (layout, stage 2): shared pieces.  Imports experiment 92's common92 (paths, guards, Argon, Azure,
geometry, XY-cut) and adds the fine label set, the byline split and the page-number rule.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(E / "92_layout"))
import common92 as C92  # noqa: E402
from common92 import (LID, area, assert_not_locked, azure_lines, fixpath, heldout_codes, inter, iou, is_locked_any,  # noqa: E402,F401
                      kendall_tau, page_is_rtl, xycut_order)

E92 = E / "92_layout/out"

# the layout model's classes (index order)
FINE = ["title", "author", "affiliation", "abstract", "heading", "body", "list", "footnote", "reference", "table",
        "caption", "page_number", "header", "equation", "verse", "other"]
# fine -> experiment 39 / 92's eleven coarse labels
TO_COARSE = {"title": "heading", "author": "heading", "affiliation": "heading", "heading": "heading",
             "abstract": "body", "body": "body", "list": "list", "footnote": "footnote", "reference": "references",
             "table": "table", "caption": "caption", "page_number": "furniture", "header": "furniture",
             "equation": "equation", "verse": "verse", "other": "other"}
# Argon block type -> fine (byline and header/footer are refined per line)
ARGON_FINE = {"title": "title", "heading": "heading", "byline": "byline", "paragraph": "body", "quote": "body",
              "boxed": "body", "abstract": "abstract", "keywords": "abstract", "list_item": "list",
              "reference": "reference", "endnote": "reference", "footnote": "footnote", "verse": "verse",
              "table": "table", "equation": "equation", "caption": "caption", "figure": "caption",
              "header": "header", "footer": "header", "other": "other", "other_article": "other",
              "scoped_box": "other"}

RAWS = {"v2_55": E / "43_rehearsal/out/v2_55/raw", "v33_300": E / "43_rehearsal/out/v33_300/raw",
        "v33_300b": E / "43_rehearsal/out/v33_300b/raw", "j0130": E / "52_journal_gate1/out/j0130/raw",
        "j0165": E / "70_gate2_pilot/out/j0165/raw"}
for _j in ("0011", "0013", "0097", "0246", "0523", "0840", "1001", "1182"):
    RAWS[f"j{_j}"] = E / f"74_gate2_full/out/{_j}/j{_j}/raw"

_DIAC = re.compile("[ً-ْٰـ]")
LETTER = re.compile(r"[^\W\d_]")
DIGIT = re.compile(r"\d")
AFF_WORDS = re.compile(r"جامع|كلي|قسم|معهد|مركز|وزار|مدرس|مديري|إدار|ادار|أستاذ|استاذ|باحث|دكتوراه|ماجستير|محاضر|"
                       r"univ|college|depart|institut|faculty|school|ministry|professor|lecturer|@|\.edu|\.com",
                       re.I)


def norm(s: str) -> str:
    s = _DIAC.sub("", s or "")
    s = re.sub("[إأآٱ]", "ا", s).replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"\s+", " ", s).strip().lower()


def is_page_number(text: str) -> bool:
    t = text or ""
    return bool(DIGIT.search(t)) and not LETTER.search(t) and len(t.strip()) <= 12


def argon_doc(raw_dir: Path, stem: str):
    """({page: [blocks with fine type and ids]}, metadata authors) for one article."""
    from rapidfuzz import fuzz  # noqa: F401  (checked early)
    pages, authors = {}, []
    for f in sorted(raw_dir.glob(f"{stem}_c*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        ans = d.get("answer")
        if not isinstance(ans, dict):
            continue
        md = ans.get("metadata")
        if isinstance(md, dict) and not authors:
            authors = [a for a in md.get("authors") or [] if isinstance(a, dict)]
    pages = C92.argon_pages(raw_dir, stem)
    return pages, authors


def byline_split(text: str, authors: list[dict]) -> str:
    """author or affiliation for one byline line."""
    from rapidfuzz import fuzz
    t = norm(text)
    names = [norm(a.get("name") or "") for a in authors if a.get("name")]
    affs = []
    for a in authors:
        for v in [a.get("affiliation"), a.get("position"), a.get("email")] + list((a.get("aff_parts") or {}).values()):
            if isinstance(v, str) and len(v.strip()) >= 3:
                affs.append(norm(v))
    sa = max((fuzz.partial_ratio(n, t) for n in names if len(n) >= 3), default=0)
    sf = max((fuzz.partial_ratio(a, t) for a in affs), default=0)
    kw = bool(AFF_WORDS.search(text or "")) or bool(AFF_WORDS.search(t))
    if max(sa, sf) >= 70 and abs(sa - sf) >= 5:
        return "author" if sa > sf else "affiliation"
    return "affiliation" if kw else "author"


def fine_of(btype: str, text: str, authors) -> str:
    f = ARGON_FINE.get(btype, "other")
    if f == "byline":
        return byline_split(text, authors)
    if f == "header" and is_page_number(text):
        return "page_number"
    return f


def orient_of(poly) -> int:
    """Text direction of an Azure line polygon (points in reading-frame order: top-left, top-right, ...): 0 upright,
    1 turned 90 deg clockwise (text runs downwards), 2 upside down, 3 turned 90 deg anticlockwise (text runs up)."""
    dx, dy = poly[2] - poly[0], poly[3] - poly[1]
    a = math.degrees(math.atan2(dy, dx))
    if -45 <= a <= 45:
        return 0
    if 45 < a <= 135:
        return 1
    if -135 <= a < -45:
        return 3
    return 2
