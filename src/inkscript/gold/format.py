"""The gold page file: `inkscript-gold/1` (experiment 34, D26).

One JSON file per page, `<page_id>.json`, `page_id = <stem>_p<NNN>` (page number 1-based, three digits), beside
the page image `<page_id>.jpg` (grey, rendered from the scan at `image.dpi`, 300 by default). All boxes are
`[x0, y0, x1, y1]` in that image's pixels; `poly` is the reader's 4-point polygon when it has one.

    {
      "schema": "inkscript-gold/1",
      "page_id": "0005-055-003-004_p003", "stem": "0005-055-003-004", "page": 3,
      "split": "test" | "dev",                     # test is held out: nothing is ever tuned on it
      "kinds": ["footnotes", "quran", ...],        # what the page was chosen for (selection.json has why)
      "primary": "footnotes", "decade": "1980s", "year": "1985", "journal": "...", "field": "...",
      "image": {"file": "<page_id>.jpg", "dpi": 300, "width": W, "height": H, "angle": 0.0},
      "status": "todo" | "doing" | "done" | "skip",
      "seconds": 0.0,                              # active correcting time (idle gaps over 60 s not counted)
      "rev": 0,                                    # +1 on every save; a save from a stale copy is refused (409)
      "checked": {"by": "owner", "at": "<ISO time>"},
      "regions": [ {"id": "r01", "type": "text|heading|title|footnote|caption|table|equation|figure|furniture|
                                         handwriting|decorative|verse",
                    "box": [...], "column": 1, "article": "a1" | null, "order": 1} ],
      "lines": [ {"id": "l001", "region": "r01", "box": [...], "poly": [...],
                  "kind": "text|heading|title|footnote|caption|cell|equation|furniture|verse",
                  "lang": "ar|la|mixed",
                  "text": "the line exactly as printed",        # the gold, once status is not todo
                  "status": "todo|ok|edited|added|deleted|unsure",
                  "draft": {"azure": "...", "gemini": "..."},   # the readings the draft was made from
                  "words": [{"text", "box", "conf"}],          # Azure's words (draft only; not gold)
                  "disagree": [[i0, i1], ...],                  # char spans of "text" where the readers differ
                  "flags": ["gemini-differs", "forms-differ", "vowels-differ", "low-conf", "no-second"],
                  "seconds": 0.0} ],                            # time spent on this line in the editor
      "order": ["l001", "l002", ...],              # reading order of the lines (the gold order)
      "tables": [ {"id": "t1", "region": "r07", "box": [...], "html": "<table>...</table>",
                   "draft_html": "...", "caption": "", "status": "todo|ok|edited", "seconds": 0.0} ],
      "equations": [ {"id": "e1", "region": "r09", "box": [...], "latex": "...", "mathml": "",
                      "display": true, "draft_latex": "...", "status": "todo|ok|edited", "seconds": 0.0} ],
      "articles": [ {"id": "a1", "title": "l004", "regions": ["r02", "r03"]} ],
      "notes": ""
    }

Text rules (as printed, not as it should be): vowel marks, shadda and sukun kept where printed; hamza and
alef forms as printed (an old print's اهل stays اهل); ى and ي as printed; Arabic-Indic or Western digits as
printed; ﷺ as the one character when printed as a ligature; tatweel (kashida) not typed — it is layout; Persian
code points never (a Persian ی in Azure's reading is an error, the gold has ي/ى). Logical (typing) order, one
space between words. A line that is not text (a speck, an ornament) is `deleted`; ink nobody can read is
`unsure` (kept, scored separately). Tables: one <table> per table, <tr> rows top to bottom, <td>/<th> cells in
reading order (rightmost first on an Arabic table), rowspan/colspan for merged cells, cell text as printed.
Equations: LaTeX (amsmath), MathML optional. Lines inside a table are also lines (kind "cell"); lines of an
equation are kind "equation" and are scored by the equation metric, not the text CER.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

SCHEMA = "inkscript-gold/1"
LINE_STATUS = ("todo", "ok", "edited", "added", "deleted", "unsure")
PAGE_STATUS = ("todo", "doing", "done", "skip")
REGION_TYPES = ("text", "heading", "title", "footnote", "caption", "table", "equation", "figure", "furniture",
                "handwriting", "decorative", "verse")
LINE_KINDS = ("text", "heading", "title", "footnote", "caption", "cell", "equation", "furniture", "verse")
_ID = re.compile(r"^[0-9A-Za-z,_.-]+_p\d{3}$")


def page_id(stem: str, page: int) -> str:
    return f"{stem}_p{page:03d}"


def split_page_id(pid: str) -> tuple[str, int]:
    stem, _, p = pid.rpartition("_p")
    return stem, int(p)


def valid_id(pid: str) -> bool:
    return bool(_ID.match(pid)) and ".." not in pid


def check(g: dict) -> list[str]:
    """Problems with a page file (empty list = fine)."""
    out = []
    if g.get("schema") != SCHEMA:
        out.append(f"schema is {g.get('schema')!r}")
    if not valid_id(g.get("page_id", "")):
        out.append(f"bad page_id {g.get('page_id')!r}")
    if g.get("status") not in PAGE_STATUS:
        out.append(f"page status {g.get('status')!r}")
    ids = [ln.get("id") for ln in g.get("lines", [])]
    if len(set(ids)) != len(ids):
        out.append("duplicate line ids")
    for ln in g.get("lines", []):
        if ln.get("status") not in LINE_STATUS:
            out.append(f"{ln.get('id')}: status {ln.get('status')!r}")
        b = ln.get("box")
        if not (isinstance(b, list) and len(b) == 4 and b[0] <= b[2] and b[1] <= b[3]):
            out.append(f"{ln.get('id')}: box {b!r}")
        if not isinstance(ln.get("text", ""), str):
            out.append(f"{ln.get('id')}: text not a string")
    order = g.get("order", [])
    if sorted(order) != sorted(i for i in ids):
        out.append("order is not a permutation of the line ids")
    return out


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path: Path, g: dict, history: bool = True) -> None:
    """Atomic write; the previous version goes to .history/<page_id>/<time>.json (a correction is never lost)."""
    path = Path(path)
    if history and path.exists():
        h = path.parent / ".history" / path.stem
        h.mkdir(parents=True, exist_ok=True)
        (h / time.strftime("%Y%m%d-%H%M%S.json")).write_bytes(path.read_bytes())
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def pages(gold_dir: Path) -> list[Path]:
    return sorted(p for p in Path(gold_dir).glob("*_p[0-9][0-9][0-9].json"))


def gold_lines(g: dict, kinds: tuple | None = None, include_unsure: bool = True) -> list[dict]:
    """The page's lines in reading order that count as gold text (deleted and still-todo lines left out unless the
    page is a draft being scored as a smoke test: pass the page with status todo and they count as drafts)."""
    by = {ln["id"]: ln for ln in g.get("lines", [])}
    out = []
    for i in g.get("order", []):
        ln = by.get(i)
        if ln is None or ln.get("status") == "deleted":
            continue
        if ln.get("status") == "unsure" and not include_unsure:
            continue
        if kinds and ln.get("kind", "text") not in kinds:
            continue
        out.append(ln)
    return out


def progress(gold_dir: Path) -> dict:
    """Pages and lines done, seconds spent, for the progress bar and `score`."""
    n_pages = done_pages = n_lines = done_lines = 0
    secs = 0.0
    todo_dis = 0
    for p in pages(gold_dir):
        g = load(p)
        n_pages += 1
        done_pages += g.get("status") in ("done", "skip")
        secs += g.get("seconds", 0.0)
        for ln in g.get("lines", []):
            n_lines += 1
            if ln.get("status") != "todo" or g.get("status") in ("done", "skip"):
                done_lines += 1
            elif ln.get("disagree") or ln.get("flags"):
                todo_dis += 1
    return dict(pages=n_pages, pages_done=done_pages, lines=n_lines, lines_done=done_lines,
                lines_todo_flagged=todo_dis, seconds=round(secs, 1))


# ---------------------------------------------------------------- ALTO 4.4 export (interchange; the JSON is the gold)

def to_alto(g: dict) -> bytes:
    """ALTO 4.4: one TextBlock per region (in region order), TextLines in reading order with their gold text as
    whole-line String elements (word boxes are not gold), lines in reading order within their region; tables and equations are
    not ALTO's business (they stay in the JSON / go to JATS as XHTML and MathML)."""
    from lxml import etree
    NS = "http://www.loc.gov/standards/alto/ns-v4#"
    X = lambda s: "g" + re.sub(r"[^0-9A-Za-z_.-]", "_", s)          # an XML ID (NCName) from a page id
    E = lambda tag, **kw: etree.Element(f"{{{NS}}}{tag}", **{k: str(v) for k, v in kw.items()})
    root = etree.Element(f"{{{NS}}}alto", nsmap={None: NS})
    desc = etree.SubElement(root, f"{{{NS}}}Description")
    etree.SubElement(desc, f"{{{NS}}}MeasurementUnit").text = "pixel"
    sii = etree.SubElement(desc, f"{{{NS}}}sourceImageInformation")
    etree.SubElement(sii, f"{{{NS}}}fileName").text = g["image"]["file"]
    layout = etree.SubElement(root, f"{{{NS}}}Layout")
    page = E("Page", ID=X(g["page_id"]), PHYSICAL_IMG_NR=g["page"], WIDTH=g["image"]["width"],
             HEIGHT=g["image"]["height"])
    layout.append(page)
    ps = E("PrintSpace", HPOS=0, VPOS=0, WIDTH=g["image"]["width"], HEIGHT=g["image"]["height"])
    page.append(ps)
    lines = gold_lines(g)
    regions = {r["id"]: r for r in g.get("regions", [])}
    blocks: dict[str, object] = {}
    for ln in lines:
        rid = ln.get("region") or "r00"
        if rid not in blocks:
            r = regions.get(rid, {"box": ln["box"]})
            x0, y0, x1, y1 = r["box"]
            tb = E("TextBlock", ID=X(f"{g['page_id']}_{rid}"), HPOS=x0, VPOS=y0, WIDTH=x1 - x0, HEIGHT=y1 - y0)
            ps.append(tb)
            blocks[rid] = tb
        x0, y0, x1, y1 = ln["box"]
        tl = E("TextLine", ID=X(f"{g['page_id']}_{ln['id']}"), HPOS=x0, VPOS=y0, WIDTH=x1 - x0, HEIGHT=y1 - y0)
        tl.append(E("String", CONTENT=ln.get("text", ""), HPOS=x0, VPOS=y0, WIDTH=x1 - x0, HEIGHT=y1 - y0))
        blocks[rid].append(tl)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
