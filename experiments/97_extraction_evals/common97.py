"""Experiment 97: shared helpers for the R1 / R2 scripts and score97.py.

Everything reads out/cache/<stem>.json (written once by extract97.py from the release database, read-only); nothing
here opens the database.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import unicodedata
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f"{HERE}/out"
PAGES = "/home/appuser/inkscript/experiments/43_rehearsal/out/pages/"
LOCK = json.load(open(f"{HERE}/LOCKED_EVAL.json"))
ARTS = LOCK["articles"]
BY_STEM = {a["stem"]: a for a in ARTS}


def exam_pages():
    """[(stem, page, kind)] for the 214 exam pages, in lock order."""
    return [(a["stem"], p, k) for a in ARTS for k, p in a["pages"].items()]


@lru_cache(maxsize=None)
def cache(stem: str) -> dict:
    return json.load(open(f"{OUT}/cache/{stem}.json"))


# ------------------------------------------------------------------------------------------------ pipeline roles
# The pipeline's block roles (blocks.role) and page-region roles (page_regions.role) onto the key's role names
# (KEYER_RULES.md, part PAGE).  Written out explicitly so every row of the confusion table can be traced to this.
BLOCK_ROLE_TO_KEY = {
    "title": "title",
    "title-translated": "title-translated",
    "byline": "byline",
    "abstract": "abstract",
    "keywords": "keywords",
    "front-matter": "front-matter",
    "heading": "heading",
    "paragraph": "paragraph",
    "list-item": "list-item",
    "quote": "quote",
    "verse-group": "verse",
    "footnote": "footnote",
    "endnote": "endnote",
    "ref": "ref",
    "caption": "caption",
    "table-cell": "table",
    "back-matter": "other",
}
REGION_ROLE_TO_KEY = {
    "pageHeader": "running-head",
    "pageFooter": "running-head",
    "pageNumber": "page-number",
    "pictureText": "figure",
    "formulaInk": "equation",
    "otherArticle": "other",
    "noise": "(not-text)",
    "showThrough": "(not-text)",
    "pictureJunk": "(not-text)",
    "ornament": "(not-text)",
}
NO_BLOCK = "(no-block)"


def map_block_role(role: str | None) -> str:
    return BLOCK_ROLE_TO_KEY.get(role, f"?{role}")


def map_region_role(role: str | None) -> str:
    return REGION_ROLE_TO_KEY.get(role, f"?region:{role}")


@lru_cache(maxsize=None)
def article_index(stem: str) -> dict:
    """Per article: blocks by id, regions by id, line_map rows by (page, azure_line), lines of every block."""
    d = cache(stem)
    blocks = {b["block_id"]: b for b in d["blocks"]}
    regions = {r["region_id"]: r for r in d["page_regions"]}
    by_line: dict[tuple, list] = {}
    block_lines: dict[str, list] = {}
    for r in d["line_map"]:
        if r["azure_line_no"] is None:
            continue
        by_line.setdefault((r["page"], r["azure_line_no"]), []).append(r)
        block_lines.setdefault(r["block_id"] or f"region:{r['region_id']}", []).append(r)
    for k in block_lines:
        block_lines[k].sort(key=lambda r: _alto_key(r["alto_line_id"], r["page"]))
    az = {(l["page"], l["line_no"]): l for l in d["azure_lines"]}
    # a table-cell block carries no figure_id; table_cells.block_id says which table it belongs to
    cell_fig = {c["block_id"]: c["figure_id"] for c in d["table_cells"] if c["block_id"]}
    return dict(blocks=blocks, regions=regions, by_line=by_line, block_lines=block_lines, azure=az, cell_fig=cell_fig)


def _alto_key(aid: str, page: int):
    m = re.match(r"p(\d+)b(\d+)l(\d+)", aid or "")
    return (page, int(m.group(2)), int(m.group(3))) if m else (page, 0, 0)


def line_targets(stem: str, page: int, line: int) -> list[tuple[str, str]]:
    """Distinct targets of one Azure line: [('block', id) | ('region', id)], in line_map order."""
    out = []
    for r in article_index(stem)["by_line"].get((page, line), []):
        t = ("block", r["block_id"]) if r["block_id"] else ("region", r["region_id"])
        if t not in out:
            out.append(t)
    return out


def pipeline_line_view(stem: str, page: int, line: int) -> dict:
    """What the pipeline made of one Azure line: its role (key names), its piece id (a table's cells are one piece,
    as in the key) and its position in the reading order (blocks.ord; None for page regions)."""
    ix = article_index(stem)
    t = line_targets(stem, page, line)
    if not t:
        return dict(role=NO_BLOCK, piece=None, ord=None, n_targets=0, raw_role=None)
    kind, tid = t[0]
    if kind == "region":
        r = ix["regions"][tid]
        return dict(role=map_region_role(r["role"]), piece=f"region:{tid}", ord=None, n_targets=len(t),
                    raw_role=f"region:{r['role']}")
    b = ix["blocks"][tid]
    fig = b["figure_id"] or ix["cell_fig"].get(tid)
    piece = f"fig:{fig}" if b["role"] == "table-cell" and fig else f"block:{tid}"
    return dict(role=map_block_role(b["role"]), piece=piece, ord=b["ord"], n_targets=len(t), raw_role=b["role"],
                block_id=tid)


# ------------------------------------------------------------------------------------------------ text
_TATWEEL = "ـ"
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def ws(s: str | None) -> str:
    """Trim and collapse whitespace (the 'exact' comparison)."""
    return re.sub(r"\s+", " ", (s or "")).strip()


def fold(s: str | None) -> str:
    """The 'folded' comparison: no diacritics (Mn), no tatweel, no punctuation or symbols, digits to ASCII,
    whitespace collapsed, Latin lower-cased.  Letters themselves (alef forms, ya / alef maqsura, ta marbuta) are kept:
    those are reading differences, not formatting."""
    s = unicodedata.normalize("NFKC", s or "").translate(_DIGITS).replace(_TATWEEL, "")
    s = "".join(ch if unicodedata.category(ch)[0] not in "PS" else " " for ch in s if unicodedata.category(ch) != "Mn")
    return ws(s).lower()


def digits(s: str | None) -> str:
    return "".join(re.findall(r"\d+", (s or "").translate(_DIGITS)))


def lev(a: str, b: str) -> int:
    try:
        from rapidfuzz.distance import Levenshtein
        return Levenshtein.distance(a, b)
    except ImportError:
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1.0 - lev(a, b) / max(len(a), len(b))


# ------------------------------------------------------------------------------------------------ line ↔ block text
@lru_cache(maxsize=None)
def tile_block(stem: str, block_id: str) -> dict:
    """(block_id may be "region:<id>" for a page region: running head, page number ...)
    Cut a block's shown text into the stretches that belong to each of its Azure lines.

    The block's Azure lines (in the pipeline's own line order) are joined with spaces and aligned to blocks.text with
    difflib; every line boundary is mapped into the block text, the boundary between two lines is put halfway between
    the end of one and the start of the next, and then moved to the nearest space (within 4 characters).  So the whole
    block text is shared out (nothing between two lines is lost) and a word Azure cut short still comes out whole.
    -> {(page, line): (start, end)} offsets into blocks.text, plus the text."""
    ix = article_index(stem)
    if block_id.startswith("region:"):
        text = ix["regions"][block_id[7:]]["text"] or ""
    else:
        text = ix["blocks"][block_id]["text"] or ""
    rows = ix["block_lines"].get(block_id, [])
    lines = []
    for r in rows:
        key = (r["page"], r["azure_line_no"])
        az = ix["azure"].get(key)
        lines.append((key, ws(az["text"]) if az else ""))
    spans, score, ratio = _tile(text, lines)
    if len(lines) > 1 and score < 0.97:
        # the pipeline's line order is not the text order (table cells read in another order, a merged column):
        # order the lines by where each one best fits in the text, and keep that cut if it fits better
        def where(t):
            if not t:
                return 0
            m = difflib.SequenceMatcher(None, text, t, autojunk=False).find_longest_match(0, len(text), 0, len(t))
            return m.a - m.b
        alt = sorted(lines, key=lambda kt: where(kt[1]))
        s2, sc2, r2 = _tile(text, alt)
        if sc2 > score:
            spans, score, ratio = s2, sc2, r2
    return dict(text=text, spans=spans, ratio=ratio, fit=round(score, 4))


def _tile(text, lines):
    seq, spans, pos = [], [], 0
    for key, t in lines:
        if pos:
            seq.append(" ")
            pos += 1
        spans.append((key, pos, pos + len(t)))
        seq.append(t)
        pos += len(t)
    A = "".join(seq)
    sm = difflib.SequenceMatcher(None, A, text, autojunk=False)
    ops = sm.get_opcodes()

    def amap(i: int) -> int:
        for tag, i1, i2, j1, j2 in ops:
            if i1 <= i < i2 or (i == i2 == len(A) and i2 == len(A)):
                if tag == "equal":
                    return j1 + (i - i1)
                if tag == "replace":
                    return j1 + round((i - i1) * (j2 - j1) / max(1, i2 - i1))
                if tag == "delete":
                    return j1
        return len(text)

    def snap(j: int) -> int:
        if j <= 0 or j >= len(text) or text[j - 1].isspace() or text[j].isspace():
            return max(0, min(len(text), j))
        for d in range(1, 5):
            for k in (j - d, j + d):
                if 0 < k < len(text) and (text[k].isspace() or text[k - 1].isspace()):
                    return k
        return j

    def snap_forward(j: int) -> int:
        """End-of-line hyphen: cut just after the hyphen when the stored word still holds it (as printed), else keep
        the whole joined word with the first line."""
        a = j
        while a > 0 and not text[a - 1].isspace():
            a -= 1
        z = j
        while z < len(text) and not text[z].isspace():
            z += 1
        h = max((k for k in range(a, z) if text[k] in "-\u00ad\u2010"), default=None)
        return h + 1 if h is not None and h + 1 < z else z

    cuts = [0]
    for (k1, s1, e1), (k2, s2, e2), (_, t1) in zip(spans, spans[1:], lines):
        a, b = amap(max(s1, e1 - 1)) + 1 if e1 > s1 else amap(s1), amap(s2)
        mid = max(cuts[-1], (a + b) // 2)
        # a word broken by an end-of-line hyphen stays whole with the line that holds its first part
        cuts.append(snap_forward(mid) if t1.endswith(("-", "\u00ad", "\u2010")) else snap(mid))
    cuts.append(len(text))
    out = {}
    num = den = 0
    for n, ((k, s, e), (_, t)) in enumerate(zip(spans, lines)):
        out[k] = (cuts[n], max(cuts[n], cuts[n + 1]))
        w = max(1, len(t))
        num += w * similarity(t, ws(text[out[k][0]:out[k][1]]))
        den += w
    return out, (num / den if den else 1.0), sm.ratio()


def shown_segment(stem: str, page: int, line: int, block_id: str) -> tuple[str, float]:
    t = tile_block(stem, block_id)
    sp = t["spans"].get((page, line))
    if sp is None:
        return "", 0.0
    seg = ws(t["text"][sp[0]:sp[1]])
    az = ws(article_index(stem)["azure"][(page, line)]["text"])
    return seg, similarity(az, seg)


def offset_to_line(stem: str, block_id: str, offset: int):
    """The Azure line (page, line) whose stretch of the block text holds character `offset` (for note calls)."""
    t = tile_block(stem, block_id)
    best = None
    for k, (s, e) in t["spans"].items():
        if s <= offset < e:
            return k
        if best is None or (offset >= e and e >= t["spans"][best][1]):
            best = k
    return best


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
