"""Experiment 38, step 1: dots.mocr's layout with Azure's words poured into it -> out/pages/<pid>/layout.json.

    PYTHONPATH=<worktree>/src /home/yassine/inkscript/.venv/bin/python parse.py [PID ...] [--force]

For one page:
1. **Blocks** are dots.mocr's, in its reading order, with its categories (title, heading, text, list item, footnote,
   caption, picture, table, formula, page header/footer).
2. **Every Azure word goes to exactly one place.** A word goes to the block that covers most of its box (at least a
   fifth of it); a word touching no block goes to the nearest one within half a line height (not a picture);
   anything else is a leftover. Leftovers are grouped by their Azure line into blocks of their own ("azure-only"),
   put into the reading order next to the block nearest them, so nothing Azure read is lost. An Azure line that
   runs across two of dots' blocks (two columns read as one line) is split between them by its words' places.
   Inside a block, lines run top to bottom, side-by-side pieces right to left (left to right in a Latin block).
3. **A dots block that got no Azure word** keeps dots' text, marked source "dots", only if Kraken found an ink line
   inside it (Azure skipped real ink); otherwise it is dropped and reported (an invention, or ornament).
4. **Tables**: dots' HTML grid. The Azure words inside the table are cut into segments at wide gaps (cells are
   separated by white space), and segments are matched to cells by text (folded), best pairs first; a cell may take
   several segments (several lines). Segments left over are placed by position, in the row and column bands of the
   matched cells. A cell with Azure words gets Azure's text and its box; a cell without keeps dots' text, marked
   source "dots", with its box inferred from its row and column.
5. **Formulas**: dots' LaTeX (checked or redone later, formulas.py); Azure's words inside are the formula's ink.
6. **Pictures**: cropped from the scan (colour from the faithful PDF where it matches). The Azure words inside are
   kept as the picture's own text (ALTO only). Captions are tied to the nearest picture or table ("جدول"/"Table"
   prefers a table, "شكل"/"Figure" a picture).
7. **Kraken as the net**: Kraken lines on the page in no block (text the layout missed), Azure lines in a block
   with no Kraken line on them, and dots-only text with no ink line.
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from statistics import median

from common import (OUT, area, azure_words, colour_page, dots_blocks, gap, gold, inter, kraken_lines, page_image,
                    pages, union)
from inkscript.gold.text import distance, folded

ROLE = {"Title": "title", "Section-header": "heading", "Text": "p", "List-item": "li", "Footnote": "fn",
        "Caption": "caption", "Picture": "figure", "Table": "table", "Formula": "formula",
        "Page-header": "header", "Page-footer": "footer"}
LATIN = re.compile(r"[A-Za-z]")
ARABIC = re.compile(r"[؀-ۿ]")
NUMBERISH = re.compile(r"^[\s\-–—|()\[\]\d٠-٩.,:/]+$")


def is_latin(text: str) -> bool:
    return len(LATIN.findall(text)) > len(ARABIC.findall(text))


# ------------------------------------------------------------------------------------------------ tables

class _Grid(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cell, self.sec = [], None, "tbody"

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("thead", "tbody", "tfoot"):
            self.sec = tag
        elif tag == "tr":
            self.rows.append(dict(head=self.sec == "thead", cells=[]))
        elif tag in ("td", "th"):
            if not self.rows:
                self.rows.append(dict(head=self.sec == "thead", cells=[]))
            self.cell = dict(th=tag == "th" or self.sec == "thead", text="",
                             colspan=int(re.sub(r"\D", "", a.get("colspan") or "1") or 1),
                             rowspan=int(re.sub(r"\D", "", a.get("rowspan") or "1") or 1))
            self.rows[-1]["cells"].append(self.cell)
        elif tag == "br" and self.cell is not None:
            self.cell["text"] += " "

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.cell = None

    def handle_data(self, d):
        if self.cell is not None:
            self.cell["text"] += d


def parse_table(html: str) -> list[dict]:
    p = _Grid()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    for r in p.rows:
        for c in r["cells"]:
            c["text"] = " ".join(c["text"].replace("**", "").split())
    return [r for r in p.rows if r["cells"]]


def grid_slots(rows):
    """(row, col) of each cell's top-right slot, cols in reading order (col 0 = rightmost in a RTL table)."""
    owner, start = {}, {}
    for ri, r in enumerate(rows):
        ci = 0
        for k, c in enumerate(r["cells"]):
            while (ri, ci) in owner:
                ci += 1
            start[(ri, k)] = (ri, ci)
            for dr in range(c["rowspan"]):
                for dc in range(c["colspan"]):
                    owner[(ri + dr, ci + dc)] = (ri, k)
            ci += c["colspan"]
    return owner, start


def sim(a: str, b: str) -> float:
    a, b = folded(a), folded(b)
    if not a or not b:
        return 0.0
    return 1 - distance(a, b) / max(len(a), len(b))


def segments(words: list[dict]) -> list[dict]:
    """A table's Azure words cut into cell-sized pieces: per Azure line, split where the white gap between two
    neighbouring words is wider than 1.2 x the line's height... or the line's median word gap x 3."""
    by = {}
    for w in words:
        by.setdefault(w["line"], []).append(w)
    out = []
    for li, ws in by.items():
        ws = sorted(ws, key=lambda w: -w["box"][2]) if not is_latin(" ".join(w["text"] for w in ws)) else \
            sorted(ws, key=lambda w: w["box"][0])
        h = median(w["box"][3] - w["box"][1] for w in ws)
        gaps = []
        for a, b in zip(ws, ws[1:]):
            gaps.append(max(0.0, max(a["box"][0], b["box"][0]) - min(a["box"][2], b["box"][2])))
        mg = median(gaps) if gaps else 0
        cut = max(1.2 * h, 3 * mg)
        cur = [ws[0]]
        for g, w in zip(gaps, ws[1:]):
            if g > cut:
                out.append(cur)
                cur = [w]
            else:
                cur.append(w)
        out.append(cur)
    return [dict(words=s, text=" ".join(w["text"] for w in s), box=union(w["box"] for w in s)) for s in out]


def fill_table(rows: list[dict], words: list[dict], tbox) -> tuple[list[dict], list[dict]]:
    """Cells filled from Azure's words where they can be found. Returns (rows, leftover words)."""
    cells = [(ri, k, c) for ri, r in enumerate(rows) for k, c in enumerate(r["cells"])]
    segs = segments(words) if words else []
    for c in (c for _, _, c in cells):
        c.update(segs=[], source="dots")
    pairs = []
    for si, s in enumerate(segs):
        for ci, (_, _, c) in enumerate(cells):
            v = sim(c["text"], s["text"])
            if v >= 0.5:
                pairs.append((v, si, ci))
            elif folded(s["text"]) and len(folded(s["text"])) >= 3 and folded(s["text"]) in folded(c["text"]):
                pairs.append((0.5 + 0.1 * len(folded(s["text"])) / max(1, len(folded(c["text"]))), si, ci))
    used = set()
    for v, si, ci in sorted(pairs, reverse=True):
        if si in used:
            continue
        c = cells[ci][2]
        now = " ".join(segs[j]["text"] for j in c["segs"])
        if c["segs"] and sim(c["text"], now + " " + segs[si]["text"]) <= sim(c["text"], now):
            continue
        c["segs"].append(si)
        used.add(si)
    # bands of the matched cells: rows by y, columns by x
    owner, start = grid_slots(rows)
    nr = max((k[0] for k in owner), default=-1) + 1
    nc = max((k[1] for k in owner), default=-1) + 1
    rowb, colb = [None] * nr, [None] * nc
    for ri, k, c in cells:
        if not c["segs"]:
            continue
        bb = union(segs[j]["box"] for j in c["segs"])
        r0, c0 = start[(ri, k)]
        if c["rowspan"] == 1:
            rowb[r0] = bb[1:4:2] if rowb[r0] is None else [min(rowb[r0][0], bb[1]), max(rowb[r0][1], bb[3])]
        if c["colspan"] == 1:
            colb[c0] = [bb[0], bb[2]] if colb[c0] is None else [min(colb[c0][0], bb[0]), max(colb[c0][1], bb[2])]
    left = []
    for si, s in enumerate(segs):
        if si in used:
            continue
        cx, cy = (s["box"][0] + s["box"][2]) / 2, (s["box"][1] + s["box"][3]) / 2
        r = next((i for i, b in enumerate(rowb) if b and b[0] - 8 <= cy <= b[1] + 8), None)
        q = next((j for j, b in enumerate(colb) if b and b[0] - 8 <= cx <= b[1] + 8), None)
        if r is None or q is None or (r, q) not in owner:
            left.append(s)
            continue
        ri, k = owner[(r, q)]
        c = rows[ri]["cells"][k]
        c["segs"].append(si)
        c.setdefault("by_position", True)
        used.add(si)
    # fill
    for ri, k, c in cells:
        if c["segs"]:
            ss = sorted((segs[j] for j in c["segs"]), key=lambda s: (s["box"][1], -s["box"][2]))
            c["words"] = [w for s in ss for w in s["words"]]
            c["azure_text"] = " ".join(w["text"] for w in c["words"])
            c["box"] = union(w["box"] for w in c["words"])
            c["source"] = "azure-position" if c.get("by_position") and len(c["segs"]) == 1 else "azure"
        else:
            c["words"] = []
        c.pop("segs")
    # inferred boxes for dots-only cells (row and column bands; else spread evenly over the table)
    x0, y0, x1, y1 = tbox
    for i in range(nr):
        if rowb[i] is None:
            rowb[i] = [y0 + i * (y1 - y0) / nr, y0 + (i + 1) * (y1 - y0) / nr]
    for j in range(nc):
        if colb[j] is None:
            colb[j] = [x1 - (j + 1) * (x1 - x0) / nc, x1 - j * (x1 - x0) / nc]
    for ri, k, c in cells:
        if "box" not in c:
            r0, c0 = start[(ri, k)]
            ys = [rowb[r0][0], rowb[min(nr - 1, r0 + c["rowspan"] - 1)][1]]
            xs = [colb[min(nc - 1, c0 + c["colspan"] - 1)][0], colb[c0][1]]
            c["box"] = [min(xs), ys[0], max(xs), ys[1]]
    return rows, [w for s in left for w in s["words"]]


# ------------------------------------------------------------------------------------------------ the page

def order_lines(words: list[dict]) -> list[list[dict]]:
    """A block's words as lines: Azure's lines, top to bottom; pieces sharing a band right to left (Latin: left to
    right); words inside a line in Azure's order."""
    by = {}
    for w in words:
        by.setdefault(w["line"], []).append(w)
    lines = [dict(words=ws, box=union(w["box"] for w in ws)) for ws in by.values()]
    latin = is_latin(" ".join(w["text"] for w in words))
    lines.sort(key=lambda l: (l["box"][1] + l["box"][3]) / 2)
    bands = []
    for l in lines:
        if bands:
            b = bands[-1][-1]["box"]
            ov = min(b[3], l["box"][3]) - max(b[1], l["box"][1])
            if ov > 0.5 * min(b[3] - b[1], l["box"][3] - l["box"][1]):
                bands[-1].append(l)
                continue
        bands.append([l])
    out = []
    for band in bands:
        band.sort(key=lambda l: l["box"][0] if latin else -l["box"][2])
        out += [l["words"] for l in band]
    return out


def strip_md(t: str) -> tuple[str, int]:
    m = re.match(r"^(#+)\s*", t)
    lvl = len(m.group(1)) if m else 0
    t = re.sub(r"^#+\s*", "", t)
    t = t.replace("**", "").replace("$$", "")
    return " ".join(t.split()), lvl


LIST_MARK = re.compile(r"^\s*([-*•●■◆❖▪➢✓]|\(?[0-9٠-٩]{1,3}[.)\-]|[ء-ي][.)\-])\s+")


def parse_page(pid: str, meta: dict) -> dict:
    g = gold(pid)
    W, H = g["image"]["width"], g["image"]["height"]
    words = azure_words(pid)
    blocks = []
    for b in dots_blocks(pid):
        role = ROLE.get(b["cat"], "p")
        if role == "p" and re.fullmatch(r"\s*\$\$[\s\S]*\$\$\s*", b["text"]):
            role = "formula"            # a displayed formula dots.mocr labelled as text
        text, lvl = strip_md(b["text"]) if role not in ("table", "formula") else (b["text"], 0)
        if role in ("header", "footer") and NUMBERISH.match(text or "x"):
            role = "pagenum"
        x0, y0, x1, y1 = b["box"]
        blocks.append(dict(id=None, dots_index=b["i"], cat=b["cat"], role=role, level=lvl, box=[max(0, x0), max(0, y0),
                      min(W, x1), min(H, y1)], dots_text=text, words=[], source="azure"))
    # 2. every Azure word to one place
    left = []
    for w in words:
        wa = area(w["box"]) or 1.0
        best, bv = None, 0.0
        for k, b in enumerate(blocks):
            v = inter(w["box"], b["box"]) / wa
            if v > bv + 1e-9 or (best is not None and abs(v - bv) < 1e-9 and v > 0
                                 and area(b["box"]) < area(blocks[best]["box"])):
                best, bv = k, v
        if best is not None and bv >= 0.2:
            blocks[best]["words"].append(w)
            continue
        h = w["box"][3] - w["box"][1]
        near = sorted(((gap(w["box"], b["box"]), k) for k, b in enumerate(blocks) if b["role"] != "figure"))
        if near and near[0][0] <= 0.5 * h:
            blocks[near[0][1]]["words"].append(w)
            blocks[near[0][1]].setdefault("near_words", 0)
            blocks[near[0][1]]["near_words"] += 1
        else:
            left.append(w)
    # leftovers -> blocks of their own, next to their nearest block in the reading order
    by = {}
    for w in left:
        by.setdefault(w["line"], []).append(w)
    for li, ws in by.items():
        bb = union(w["box"] for w in ws)
        nb = dict(id=None, dots_index=None, cat="(azure-only)", role="p", level=0, box=bb, dots_text="", words=ws,
                  source="azure-only")
        lt = " ".join(w["text"] for w in ws)
        if ws[0]["line_kind"] == "furniture" or NUMBERISH.match(lt):
            nb["role"] = "pagenum" if NUMBERISH.match(lt) else ("header" if bb[1] < H / 2 else "footer")
        if blocks:
            k = min(range(len(blocks)), key=lambda k: gap(bb, blocks[k]["box"]))
            before = (bb[1] + bb[3]) / 2 < (blocks[k]["box"][1] + blocks[k]["box"][3]) / 2
            blocks.insert(k if before else k + 1, nb)
        else:
            blocks.append(nb)
    # 3. kraken
    kl = [dict(text=l["text"], box=list(l["box"])) for l in kraken_lines(pid)]

    def kraken_in(box, frac=0.5):
        return [l for l in kl if inter(l["box"], box) >= frac * (area(l["box"]) or 1)]
    out_blocks, dropped = [], []
    for b in blocks:
        if b["role"] == "table":
            rows = parse_table(b["dots_text"])
            import copy
            rows0 = copy.deepcopy(rows)
            rows, tleft = fill_table(rows, b["words"], b["box"]) if rows else ([], b["words"])
            # dots sometimes lists an Arabic table's cells left to right: the editions want reading order (the
            # first cell of a row the rightmost). Seen on the page itself: if most rows' matched cells run left
            # to right, every row is reversed and the table filled again.
            ltr = rtl = 0
            for r in rows:
                xs = [(c["box"][0] + c["box"][2]) / 2 for c in r["cells"] if c.get("words")]
                for a, c2 in zip(xs, xs[1:]):
                    ltr += c2 > a
                    rtl += c2 < a
            if rows and ltr > rtl and not is_latin(" ".join(c["text"] for r in rows for c in r["cells"])):
                for r in rows0:
                    r["cells"].reverse()
                rows, tleft = fill_table(rows0, b["words"], b["box"])
                b["cells_reversed"] = True
            b["rows"] = rows
            b["table_leftover"] = tleft
            b["html"] = b["dots_text"]
        elif b["role"] == "formula":
            tex = b["dots_text"].strip()
            tex = re.sub(r"^\$\$|\$\$$", "", tex).strip()
            tex = re.sub(r"^\\\[|\\\]$", "", tex).strip()
            b["tex_dots"] = tex
        elif b["role"] == "figure":
            pass
        elif not b["words"]:
            ink = kraken_in(b["box"])
            if b["dots_text"] and ink:
                b["source"] = "dots"
                b["kraken_ink"] = len(ink)
            else:
                dropped.append(dict(dots_index=b["dots_index"], cat=b["cat"], text=b["dots_text"][:200],
                                    box=b["box"], kraken_lines=len(ink)))
                continue
        out_blocks.append(b)
    blocks = out_blocks
    # ids, lines
    nf = nt = ne = nb = 0
    for b in blocks:
        if b["role"] == "figure":
            nf += 1
            b["id"] = f"p1f{nf}"
        elif b["role"] == "table":
            nt += 1
            b["id"] = f"p1t{nt}"
        elif b["role"] == "formula":
            ne += 1
            b["id"] = f"p1eq{ne}"
        else:
            nb += 1
            b["id"] = f"p1b{nb}"
        if b["role"] != "table":
            b["lines"] = order_lines(b["words"]) if b["words"] else []
            b["text"] = " ".join(" ".join(w["text"] for w in ln) for ln in b["lines"]) if b["lines"] else \
                (b["dots_text"] if b["source"] == "dots" else "")
        b["latin"] = is_latin(b.get("text") or b["dots_text"] or "")
        if b["role"] == "li":
            m = LIST_MARK.match(b["dots_text"])
            first = b["lines"][0][0]["text"] if b.get("lines") else ""
            mk = m.group(1) if m else ""
            b["list_mark"] = mk
            b["label"] = None if (not mk or LIST_MARK.match(first + " ") or first in "-*•●■◆❖▪➢✓") \
                else ("•" if mk in "-*" else mk)
            b["list_type"] = "bullet" if (not mk or mk in "-*•●■◆❖▪➢✓") else "order"
    # captions -> nearest picture/table
    targets = [b for b in blocks if b["role"] in ("figure", "table")]
    for b in blocks:
        if b["role"] != "caption" or not targets:
            continue
        t = b.get("text") or ""
        pref = "table" if re.match(r"^\s*(جدول|الجدول|Table)", t) else ("figure" if re.match(
            r"^\s*(شكل|الشكل|صورة|رسم|Fig)", t) else None)
        cand = [x for x in targets if (pref is None or x["role"] == pref) and not x.get("caption")]
        cand = cand or [x for x in targets if not x.get("caption")]
        if not cand:
            continue
        x = min(cand, key=lambda x: gap(b["box"], x["box"]))
        if gap(b["box"], x["box"]) < 0.08 * H:
            x["caption"] = b["id"]
            b["caption_of"] = x["id"]
    # pictures: crop
    pdir = OUT / "pages" / pid
    (pdir / "crops").mkdir(parents=True, exist_ok=True)
    col = None
    img = None
    import cv2
    for b in blocks:
        if b["role"] in ("figure", "table", "formula"):
            if img is None:
                col = colour_page(pid, meta["stem"], meta["page"])
                img = col if col is not None else page_image(pid)
            x0, y0, x1, y1 = (int(round(v)) for v in b["box"])
            m = 6
            crop = img[max(0, y0 - m):min(H, y1 + m), max(0, x0 - m):min(W, x1 + m)]
            if crop.size:
                cv2.imwrite(str(pdir / "crops" / f"{b['id']}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
                b["crop"] = f"crops/{b['id']}.jpg"
    # 7. the net
    allb = [b["box"] for b in blocks]
    k_out = [l for l in kl if len(folded(l["text"])) >= 3 and not any(
        inter(l["box"], bb) >= 0.5 * (area(l["box"]) or 1) for bb in allb)]
    no_line = []
    for b in blocks:
        for ln in b.get("lines") or []:
            bb = union(w["box"] for w in ln)
            if not any(inter(l["box"], bb) > 0.3 * (area(bb) or 1) for l in kl):
                no_line.append(dict(block=b["id"], text=" ".join(w["text"] for w in ln)[:200], box=bb))
    dots_no_ink = [dict(block=b["id"], text=(b.get("text") or "")[:200]) for b in blocks
                   if b["source"] == "dots" and not kraken_in(b["box"])]
    cells_dots = [dict(table=b["id"], text=c["text"]) for b in blocks if b["role"] == "table" for r in b["rows"]
                  for c in r["cells"] if c["source"] == "dots" and c["text"]]
    nw = len(words)
    placed = sum(len(b["words"]) for b in blocks)
    stats = dict(azure_words=nw, words_in_dots_blocks=nw - len(left), words_near=sum(b.get("near_words", 0)
                 for b in blocks), leftover_words=len(left), leftover_blocks=len(by),
                 words_in_pictures=sum(len(b["words"]) for b in blocks if b["role"] == "figure"),
                 words_placed=placed, every_word_once=placed == nw,
                 dots_blocks=len(dots_blocks(pid)), dots_blocks_no_words=len(dropped) + sum(
                     1 for b in blocks if b["source"] == "dots"),
                 dots_blocks_kept_from_dots=sum(1 for b in blocks if b["source"] == "dots"),
                 dots_blocks_dropped=len(dropped),
                 tables=sum(b["role"] == "table" for b in blocks),
                 table_cells=sum(len(r["cells"]) for b in blocks if b["role"] == "table" for r in b["rows"]),
                 table_cells_azure=sum(c["source"].startswith("azure") for b in blocks if b["role"] == "table"
                                       for r in b["rows"] for c in r["cells"]),
                 table_cells_dots=len(cells_dots),
                 table_words_left=sum(len(b.get("table_leftover") or []) for b in blocks),
                 formulas=sum(b["role"] == "formula" for b in blocks),
                 figures=sum(b["role"] == "figure" for b in blocks),
                 kraken_lines=len(kl), kraken_outside_blocks=len(k_out), azure_lines_no_kraken=len(no_line),
                 dots_text_no_ink=len(dots_no_ink))
    # table leftovers: their own block after the table (still exactly one place)
    final = []
    for b in blocks:
        final.append(b)
        if b["role"] == "table" and b.get("table_leftover"):
            nb += 1
            ws = b["table_leftover"]
            final.append(dict(id=f"p1b{nb}", dots_index=None, cat="(table leftover)", role="p", level=0,
                              box=union(w["box"] for w in ws), dots_text="", words=ws, source="azure-only",
                              lines=order_lines(ws), text=" ".join(w["text"] for w in ws), latin=False))
    for b in final:
        b.pop("table_leftover", None)
    return dict(page_id=pid, stem=meta["stem"], page=meta["page"], width=W, height=H, colour=col is not None,
                blocks=final, dropped=dropped, stats=stats,
                net=dict(kraken_outside=k_out, azure_no_kraken=no_line, dots_no_ink=dots_no_ink,
                         table_cells_from_dots=cells_dots))


def main(argv):
    force = "--force" in argv
    want = [a for a in argv if not a.startswith("--")]
    for meta in pages():
        pid = meta["page_id"]
        if want and pid not in want:
            continue
        f = OUT / "pages" / pid / "layout.json"
        if f.exists() and not force:
            continue
        d = parse_page(pid, meta)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
        s = d["stats"]
        print(f"{pid}: {s['azure_words']} words, left {s['leftover_words']}, pictures {s['words_in_pictures']}, "
              f"dots blocks no words {s['dots_blocks_no_words']} (kept {s['dots_blocks_kept_from_dots']}), "
              f"tables {s['tables']} cells {s['table_cells_azure']}/{s['table_cells']} azure, "
              f"formulas {s['formulas']}, figures {s['figures']}, kraken outside {s['kraken_outside_blocks']}",
              flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
