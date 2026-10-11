"""The second reading of the draft, and where the two readers disagree (experiment 34).

    PYTHONPATH=src python second.py lines  [--limit N]   Gemini reads every draft line from its crop
    PYTHONPATH=src python second.py tables                Gemini drafts tables (HTML) and equations (LaTeX)
    PYTHONPATH=src python second.py mark                  writes draft.gemini, disagree spans and flags into the
                                                          gold files (only lines still todo are touched)

Lines: each line's crop from the 300 dpi page (its box, a tenth of its height added above and below), 12 crops a
request, gemini-3.8-flash, blind (Azure's reading is never shown), asked for the text exactly as printed. Tables
and equations: the whole page, gemini-3.1-pro-preview, tables as HTML (rows top to bottom, cells in reading order,
rowspan/colspan) and equations as LaTeX, each with its box (0-1000 of the page). All cached and logged (gem.py);
the experiment's cap is $15.

Disagreement: Azure's and Gemini's words aligned (difflib on words with vowel marks removed and alef/ya forms
folded); an Azure word Gemini reads differently, or a gap where Gemini has words Azure lacks, is a "disagree" span
(characters of the draft text) and the line gets the flag gemini-differs; a word whose letters agree but whose
hamza, alef or ى/ي forms differ is a span with the flag forms-differ (Azure's commonest real fault on old prints is
a hamza the print leaves out, experiment 19); on a page tagged vowelled, a word whose vowel marks alone differ is a
span with the flag vowels-differ. Gemini's own reading is kept in
draft.gemini so the owner can take it with one key.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

import gem
from inkscript.gold.format import load, pages, save
from inkscript.gold.text import HARAKAT, faithful

OUT = gem.OUT
GOLD = OUT / "gold"
LINES_MODEL, TABLE_MODEL = "gemini-3.8-flash", "gemini-3.1-pro-preview"
PER_REQ = 12
THREADS = 6                      # requests in flight (API-bound; each process stays under 300 MB)

LINE_PROMPT = """Each image above is one printed line cut from a scanned page of an Arabic journal (slivers of the lines
above and below may show at the edges: read only the full line in the middle). Transcribe each line EXACTLY as printed:
- keep every short vowel, tanwin, shadda and sukun that is printed, and add none that is not printed;
- keep hamza and alef forms as printed (do not add a hamza the print leaves out), ى and ي as printed, ة and ه as printed;
- digits as printed (Arabic-Indic ٠١٢ or Western 012), punctuation and brackets as printed;
- no kashida/tatweel; do not correct spelling or grammar; do not complete cut words;
- Latin-script text as printed (with its accents);
- the ligature ﷺ as the single character ﷺ when it is printed as one sign.
If the image holds no text (a speck, a rule, an ornament, a picture), give an empty string. Write ? for a letter you
cannot read. Answer for every image n = 1..{n}."""
LINE_SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "text": {"type": "string"}}, "required": ["n", "text"]}}}, "required": ["lines"]}

TABLE_PROMPT = """This is a scanned page of an Arabic journal. Find every TABLE and every mathematical EQUATION or
formula on it (not ordinary numbers in running text).
For each table give: its box [ymin, xmin, ymax, xmax] on a 0-1000 scale of the page, and its content as one HTML
<table>: <tr> rows from top to bottom, <td> cells in reading order (for an Arabic table the rightmost cell first),
rowspan/colspan for merged cells, header cells as <th>, the cell text EXACTLY as printed (vowel marks, digits as
printed: Arabic-Indic or Western), no styling, no caption (give the caption separately).
For each equation give: its box on the same scale, its LaTeX (amsmath; no $ signs), and display=true when it stands on
its own line. Empty lists when there are none."""
TABLE_SCHEMA = {"type": "object", "properties": {
    "tables": {"type": "array", "items": {"type": "object", "properties": {
        "box_2d": {"type": "array", "items": {"type": "integer"}}, "html": {"type": "string"},
        "caption": {"type": "string"}}, "required": ["box_2d", "html", "caption"]}},
    "equations": {"type": "array", "items": {"type": "object", "properties": {
        "box_2d": {"type": "array", "items": {"type": "integer"}}, "latex": {"type": "string"},
        "display": {"type": "boolean"}}, "required": ["box_2d", "latex", "display"]}}},
    "required": ["tables", "equations"]}


def _img(pid):
    return cv2.imread(str(GOLD / f"{pid}.jpg"), cv2.IMREAD_GRAYSCALE)


def crop(img, box) -> bytes:
    x0, y0, x1, y1 = box
    h = y1 - y0
    pad = max(4, int(0.1 * h))
    H, W = img.shape
    c = img[max(0, int(y0) - pad):min(H, int(y1) + pad), max(0, int(x0) - 8):min(W, int(x1) + 8)]
    return cv2.imencode(".png", c)[1].tobytes()


def lines(limit: int = 0, per: int = PER_REQ) -> int:
    items = []
    for p in pages(GOLD):
        g = load(p)
        for ln in g["lines"]:
            items.append((g["page_id"], ln["id"], ln["box"]))
    if limit:
        items = items[:limit]
    res_f = OUT / "second_lines.json"
    res = json.loads(res_f.read_text()) if res_f.exists() else {}
    todo = [it for it in items if f"{it[0]}:{it[1]}" not in res]
    chunks = [todo[i:i + per] for i in range(0, len(todo), per)]
    est = 0.012
    print(f"{len(todo)} lines, {len(chunks)} requests, estimate ${len(chunks) * est:.2f}; spent ${gem.spent():.3f}",
          flush=True)
    def one(ch):
        crops, imgs = [], {}
        for pid, lid, box in ch:
            if pid not in imgs:
                imgs[pid] = _img(pid)
            crops.append(crop(imgs[pid], box))
        return ch, gem.call(LINES_MODEL, LINE_PROMPT.format(n=len(ch)), crops, LINE_SCHEMA, "lines", est,
                            resolution="medium")

    with ThreadPoolExecutor(THREADS) as ex:
        for k, (ch, a) in enumerate(ex.map(one, chunks), 1):
            if a:
                by = {x["n"]: x["text"] for x in a.get("lines", [])}
                for n, (pid, lid, _) in enumerate(ch, 1):
                    if n in by:
                        res[f"{pid}:{lid}"] = by[n]
            if k % 20 == 0 or k == len(chunks):
                res_f.write_text(json.dumps(res, ensure_ascii=False))
                print(k, f"${gem.spent():.3f}", flush=True)
    res_f.write_text(json.dumps(res, ensure_ascii=False))
    return 0


def tables() -> int:
    res_f = OUT / "second_tables.json"
    res = json.loads(res_f.read_text()) if res_f.exists() else {}
    todo = []
    for p in pages(GOLD):
        g = load(p)
        if {"table", "equation"} & set(g.get("kinds", [])) and g["page_id"] not in res:
            todo.append(g["page_id"])
    est = 0.06
    print(f"{len(todo)} pages, estimate ${len(todo) * est:.2f}; spent ${gem.spent():.3f}", flush=True)

    def one(pid):
        img = _img(pid)
        b = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
        return pid, gem.call(TABLE_MODEL, TABLE_PROMPT, [b], TABLE_SCHEMA, "tables", est, resolution="high",
                             thinking="low", max_out=32768)

    with ThreadPoolExecutor(3) as ex:
        for pid, a in ex.map(one, todo):
            if a:
                res[pid] = a
                res_f.write_text(json.dumps(res, ensure_ascii=False))
            print(pid, f"{len((a or {}).get('tables', []))} tables {len((a or {}).get('equations', []))} eq ${gem.spent():.3f}", flush=True)
    return 0


# ---------------------------------------------------------------- disagreement

_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ی": "ي", "ک": "ك", "ـ": None,
                       **{chr(0x660 + i): str(i) for i in range(10)}, **{chr(0x6f0 + i): str(i) for i in range(10)}})
_P = re.compile(r"[^\w]")
_PDIG = str.maketrans({chr(0x6f0 + i): chr(0x660 + i) for i in range(10)})   # Persian digit shapes = Arabic-Indic


def wkey(w: str) -> str:
    return _P.sub("", HARAKAT.sub("", w).translate(_FOLD))


def lkey(w: str) -> str:
    """Letters as printed: vowel marks, tatweel and punctuation removed; hamza, alef and ya forms kept."""
    return _P.sub("", HARAKAT.sub("", w).replace("ـ", "").translate(_PDIG))


def disagree(az: str, ge: str, vowels: bool) -> tuple[list[list[int]], set]:
    """Char spans of az where ge differs, and the kinds of difference found: "letters" (a word read otherwise),
    "forms" (only hamza / alef / ى-ي forms differ: the old-print hamza Azure adds, experiment 19), "vowels"
    (only vowel marks differ; looked for on vowelled pages only)."""
    aw = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", az) if wkey(m.group())]
    gw = [w for w in ge.split() if wkey(w)]          # punctuation alone is not a disagreement
    sm = difflib.SequenceMatcher(None, [wkey(w) for *_, w in aw], [wkey(w) for w in gw], autojunk=False)
    spans, kinds = [], set()
    for op, i0, i1, j0, j1 in sm.get_opcodes():
        if op == "equal":
            for i, j in zip(range(i0, i1), range(j0, j1)):
                a, g = aw[i][2], gw[j]
                if lkey(a) != lkey(g):
                    spans.append([aw[i][0], aw[i][1]])
                    kinds.add("forms")
                elif vowels and faithful(a) != faithful(g) and HARAKAT.sub("", a) == HARAKAT.sub("", g):
                    spans.append([aw[i][0], aw[i][1]])
                    kinds.add("vowels")
            continue
        kinds.add("letters")
        if i1 > i0:
            spans.append([aw[i0][0], aw[i1 - 1][1]])
        elif aw:                                         # Gemini has words Azure lacks: mark the neighbour
            k = min(i0, len(aw) - 1)
            spans.append([aw[k][0], aw[k][1]])
    if not aw and gw:
        kinds.add("letters")
    return spans, kinds


def _box1000(b, W, H):
    y0, x0, y1, x1 = (b + [0, 0, 1000, 1000])[:4]
    return [round(x0 * W / 1000, 1), round(y0 * H / 1000, 1), round(x1 * W / 1000, 1), round(y1 * H / 1000, 1)]


def _inside(lb, tb, share=0.6) -> bool:
    ix = max(0, min(lb[2], tb[2]) - max(lb[0], tb[0]))
    iy = max(0, min(lb[3], tb[3]) - max(lb[1], tb[1]))
    a = (lb[2] - lb[0]) * (lb[3] - lb[1])
    return a > 0 and ix * iy >= share * a


def mark() -> int:
    L = json.loads((OUT / "second_lines.json").read_text()) if (OUT / "second_lines.json").exists() else {}
    T = json.loads((OUT / "second_tables.json").read_text()) if (OUT / "second_tables.json").exists() else {}
    tot = dict(lines=0, read=0, tables=0, equations=0)
    for p in pages(GOLD):
        g = load(p)
        vowels = "vowelled" in g.get("kinds", [])
        for ln in g["lines"]:
            tot["lines"] += 1
            ge = L.get(f"{g['page_id']}:{ln['id']}")
            if ge is None:                               # Gemini gave no answer (a blocked reply): look at it
                if ln["status"] == "todo" and "no-second" not in ln["flags"]:
                    ln["flags"].append("no-second")
                continue
            tot["read"] += 1
            ln["draft"]["gemini"] = faithful(ge).translate(_PDIG)       # gold uses Arabic-Indic digits
            if ln["status"] != "todo":
                continue
            sp, kinds = disagree(ln["text"], ln["draft"]["gemini"], vowels)
            ln["disagree"] = sp
            ln["flags"] = [f for f in ln["flags"] if f not in ("gemini-differs", "forms-differ", "vowels-differ")]
            for k, flag in (("letters", "gemini-differs"), ("forms", "forms-differ"), ("vowels", "vowels-differ")):
                if k in kinds:
                    ln["flags"].append(flag)
                    tot[flag] = tot.get(flag, 0) + 1
        t = T.get(g["page_id"])
        if t and not g.get("tables") and not g.get("equations"):
            W, H = g["image"]["width"], g["image"]["height"]
            for k, tb in enumerate(t.get("tables", []), 1):
                box = _box1000(tb["box_2d"], W, H)
                rid = f"t{k}"
                g["regions"].append(dict(id=f"rt{k}", type="table", box=box, column=1, article=None,
                                         order=len(g["regions"]) + 1))
                g["tables"].append(dict(id=rid, region=f"rt{k}", box=box, html="", draft_html=tb["html"],
                                        caption=tb.get("caption", ""), status="todo"))
                for ln in g["lines"]:
                    if _inside(ln["box"], box):
                        ln["kind"] = "cell"
                tot["tables"] += 1
            for k, eq in enumerate(t.get("equations", []), 1):
                box = _box1000(eq["box_2d"], W, H)
                g["regions"].append(dict(id=f"re{k}", type="equation", box=box, column=1, article=None,
                                         order=len(g["regions"]) + 1))
                g["equations"].append(dict(id=f"e{k}", region=f"re{k}", box=box, latex="", mathml="",
                                           display=bool(eq.get("display")), draft_latex=eq["latex"], status="todo"))
                if eq.get("display"):
                    for ln in g["lines"]:
                        if _inside(ln["box"], box, 0.7) and len(re.findall("[ء-ي]", ln["text"])) < 4:
                            ln["kind"] = "equation"
                tot["equations"] += 1
        save(p, g, history=False)
    print(tot)
    (OUT / "second_summary.json").write_text(json.dumps(tot))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    per = int(sys.argv[sys.argv.index("--per") + 1]) if "--per" in sys.argv else PER_REQ
    sys.exit(lines(lim, per) if cmd == "lines" else tables() if cmd == "tables" else mark())
