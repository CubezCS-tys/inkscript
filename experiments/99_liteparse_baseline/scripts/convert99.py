"""Experiment 99: LiteParse output (out/runs/<set>_<mode>/<stem>.json) -> the exam's key formats, in Azure line numbers.

Run with the repo's .venv python (never the LiteParse venv); imports nothing from LiteParse, reads its JSON only.

Matching (README, "How lines were matched"): every LiteParse word box (text items carry per-word boxes; an item with
no word boxes counts as one word) is scaled from LiteParse's 72-dpi page units to the packet's 300-dpi pixels (the
factor is measured per page as packet width_px / LiteParse page width, ~4.1667) and given to the Azure line it
overlaps most (intersection area; at least 30% of the word box, or of the Azure line box when that is smaller).
An Azure line then takes the block that holds most of its matched word area (a text item's block comes from the
blocks' text_item_indices; the first block wins when an item is listed in more than one).
"""
from __future__ import annotations

import collections as C
import json
import os
import sys

X = "/home/appuser/inkscript/experiments"
E = f"{X}/99_liteparse_baseline"
P97 = f"{X}/97_extraction_evals"
sys.path.insert(0, P97)
from common97 import NO_BLOCK  # noqa: E402

NOT_TEXT = "(not-text)"
# LiteParse block kinds -> key roles.  Written out so every confusion row can be traced here.
KIND_TO_KEY = {
    "heading": "heading",
    "paragraph": "paragraph",
    "list_item": "list-item",
    "table": "table",
    "merged_table": "table",
    "grid_fallback": "table",
    "figure": "figure",
    "code": "other",
    "page_header": "running-head",
    "page_footer": "running-head",
    "rule": NOT_TEXT,
}
TABLE_KINDS = {"table", "merged_table", "grid_fallback"}
# key roles LiteParse has a name for (P1 'restricted'): everything else (title, byline, affiliation, abstract,
# keywords, front-matter, quote, verse, footnote, endnote, ref, caption, equation, page-number, other) it cannot say
EXPRESSIBLE = {"heading", "paragraph", "list-item", "table", "figure", "running-head"}


def kind_role(k):
    return KIND_TO_KEY.get(k, f"?{k}")


_packets = {}


def packet(stem):
    if stem not in _packets:
        _packets[stem] = json.load(open(f"{P97}/out/packets/{stem}/packet.json"))
    return _packets[stem]


def packet_page(stem, page):
    return next(p for p in packet(stem)["pages"] if p["page"] == page)


_crops = None


def load_run(set_mode, stem):
    """A run file; for text-layer runs each page carries `_shifts`: the registration candidates (page units) for a
    page whose crop box sits inside its media box (see match_page)."""
    global _crops
    f = f"{E}/out/runs/{set_mode}/{stem}.json"
    if not os.path.exists(f):
        return None
    d = json.load(open(f))
    if "_text" in set_mode:
        if _crops is None:
            _crops = json.load(open(f"{E}/out/cropboxes.json")) if os.path.exists(f"{E}/out/cropboxes.json") else {}
        for pg, p in (d.get("pages") or {}).items():
            c = _crops.get(f"{stem}|{pg}")
            if c and [round(x, 1) for x in c["media"]] != [round(x, 1) for x in c["crop"]]:
                dx, dy = c["crop"][0] - c["media"][0], c["crop"][1] - c["media"][1]
                p["_shifts"] = [(0.0, 0.0), (-dx, -dy), (0.0, -dy), (-dx, 0.0), (dx, dy), (0.0, dy), (dx, 0.0)]
    return d


def _inter(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def match_page(stem, page, lp):
    """-> dict(scale, words=[{item, text, box_px, line}], line_items={line: [item,...] in returned order},
    line_block={line: block index | None}, item_block={item: block index})  (memoised on the page dict)"""
    if "_match" in lp:
        return lp["_match"]
    lp["_match"] = _match_page(stem, page, lp)
    return lp["_match"]


def _match_page(stem, page, lp):
    pp = packet_page(stem, page)
    scale = pp["width_px"] / lp["width"]
    az = [(l["line"], (l["x"], l["y"], l["w"], l["h"])) for l in pp["azure_lines"]]
    item_block = {}
    for n, b in enumerate(lp.get("blocks") or []):
        for i in b.get("text_item_indices") or []:
            item_block.setdefault(i, n)
    # items listed in no block (LiteParse leaves table cells' text_item_indices empty): the smallest block whose
    # box holds the item's centre
    blocks = lp.get("blocks") or []
    for i, it in enumerate(lp.get("text_items") or []):
        if i in item_block:
            continue
        cx, cy = it["x"] + it["width"] / 2, it["y"] + it["height"] / 2
        best = None
        for n, b in enumerate(blocks):
            bb = b.get("bbox")
            if bb and bb["x"] <= cx <= bb["x"] + bb["width"] and bb["y"] <= cy <= bb["y"] + bb["height"]:
                if best is None or bb["width"] * bb["height"] < best[1]:
                    best = (n, bb["width"] * bb["height"])
        if best:
            item_block[i] = best[0]
    # registration (text-layer pages with a crop box inside the media box only): the PDF's invisible text sits
    # offset from the scanned ink by the crop box origin; take the candidate shift under which LiteParse's word boxes
    # overlap Azure's line boxes most.  Every other page: no shift.
    shift = (0.0, 0.0)
    if lp.get("_shifts"):
        def total(sh):
            t = 0.0
            for it in lp.get("text_items") or []:
                for w in it.get("words") or [it]:
                    b = ((w["x"] + sh[0]) * scale, (w["y"] + sh[1]) * scale, w["width"] * scale, w["height"] * scale)
                    t += max((_inter(b, ab) for _, ab in az), default=0.0)
            return t
        shift = max(lp["_shifts"], key=total)
    words = []
    for i, it in enumerate(lp.get("text_items") or []):
        ws_ = it.get("words") or [dict(text=it["text"], x=it["x"], y=it["y"], width=it["width"], height=it["height"])]
        for w in ws_:
            box = ((w["x"] + shift[0]) * scale, (w["y"] + shift[1]) * scale, max(w["width"], 0.01) * scale,
                   max(w["height"], 0.01) * scale)
            area = box[2] * box[3]
            best, bv = None, 0.0
            for ln, ab in az:
                v = _inter(box, ab)
                if v > bv:
                    best, bv = ln, v
            if best is not None:
                ab = dict(az)[best]
                if bv < 0.3 * min(area, ab[2] * ab[3]):
                    best = None
            words.append(dict(item=i, text=w["text"], box_px=box, line=best, area=bv))
    line_items, vote = C.defaultdict(list), C.defaultdict(C.Counter)
    for w in words:
        if w["line"] is None:
            continue
        if w["item"] not in line_items[w["line"]]:
            line_items[w["line"]].append(w["item"])
        vote[w["line"]][item_block.get(w["item"])] += w["area"]
    line_block = {ln: v.most_common(1)[0][0] for ln, v in vote.items()}
    return dict(scale=scale, shift=shift, words=words, line_items=dict(line_items), line_block=line_block, item_block=item_block)


def line_text(m, lp, line, order="returned"):
    """The text LiteParse returns for one Azure line: its words on that line, item by item.  order='returned':
    items in LiteParse's own order (the order of text_items, which is the order of its page text); 'rtl': items
    sorted right to left by x (our fix, to separate reading from ordering)."""
    items = list(m["line_items"].get(line, []))
    if order == "rtl":
        xs = {i: lp["text_items"][i]["x"] + lp["text_items"][i]["width"] / 2 for i in items}
        items.sort(key=lambda i: -xs[i])
    parts = []
    for i in items:
        it = lp["text_items"][i]
        mine = [w for w in m["words"] if w["item"] == i]
        on = [w for w in mine if w["line"] == line]
        if len(on) == len(mine):
            parts.append(it["text"])                     # the whole item is on this line: its text as returned
            continue
        # an item cut by Azure's line boundary: its words on this line, in the order they stand in the item's own
        # text (LiteParse lists an item's word boxes left to right, its text in its own order)
        txt, pos, placed = it["text"], 0, []
        for w in mine:
            k = txt.find(w["text"], 0)
            placed.append((k if k >= 0 else 10 ** 6, w))
        placed.sort(key=lambda kw: kw[0])
        parts.append(" ".join(w["text"] for _, w in placed if w["line"] == line))
    return " ".join(p.strip() for p in parts if p.strip())


# ------------------------------------------------------------------------------------------------ PAGE
def pred_page(stem, page, lp):
    m = match_page(stem, page, lp)
    blocks = lp.get("blocks") or []
    pieces = {}
    not_text = []
    for ln in sorted(m["line_block"]):
        b = m["line_block"][ln]
        if b is None:
            continue                                     # words in no block: the line is in no piece
        role = kind_role(blocks[b]["kind"])
        if role == NOT_TEXT:
            not_text.append(ln)
            continue
        pieces.setdefault(b, dict(role=role, lines=[], _kind=blocks[b]["kind"], _block=b, unordered=False))
        pieces[b]["lines"].append(ln)
    plist = [pieces[b] for b in sorted(pieces)]          # LiteParse's block order = its reading order
    return dict(stem=stem, page=page, columns=None, pieces=plist, note_calls=[],
                azure_lines_that_are_not_text=not_text, unsure=False), m


# ------------------------------------------------------------------------------------------------ TAB
def _cells_rows(b):
    rows = []
    if b.get("header"):
        h = b["header"]
        rows.append(h if h and isinstance(h[0], dict) else [c for r in h for c in r])
    rows += list(b.get("rows") or [])
    return rows


def pred_tab(stem, page, lp, m=None):
    m = m or match_page(stem, page, lp)
    tables = []
    for n, b in enumerate(lp.get("blocks") or []):
        if b["kind"] not in TABLE_KINDS:
            continue
        rows = _cells_rows(b)
        grid = [[(c.get("text") or "").strip() for c in r] for r in rows] if rows else None
        ln = sorted(l for l, bb in m["line_block"].items() if bb == n)
        # cell order within a row: LiteParse lists cells left to right (checked on the dev pages); the key's c0 is
        # the rightmost column for an Arabic table, and compare_tab mirrors when the directions differ
        direction = "ltr"
        xs = [[c["bbox"]["x"] for c in r if c.get("bbox")] for r in rows]
        xs = [x for x in xs if len(x) >= 2]
        if xs and sum(1 for x in xs if x[0] > x[-1]) > len(xs) / 2:
            direction = "rtl"
        if grid is not None:
            nc = max((len(r) for r in grid), default=0)
            grid = [r + [""] * (nc - len(r)) for r in grid]
        tables.append(dict(lines_first_last=[ln[0], ln[-1]] if ln else None, lines=ln, caption=None,
                           number_printed=None, n_rows=len(grid or []), n_cols=max((len(r) for r in grid or []), default=0),
                           n_header_rows=1 if b.get("header") else 0, is_continuation_of_previous_page=False,
                           continues_on_next_page=False, cells=grid, direction=direction, _kind=b["kind"], _block=n))
    tables.sort(key=lambda t: (t["lines_first_last"] or [10 ** 6])[0])
    figs = [dict(kind="figure", caption=None, number_printed=None) for b in lp.get("blocks") or [] if b["kind"] == "figure"]
    return dict(stem=stem, page=page, tables=tables, figures=figs, unsure=False)


# ------------------------------------------------------------------------------------------------ REFS
def pred_refs(stem, page, lp, m=None, kinds=("list_item",)):
    """References = LiteParse's list items on the page (boundaries only: LiteParse has no reference fields)."""
    m = m or match_page(stem, page, lp)
    refs = []
    for n, b in enumerate(lp.get("blocks") or []):
        if b["kind"] not in kinds:
            continue
        ln = sorted(l for l, bb in m["line_block"].items() if bb == n)
        if ln:
            refs.append(dict(lines=ln, starts_on_previous_page=False, continues_on_next_page=False, _kind=b["kind"]))
    return dict(stem=stem, page=page, references=refs, unsure=False)
