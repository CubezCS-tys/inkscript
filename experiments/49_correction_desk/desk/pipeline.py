"""How a page is read (2026-10-30): one scanned page taken through the pipeline, stage by stage, from the real data,
for the Desk's /pipeline page (an animated walk-through the owner can show).

    GET /desk/api/pipeline/{stem}?page=N      everything the page shows for one page of one article

Read-only. What it reads, all on this machine:
- the release copy (or platform_v2.db) the Desk reads: the page, Azure's numbered lines (`azure_lines`), the blocks
  and their boxes, the regions kept out of the text, fixes, flags, judge looks and patches, the article's fields
  (`pages.article`) and the entities they resolve to (persons A…, institutions I…, cited works C…, journal J…);
- the article's ALTO master (`43_rehearsal/out/<versions.masters_key>`, .alto.xml): every Azure word with its box
  and its id `p<page>w<nnnn>` (= Azure's word number on the page, the numbering every ink anchor uses);
- Gemini's own answer for the chunk holding the page (`43_rehearsal/out/<run>/raw/<stem>_cAAA-BBB.json`, looked up
  in the run and the runs it was built from: `v33_300_final_lettersfix` → `v33_300_final` → `v33_300`), else the
  answer after the code rules (`rules/`), else the roles the masters hold (`line_map`).

Boxes are in the ALTO frame (`pages.width_px` × `height_px`); the screen turns them into fractions of the page.
File names never come from the request: the stem is checked against the reading, the run comes from the database,
and every path is checked to sit under experiment 43's out/."""
from __future__ import annotations

import json
import os
import re
import threading
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from . import api as A
from . import pages as P
from . import scan as S
from .crops import CropError

router = APIRouter()
E43 = Path(__file__).resolve().parents[2] / "43_rehearsal" / "out"
ALTO_NS = "{http://www.loc.gov/standards/alto/ns-v4#}"
WORD_ID = re.compile(r"p(\d+)w(\d+)$")
LINE_ID = re.compile(r"^(\d+):(\d+)$")
ANCHOR_W = re.compile(r"\|p(\d+)\|w(\d+)-(\d+)$")
ANCHOR_B = re.compile(r"\|p(\d+)\|b([\d.]+),([\d.]+),([\d.]+),([\d.]+)$")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Gemini's block types → the role shown on the page (one colour each on the screen)
ROLE_OF_TYPE = {
    "title": "title", "trans_title": "title", "subtitle": "title",
    "byline": "byline", "affiliation": "byline", "author": "byline",
    "abstract": "abstract", "keywords": "keywords",
    "heading": "heading",
    "paragraph": "paragraph", "list_item": "list", "quote": "quote", "boxed": "paragraph", "other": "paragraph",
    "verse": "verse",
    "footnote": "footnote", "endnote": "footnote",
    "reference": "reference",
    "table": "table", "caption": "caption", "figure": "figure", "equation": "figure",
    "header": "running", "footer": "running",
    "noise": "noise", "other_article": "other_article",
}
ROLE_LABEL = {
    "title": "Title", "byline": "Byline", "abstract": "Abstract", "keywords": "Keywords",
    "heading": "Heading", "paragraph": "Paragraph", "list": "List item", "quote": "Quotation", "verse": "Verse",
    "footnote": "Footnote", "reference": "Reference", "table": "Table cell", "caption": "Caption",
    "figure": "Figure", "running": "Running head", "page_number": "Page number", "noise": "Noise (no words)",
    "other_article": "Another article", "note_call": "Note call",
}
# blocks of the masters (their closed list) → the same roles, for an article without Gemini's answer on this machine
ROLE_OF_BLOCK = {"title": "title", "title-translated": "title", "byline": "byline", "affiliation": "byline",
                 "front-matter": "byline", "abstract": "abstract", "keywords": "keywords", "heading": "heading",
                 "paragraph": "paragraph", "list-item": "list", "footnote": "footnote", "endnote": "footnote",
                 "ref": "reference", "caption": "caption", "table-cell": "table", "verse-group": "verse",
                 "quote": "quote", "back-matter": "paragraph"}
ROLE_OF_REGION = {"pageHeader": "running", "pageFooter": "running", "pageNumber": "page_number", "noise": "noise",
                  "otherArticle": "other_article", "pictureText": "figure", "pictureJunk": "figure",
                  "formulaInk": "figure", "ornament": "noise", "showThrough": "noise"}

_lock = threading.Lock()
_alto_cache: OrderedDict = OrderedDict()


# ------------------------------------------------------------------ files (all under experiment 43's out/)
def _under_e43(p: Path) -> Path | None:
    """The path, if it is written under experiment 43's out/ (no '..' escapes) and is a file. Run folders there may
    be symlinks into other experiments' out/ (gate 1's j0130 lives in experiment 52), so the check is on the
    path as written, not as resolved."""
    r = Path(os.path.normpath(p))
    return r if r.is_relative_to(Path(os.path.normpath(E43))) and r.is_file() else None


def alto_path(masters_key: str | None, stem: str) -> Path | None:
    if not masters_key or not masters_key.endswith(".jats.xml"):
        return None
    return _under_e43(E43 / (masters_key[: -len(".jats.xml")] + ".alto.xml"))


def _runs_from(run: str) -> list[str]:
    """The run and the runs it was built from (v33_300_final_lettersfix → v33_300_final → v33_300)."""
    parts = run.split("_")
    return ["_".join(parts[:i]) for i in range(len(parts), 0, -1)]


def answer_chunk(run: str, stem: str, page: int, subs=("raw", "rules")) -> tuple[dict | None, str | None]:
    """Gemini's answer for the chunk holding the page: (chunk json, 'raw' | 'rules'), or (None, None)."""
    if not re.fullmatch(r"[0-9A-Za-z_\-]{1,80}", run or ""):
        return None, None
    for sub in subs:
        for r in _runs_from(run):
            d = E43 / r / sub
            if not d.is_dir():
                continue
            for f in sorted(d.glob(f"{stem}_c*.json")):
                m = re.search(r"_c(\d+)-(\d+)\.json$", f.name)
                if m and int(m.group(1)) <= page <= int(m.group(2)) and _under_e43(f):
                    try:
                        return json.loads(f.read_text()), sub
                    except (OSError, ValueError):
                        continue
    return None, None


def _alto_pages(path: Path) -> dict:
    """page → {words: [...], blocks: {...}, lines: {...}} from one ALTO master (cached by path and mtime)."""
    key = (str(path), path.stat().st_mtime)
    with _lock:
        if key in _alto_cache:
            _alto_cache.move_to_end(key)
            return _alto_cache[key]
    out: dict = {}
    root = ET.parse(path).getroot()
    for pg in root.iter(ALTO_NS + "Page"):
        n = int(pg.get("PHYSICAL_IMG_NR") or pg.get("ID", "page0")[4:] or 0)
        words, blocks = [], {}
        for tb in pg.iter(ALTO_NS + "TextBlock"):
            bid = tb.get("ID")
            blocks[bid] = dict(id=bid, tag=(tb.get("TAGREFS") or "").split(" ")[0].replace("role.", ""))
            for tl in tb.iter(ALTO_NS + "TextLine"):
                for s in tl.iter(ALTO_NS + "String"):
                    m = WORD_ID.match(s.get("ID") or "")
                    if not m:
                        continue
                    alt = s.find(ALTO_NS + "ALTERNATIVE")
                    words.append(dict(n=int(m.group(2)), t=s.get("CONTENT") or "",
                                      x=_f(s.get("HPOS")), y=_f(s.get("VPOS")), w=_f(s.get("WIDTH")), h=_f(s.get("HEIGHT")),
                                      wc=_f(s.get("WC")), az=alt.text if alt is not None else None,
                                      line=tl.get("ID"), block=bid))
        out[n] = dict(words=sorted(words, key=lambda w: w["n"]), blocks=blocks)
    with _lock:
        _alto_cache[key] = out
        while len(_alto_cache) > 6:
            _alto_cache.popitem(last=False)
    return out


def _f(v) -> float | None:
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ boxes
def _union(rs: list[dict]) -> dict | None:
    rs = [r for r in rs if r and r.get("x") is not None and r.get("w") is not None]
    if not rs:
        return None
    x0, y0 = min(r["x"] for r in rs), min(r["y"] for r in rs)
    x1, y1 = max(r["x"] + r["w"] for r in rs), max(r["y"] + r["h"] for r in rs)
    return dict(x=round(x0, 1), y=round(y0, 1), w=round(x1 - x0, 1), h=round(y1 - y0, 1))


class Ink:
    """Turns an anchor key, a word span, a block id or a line list into boxes on this page (one box per printed line,
    so a highlight hugs the ink instead of covering a whole column)."""

    def __init__(self, page: int, words: list[dict], lines: list[dict], block_boxes: dict):
        self.page = page
        self.by_n = {w["n"]: w for w in words}
        self.line_of_word = {}
        for ln in lines:
            for k in range(ln["a"] or 0, (ln["b"] or -1) + 1):
                self.line_of_word[k] = ln["n"]
        self.line_box = {ln["n"]: ln for ln in lines}
        self.block_boxes = block_boxes

    def words(self, a: int, b: int) -> list[dict]:
        groups: dict = defaultdict(list)
        for k in range(a, b + 1):
            w = self.by_n.get(k)
            if w:
                groups[self.line_of_word.get(k, w["line"])].append(w)
        return [u for u in (_union(g) for g in groups.values()) if u]

    def anchor(self, key: str | None) -> list[dict]:
        if not key:
            return []
        m = ANCHOR_W.search(key)
        if m and int(m.group(1)) == self.page:
            return self.words(int(m.group(2)), int(m.group(3)))
        m = ANCHOR_B.search(key)
        if m and int(m.group(1)) == self.page:
            return [dict(x=float(m.group(2)), y=float(m.group(3)), w=float(m.group(4)), h=float(m.group(5)))]
        return []

    def block(self, bid: str | None) -> list[dict]:
        return list(self.block_boxes.get(bid) or [])

    def lines(self, ns) -> list[dict]:
        return [dict(x=l["x"], y=l["y"], w=l["w"], h=l["h"]) for n in ns if (l := self.line_box.get(n))]


def _anchor_page(key: str | None) -> int | None:
    m = re.search(r"\|p(\d+)\|", key or "")
    return int(m.group(1)) if m else None


# ------------------------------------------------------------------ Gemini's answer for the page
def _line_ids(x, out: list, page: int):
    """Every 'P:N' line id under a 'lines' key (tables nest them in rows → cells), in order."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "lines" and isinstance(v, list):
                for s in v:
                    m = LINE_ID.match(str(s))
                    if m and int(m.group(1)) == page:
                        out.append(int(m.group(2)))
            elif isinstance(v, (dict, list)) and k not in ("parsed", "calls"):
                _line_ids(v, out, page)
    elif isinstance(x, list):
        for v in x:
            _line_ids(v, out, page)
    return out


def _gemini_blocks(chunk: dict, page: int) -> list[dict]:
    ans = (chunk or {}).get("answer") or {}
    for p in ans.get("pages") or []:
        if p.get("page") == page:
            out = []
            for i, b in enumerate(p.get("blocks") or []):
                t = b.get("type") or "other"
                lines = list(dict.fromkeys(_line_ids(b, [], page)))
                calls = []
                for c in b.get("calls") or []:
                    m = LINE_ID.match(str(c.get("line") or ""))
                    if m and int(m.group(1)) == page:
                        calls.append(dict(line=int(m.group(2)), marker=str(c.get("marker") or ""), fn=c.get("fn")))
                out.append(dict(i=i, type=t, role=ROLE_OF_TYPE.get(t, "paragraph"), lang=b.get("lang"),
                                level=b.get("level"), marker=b.get("marker"), note=b.get("id"),
                                translated=bool(b.get("translated")), lines=lines, calls=calls,
                                parsed=len(b.get("parsed") or []) or None,
                                cells=sum(len(r) for r in b.get("rows") or []) or None))
            return out
    return []


def _on_page(items, page: int) -> list:
    out = []
    for x in items or []:
        m = LINE_ID.match(str(x.get("line") or ""))
        if m and int(m.group(1)) == page:
            out.append(dict(x, line=int(m.group(2))))
    return out


# ------------------------------------------------------------------ the whole story of one page
def page_story(path: Path, stem: str, page: int) -> dict:
    con = P.open_ro(path)
    try:
        return _story(con, path, stem, page)
    finally:
        con.close()


def _story(con, path: Path, stem: str, page: int) -> dict:
    vid, run = S._doc(con, stem)
    pg = con.execute("SELECT width_px, height_px, image_w, image_h, dpi, printed_folio, n_words, wc_mean, n_low_wc "
                     "FROM pages WHERE stem = ? AND page = ?", (stem, page)).fetchone()
    if not pg:
        raise CropError(404, "no such page in the reading")
    n_pages = con.execute("SELECT count(*) FROM pages WHERE stem = ?", (stem,)).fetchone()[0]
    ver = con.execute("SELECT masters_key, pages_covered, usd, n_chunks FROM versions WHERE version_id = ?",
                      (vid,)).fetchone()
    ap = alto_path(ver[0], stem)
    if ap is None:
        raise CropError(404, "this article's masters are not on this server")
    alto = _alto_pages(ap).get(page) or dict(words=[], blocks={})
    words = alto["words"]

    # ---- 2 · Azure: lines with their numbers ("P:N"), words with their boxes
    lines = [dict(n=r[0], x=r[1], y=r[2], w=r[3], h=r[4], a=r[5], b=r[6], text=r[7]) for r in con.execute(
        "SELECT line_no, x, y, w, h, first_word, last_word, text FROM azure_lines WHERE stem = ? AND page = ? "
        "ORDER BY line_no", (stem, page))]
    line_of_word = {}
    for ln in lines:
        for k in range(ln["a"] or 0, (ln["b"] or -1) + 1):
            line_of_word[k] = ln["n"]
    wc = [w["wc"] for w in words if w["wc"] is not None]

    # ---- the masters' blocks and kept-out regions on the page (ALTO frame)
    parts: dict = defaultdict(list)
    for r in con.execute("SELECT block_id, x, y, w, h FROM block_parts WHERE version_id = ? AND page = ?", (vid, page)):
        if r[1] is not None:
            parts[r[0]].append(dict(x=r[1], y=r[2], w=r[3], h=r[4]))
    blocks = []
    for r in con.execute("SELECT block_id, ord, role, text, role_source, n_fixes, n_flags, figure_id, note_id, "
                         "section_id FROM blocks WHERE version_id = ? AND (page = ? OR block_id IN (SELECT block_id "
                         "FROM block_parts WHERE version_id = ? AND page = ?)) ORDER BY ord", (vid, page, vid, page)):
        bx = parts.get(r[0])
        if not bx:
            continue
        blocks.append(dict(id=r[0], ord=r[1], role=r[2], shown=ROLE_OF_BLOCK.get(r[2], "paragraph"),
                           text=(r[3] or "")[:160], source=r[4], fixes=r[5] or 0, flags=r[6] or 0, boxes=bx))
    regions = [dict(id=r[0], role=r[1], shown=ROLE_OF_REGION.get(r[1], "noise"), text=r[2], decided_by=r[3],
                    box=dict(x=r[4], y=r[5], w=r[6], h=r[7]))
               for r in con.execute("SELECT region_id, role, text, decided_by, x, y, w, h FROM page_regions WHERE "
                                    "version_id = ? AND page = ? ORDER BY y", (vid, page)) if r[4] is not None]
    region_role = {}
    for r in con.execute("SELECT m.azure_line_no, g.role FROM line_map m JOIN page_regions g ON g.version_id = "
                         "m.version_id AND g.region_id = m.region_id WHERE m.version_id = ? AND m.page = ?", (vid, page)):
        region_role[r[0]] = ROLE_OF_REGION.get(r[1], "noise")
    block_of_line = {r[0]: r[1] for r in con.execute(
        "SELECT azure_line_no, block_id FROM line_map WHERE version_id = ? AND page = ? AND block_id IS NOT NULL",
        (vid, page))}
    ink = Ink(page, words, lines, {b["id"]: b["boxes"] for b in blocks})

    # ---- 3 · Gemini's answer: each line's role, the reading order, in line ids only
    chunk, chunk_kind = answer_chunk(run, stem, page)
    gblocks = _gemini_blocks(chunk, page) if chunk else []
    if gblocks:
        for b in gblocks:                       # a header / footer line the masters call a page number
            if b["role"] == "running" and b["lines"] and all(region_role.get(n) == "page_number" for n in b["lines"]):
                b["role"] = "page_number"
        source = "gemini" if chunk_kind == "raw" else "gemini-after-rules"
    else:                                       # no answer on this machine: the roles the masters hold, in their order
        source = "masters"
        role_of_block = {b["id"]: b for b in blocks}
        seen: dict = {}
        for ln in lines:
            bid = block_of_line.get(ln["n"])
            key = bid or f"region:{region_role.get(ln['n'], 'noise')}"
            if key not in seen:
                b = role_of_block.get(bid)
                seen[key] = dict(i=len(seen), type=b["role"] if b else "region",
                                 role=b["shown"] if b else region_role.get(ln["n"], "noise"),
                                 lines=[], calls=[], ord=b["ord"] if b else 10 ** 6)
            seen[key]["lines"].append(ln["n"])
        gblocks = sorted(seen.values(), key=lambda b: (b["ord"], b["lines"][0]))
        for i, b in enumerate(gblocks):
            b["i"] = i
    role_of_line = {}
    for b in gblocks:
        for n in b["lines"]:
            role_of_line.setdefault(n, b["role"])
    for ln in lines:
        ln["role"] = role_of_line.get(ln["n"])
        ln["block"] = next((b["i"] for b in gblocks if ln["n"] in b["lines"]), None)
    ans = (chunk or {}).get("answer") or {}
    fixes_g = _on_page(ans.get("fixes"), page)
    sic_g = _on_page(ans.get("sic"), page)
    calls_g = [dict(c, block=b["i"]) for b in gblocks for c in b["calls"]]
    for c in calls_g:                           # the call mark's own word, else its line
        mk = c["marker"].translate(DIGITS).strip("()[]*")
        ln = next((l for l in lines if l["n"] == c["line"]), None)
        hit = None
        if ln and mk:
            cand = [w for w in words if ln["a"] <= w["n"] <= ln["b"]]
            hit = next((w for w in cand if mk in (w["t"] or "").translate(DIGITS)), None)
        c["box"] = (dict(x=hit["x"], y=hit["y"], w=hit["w"], h=hit["h"]) if hit else
                    (dict(x=ln["x"], y=ln["y"], w=ln["w"], h=ln["h"]) if ln else None))

    # ---- 4 · code rules: fixes on the page (from the ALTO, with the reason recorded), flags, rules that fired
    fixes, misprints, seen_w = [], [], set()
    for r in con.execute("SELECT t.layer, t.azure_reading, t.printed, t.proposed, t.why, i.anchor_key FROM "
                         "text_corrections t LEFT JOIN ink_anchors i ON i.anchor_pk = t.anchor_pk WHERE t.version_id = ? "
                         "AND i.page = ? ORDER BY t.corr_pk", (vid, page)):
        m = ANCHOR_W.search(r[5] or "")
        bx = ink.anchor(r[5])
        if not m or not bx:
            continue
        reason = r[4] or ""
        if r[0] in ("misprint", "model-suggestion"):     # exp 68: a D30-guard refusal is shown with the flags
            misprints.append(dict(word=int(m.group(2)), printed=r[2], proposed=r[3], why=reason, box=bx[0],
                                  kind=r[0]))
        else:
            seen_w.update(range(int(m.group(2)), int(m.group(3)) + 1))
            fixes.append(dict(word=int(m.group(2)), azure=r[1], printed=r[2], why=reason,
                              by="code" if reason.startswith("code:") else "gemini", letter="letters43" in reason,
                              box=bx[0]))
    for w in words:                             # a fix the ALTO holds that the ledger placed elsewhere
        if w["az"] is not None and w["az"] != w["t"] and w["n"] not in seen_w:
            fixes.append(dict(word=w["n"], azure=w["az"], printed=w["t"], why="", by="gemini", letter=False,
                              box=dict(x=w["x"], y=w["y"], w=w["w"], h=w["h"])))
    flags = [dict(kind=r[0], severity=r[1], reason=r[2], boxes=ink.anchor(r[3]) or ink.block(r[4]))
             for r in con.execute("SELECT f.kind, f.severity, f.reason, i.anchor_key, f.block_id FROM flags f LEFT JOIN "
                                  "ink_anchors i ON i.anchor_pk = f.anchor_pk WHERE f.version_id = ? AND f.page = ?",
                                  (vid, page))]
    fired = []
    ruled = chunk if chunk_kind == "rules" else answer_chunk(run, stem, page, subs=("rules",))[0]
    for k, v in ((ruled or {}).get("rules43") or {}).items():
        n = len(v) if isinstance(v, list) else (v if isinstance(v, int) else 0)
        if n:
            fired.append(dict(rule=k, n=n))

    # ---- 5 · the judge and patches
    judged = [dict(page=r[0], verdict=r[1], model=r[2]) for r in con.execute(
        "SELECT page, verdict, model FROM judge_calls WHERE stem = ? GROUP BY page ORDER BY page", (stem,))]
    findings = [dict(type=r[0], subtype=r[1], confidence=r[2], route=r[3], action=r[4], boxes=ink.anchor(r[5]))
                for r in con.execute("SELECT f.type, f.subtype, f.confidence, f.route, f.action, i.anchor_key FROM "
                                     "judge_findings f JOIN judge_calls c ON c.call_id = f.call_id LEFT JOIN ink_anchors i "
                                     "ON i.anchor_pk = f.anchor_pk WHERE c.stem = ? AND c.page = ?", (stem, page))]
    patches = [dict(op=r[0], source=r[1], page=r[2], reason=r[3], status=r[4]) for r in con.execute(
        "SELECT p.op, p.source, p.page, p.reason, (SELECT a.status FROM patch_applications a WHERE a.patch_key = "
        "p.patch_key AND a.version_id = ? ORDER BY a.load_id DESC LIMIT 1) FROM patches p WHERE p.stem = ? AND "
        "p.domain = 'content' ORDER BY p.page", (vid, stem))]

    # ---- 6 · the fields on this page, each with its ink, and the entities they resolve to
    art = P.article(path, stem) or {}
    fields, entities = _fields(con, art, page, ink, blocks, calls_g)
    entities += _article_entities(con, art)
    _entity_counts(con, entities)
    index = _index_record(con, art)

    # ---- which pages of this article show each kind of thing (the picker's quick switches)
    suggest = dict(front=1)
    r = con.execute("SELECT min(page) FROM notes WHERE version_id = ?", (vid,)).fetchone()
    if r[0]:
        suggest["footnotes"] = r[0]
    r = con.execute("SELECT min(page) FROM figures WHERE version_id = ? AND kind = 'table'", (vid,)).fetchone()
    if r[0]:
        suggest["table"] = r[0]
    r = con.execute("SELECT min(page) FROM citation_mentions WHERE version_id = ? AND container_kind = 'ref-list'",
                    (vid,)).fetchone()
    if r[0]:
        suggest["references"] = r[0]
    elif (r := con.execute("SELECT min(page) FROM notes WHERE version_id = ? AND first_block_id IN (SELECT block_id "
                           "FROM citation_mentions WHERE version_id = ?)", (vid, vid)).fetchone())[0]:
        suggest["references"] = r[0]

    r = con.execute("SELECT min(c.page) FROM judge_calls c WHERE c.stem = ? AND (c.verdict = 'problems' OR "
                    "c.page IN (SELECT page FROM patches WHERE stem = ?))", (stem, stem)).fetchone()
    if r[0]:
        suggest["judged"] = r[0]

    roles_present = [k for k, _ in Counter(b["role"] for b in gblocks).most_common()]
    n_kept = sum(1 for g in regions)
    counts = {
        "scan": dict(page=page, pages=n_pages, width=pg[2], height=pg[3], dpi=pg[4] or 300),
        "azure": dict(words=len(words), lines=len(lines), wc_mean=round(sum(wc) / len(wc), 3) if wc else None,
                      low_wc=sum(1 for x in wc if x < 0.8)),
        "gemini": dict(lines=sum(1 for l in lines if l["role"]), blocks=len(gblocks), roles=len(roles_present),
                       calls=len(calls_g), fixes=len(fixes_g), sic=len(sic_g)),
        "rules": dict(blocks=len(blocks), fixes=len(fixes), letter_fixes=sum(1 for f in fixes if f["letter"]),
                      code_fixes=sum(1 for f in fixes if f["by"] == "code"), misprints=len(misprints),
                      kept_out=n_kept, flags=len(flags)),
        "judge": dict(flags=len(flags), judged_pages=len(judged), this_page=any(j["page"] == page for j in judged),
                      findings=len(findings), patches=sum(1 for p in patches if p["page"] == page),
                      patches_article=len(patches)),
        "platform": _platform_counts(fields, entities),
        "index": dict(references=index["references"], on_cards=index["on_cards"], held=index["held"],
                      times_cited=index["times_cited"]),
    }
    return dict(
        stem=stem, page=page, pages=n_pages, run=run, folio=pg[5],
        frame=dict(w=pg[0], h=pg[1]), image=S.source_of(con, stem, page) is not None,
        image_url=f"/desk/api/evidence/page?stem={stem}&page={page}&w=1400",
        title=(art.get("title") or {}).get("shown"), journal=(art.get("journal") or {}).get("title"),
        answer=dict(source=source, prompt=(chunk or {}).get("prompt"), model="gemini-4-argon" if chunk else None,
                    chunk=[chunk.get("first"), chunk.get("last")] if chunk else None,
                    usd=round(chunk["usd"], 4) if chunk and chunk.get("usd") is not None else None,
                    blocks=gblocks, fixes=fixes_g, sic=sic_g, calls=calls_g, roles=roles_present),
        words=[dict(n=w["n"], t=w["t"], x=w["x"], y=w["y"], w=w["w"], h=w["h"], wc=w["wc"],
                    l=line_of_word.get(w["n"])) for w in words],
        lines=[{k: v for k, v in l.items() if k not in ("a", "b")} | dict(words=[l["a"], l["b"]]) for l in lines],
        blocks=blocks, regions=regions, fixes=fixes, misprints=misprints, flags=flags, rules_fired=fired,
        judge=dict(calls=judged, findings=findings, patches=patches),
        fields=fields, entities=entities, index=index, suggest=suggest, counts=counts,
        role_labels=ROLE_LABEL)


def _fields(con, art: dict, page: int, ink: Ink, blocks: list[dict], calls_g: list[dict]) -> tuple[list, list]:
    """The fields read from this page, in the order the cards show them, each with its boxes on the page, and the
    entities (with their permanent ids) they resolve to."""
    F: list[dict] = []
    E: dict = {}

    def field(kind, label, value, boxes, lang=None, ents=(), **extra):
        if value in (None, "", []):
            return None
        f = dict(id=f"f{len(F) + 1}", kind=kind, label=label, value=value, lang=lang, boxes=boxes,
                 entities=[e for e in ents if e], **extra)
        F.append(f)
        return f

    def entity(eid, kind, name, **extra):
        if not eid:
            return None
        if eid not in E:
            E[eid] = dict(id=eid, kind=kind, name=name, **extra)
        return eid

    by_role = defaultdict(list)
    for b in blocks:
        by_role[b["role"]].append(b)
    full = {b["block_id"]: b for b in art.get("blocks") or []}
    for b in by_role.get("title", []):
        field("title", "Title", full.get(b["id"], {}).get("text") or b["text"], ink.block(b["id"]), lang="ar"
              if P._script(b["text"]) == "ar" else "en", ents=[art.get("pub_id")])
    for b in by_role.get("title-translated", []):
        field("title", "Translated title", full.get(b["id"], {}).get("text") or b["text"], ink.block(b["id"]),
              lang="en" if P._script(b["text"]) != "ar" else "ar")
    # authors: each byline printed on this page, its affiliations split into parts, the person and institutions
    for au in art.get("authors") or []:
        for bl in au.get("bylines") or []:
            if _anchor_page(bl.get("anchor")) != page:
                continue
            pid = entity(au.get("person_id"), "person", au.get("preferred_name_ar") or au.get("name"),
                         latin=au.get("preferred_name_lat"), authority=au.get("authority_id"))
            field("author", "Author", bl["printed"], ink.anchor(bl.get("anchor")), lang=P._script(bl["printed"]),
                  ents=[pid], email=bl.get("email"), titles=bl.get("titles"), role=bl.get("role_phrase"),
                  twin=bool(bl.get("twin")), method=au.get("method"))
            for af in bl.get("affiliations") or []:
                insts = [entity(i["inst_id"], "institution", i["name"], level=i.get("level"), inst_kind=i.get("kind"),
                                country=i.get("country_code")) for i in af.get("institutions") or []]
                bx = ink.anchor(af.get("anchor")) or _find_text(ink, af["printed"]) or ink.anchor(bl.get("anchor"))
                parts = [dict(part=k, value=af.get(c)) for k, c in (
                    ("position", "position_title"), ("faculty", "faculty_printed"), ("faculty", "faculty_text"),
                    ("department", "dept_text"), ("organisation", "org_text"), ("city", "city"),
                    ("country", "country_code")) if af.get(c)]
                seen_p, parts2 = set(), []
                for p_ in parts:
                    if p_["value"] not in seen_p and not (p_["part"] == "department" and p_["value"] == af.get("faculty_text")):
                        seen_p.add(p_["value"])
                        parts2.append(p_)
                field("affiliation", "Affiliation", af["printed"], bx, lang=P._script(af["printed"]), ents=insts,
                      parts=parts2)
    # abstracts (one card per language), keywords
    for lang in ("ar", "lat"):
        bs = [b for b in by_role.get("abstract", []) if P._script(b["text"]) == lang]
        if bs:
            field("abstract", "Abstract", " ".join(full.get(b["id"], {}).get("text") or b["text"] for b in bs),
                  [x for b in bs for x in ink.block(b["id"])], lang="ar" if lang == "ar" else "en", paragraphs=len(bs))
    for b in by_role.get("keywords", []):
        field("keywords", "Keywords", full.get(b["id"], {}).get("text") or b["text"], ink.block(b["id"]),
              lang=P._script(b["text"]))
    # headings, as a tree (level from the sections)
    level = {s["heading_block_id"]: s["level"] for s in art.get("sections") or []}
    for b in by_role.get("heading", []):
        field("heading", "Heading", full.get(b["id"], {}).get("text") or b["text"], ink.block(b["id"]),
              lang=P._script(b["text"]), level=level.get(b["id"]) or 2)
    # footnotes and the calls that open them
    for n in art.get("notes") or []:
        if n.get("page") != page:
            continue
        label = (n.get("label") or "").translate(DIGITS).strip("()[]* ")
        call = next((c for c in calls_g if c["marker"].translate(DIGITS).strip("()[]* ") == label and c.get("box")), None)
        field("footnote", f"Footnote {n.get('label') or ''}".strip(), n.get("text"),
              ink.block(n.get("first_block_id")) or ink.anchor(n.get("anchor")), lang=P._script(n.get("text")),
              call=call["box"] if call else None, note_kind=n.get("kind"))
    # tables, as cells
    for fg in art.get("figures") or []:
        if fg.get("page") != page or fg.get("kind") != "table":
            continue
        cells = [dict(r=c["row"], c=c["col"], rs=c.get("rowspan") or 1, cs=c.get("colspan") or 1,
                      th=bool(c.get("is_header")), t=c.get("text")) for c in fg.get("cells") or []]
        field("table", fg.get("label") or "Table", f"{len(cells)} cells", [dict(x=fg["x"], y=fg["y"], w=fg["w"],
              h=fg["h"])] if fg.get("x") is not None else [], cells=cells, caption=fg.get("caption"))
    # references printed on this page, split into their parts, each on its cited-work card
    parsed = {r[0]: r[1] for r in con.execute(
        "SELECT mention_id, parsed FROM citation_mentions WHERE version_id = ? AND page = ?",
        ((art.get("version") or {}).get("version_id"), page))}
    for c in art.get("citations") or []:
        if c.get("page") != page or c.get("kind") != "full":
            continue
        try:
            pz = json.loads(parsed.get(c["mention_id"]) or "null") or {}
        except ValueError:
            pz = {}
        authors = [" ".join(x for x in reversed(a) if x) if isinstance(a, list) else str(a) for a in pz.get("authors") or []]
        parts = [dict(part="author", value="، ".join(authors) if P._script(" ".join(authors)) == "ar" else "; ".join(authors))
                 if authors else None,
                 dict(part="title", value=pz.get("title") or pz.get("source_title")),
                 dict(part="source", value=pz.get("source") if pz.get("title") else None),
                 dict(part="year", value=pz.get("year") or c.get("year")),
                 dict(part="publisher", value=pz.get("publisher")), dict(part="place", value=pz.get("place"))]
        card = c.get("card") or {}
        cw = entity(card.get("id"), "work", card.get("title"), n_citing=card.get("n_citing_pubs"),
                    n_mentions=card.get("n_mentions"), pub_type=card.get("pub_type"))
        field("reference", "Reference", c.get("printed"), ink.anchor(c.get("anchor")), lang=c.get("script"),
              ents=[cw], parts=[p_ for p_ in parts if p_ and p_["value"]], pub_type=pz.get("pub_type"),
              held=bool(c.get("link")))
    for fg in art.get("figures") or []:
        if fg.get("page") == page and fg.get("kind") != "table" and fg.get("kind") != "inline-equation":
            field("figure", {"equation": "Equation"}.get(fg["kind"], "Figure"), fg.get("caption") or fg.get("alt_en")
                  or fg.get("fig_type") or fg["kind"], [dict(x=fg["x"], y=fg["y"], w=fg["w"], h=fg["h"])]
                  if fg.get("x") is not None else [], lang=P._script(fg.get("caption") or ""))
    return F, list(E.values())


def _find_text(ink: Ink, text: str | None) -> list[dict]:
    """The line(s) whose Azure text holds the printed words (an affiliation stored without its own anchor)."""
    if not text:
        return []
    toks = [t for t in re.split(r"[\s\-–،,]+", text) if len(t) > 2][:4]
    if not toks:
        return []
    hits = [l for l in ink.line_box.values() if l.get("text") and sum(t in l["text"] for t in toks) >= max(1, len(toks) // 2)]
    return [dict(x=l["x"], y=l["y"], w=l["w"], h=l["h"]) for l in hits[:3]]


def _article_entities(con, art: dict) -> list[dict]:
    out = []
    j = art.get("journal") or {}
    if j.get("id"):
        out.append(dict(id=j["id"], kind="journal", name=j.get("title"), country=j.get("country_code")))
    if art.get("pub_id"):
        out.append(dict(id=art["pub_id"], kind="publication", name=(art.get("title") or {}).get("shown")))
    return out


def _entity_counts(con, ents: list[dict]) -> None:
    """How many articles each entity already connects in the index (the bridge it is)."""
    for e in ents:
        if e["kind"] == "person":
            e["n_articles"] = con.execute("SELECT count(DISTINCT pub_id) FROM authorships WHERE person_id = ?",
                                          (e["id"],)).fetchone()[0]
        elif e["kind"] == "institution":
            e["n_articles"] = con.execute(
                "SELECT count(DISTINCT v.stem) FROM affiliation_links l JOIN affiliation_mentions a ON a.aff_pk = "
                "l.aff_pk JOIN byline_mentions b ON b.mention_pk = a.mention_pk JOIN versions v ON v.version_id = "
                "b.version_id AND v.is_current = 1 WHERE l.inst_id = ?", (e["id"],)).fetchone()[0]
        elif e["kind"] == "journal":
            e["n_articles"] = con.execute("SELECT count(*) FROM publications p JOIN documents d ON d.pub_id = p.pub_id "
                                          "WHERE p.journal_id = ?", (e["id"],)).fetchone()[0]


def _platform_counts(fields: list[dict], ents: list[dict]) -> dict:
    k = Counter(f["kind"] for f in fields)
    e = Counter(x["kind"] for x in ents)
    return dict(fields=len(fields), with_ink=sum(1 for f in fields if f["boxes"]), authors=k["author"],
                affiliations=k["affiliation"], headings=k["heading"], footnotes=k["footnote"], tables=k["table"],
                references=k["reference"], persons=e["person"], institutions=e["institution"], works=e["work"],
                journals=e["journal"])


def _index_record(con, art: dict) -> dict:
    """The article as the index shows it: who, where, what it cites and who cites it."""
    pub, iss, j = art.get("publication") or {}, art.get("issue") or {}, art.get("journal") or {}
    meta = art.get("metadata") or {}

    def chosen(f):
        for r in meta.get(f) or []:
            if r.get("is_chosen"):
                return r.get("value")
        return None
    refs = [c for c in art.get("citations") or [] if c.get("kind") == "full"]
    top = sorted((c["card"] for c in refs if c.get("card")), key=lambda w: -(w.get("n_citing_pubs") or 0))
    seen, top_works = set(), []
    for w in top:
        if w["id"] not in seen:
            seen.add(w["id"])
            top_works.append(dict(id=w["id"], title=w.get("title"), n_citing=w.get("n_citing_pubs"),
                                  pub_type=w.get("pub_type")))
    authors = [dict(id=a.get("person_id"), name=a.get("preferred_name_ar") or a.get("name"),
                    latin=a.get("preferred_name_lat"),
                    institutions=sorted({(i["inst_id"], i["name"]) for b in a.get("bylines") or []
                                         for f in b.get("affiliations") or [] for i in f.get("institutions") or []}))
               for a in art.get("authors") or []]
    for a in authors:
        a["institutions"] = [dict(id=i, name=n) for i, n in a["institutions"]]
    return dict(pub_id=art.get("pub_id"), title=(art.get("title") or {}).get("shown"),
                translated=(art.get("title") or {}).get("translated"),
                journal=dict(id=j.get("id"), title=j.get("title"), country=j.get("country_code")),
                issue=iss.get("issue_printed"), year=pub.get("year_shown"),
                fpage=chosen("fpage"), lpage=chosen("lpage"), doc_type=(art.get("doc_type") or {}).get("shown"),
                authors=authors, references=len(art.get("citations") or []), full_references=len(refs),
                on_cards=sum(1 for c in art.get("citations") or [] if c.get("card")),
                held=sum(1 for c in art.get("citations") or [] if c.get("link")),
                times_cited=len(art.get("cited_by") or []),
                cited_by=[dict(stem=c.get("stem"), title=c.get("title")) for c in (art.get("cited_by") or [])[:5]],
                top_works=top_works[:6], notes=len(art.get("notes") or []), figures=len(art.get("figures") or []),
                sections=len(art.get("sections") or []), blocks=len(art.get("blocks") or []))


@router.get(A.P + "/pipeline/{stem}")
def pipeline_page(stem: str, page: int = Query(default=1, ge=1, le=2000), actor: dict = Depends(A.me)):
    if not P.STEM.fullmatch(stem):
        raise HTTPException(404, "no such article in the reading")
    with A.pgc() as pg:
        path, st = A._state(pg)
    try:
        out = page_story(path, stem, page)
    except CropError as e:
        raise HTTPException(e.status, str(e))
    return A.jsonable(dict(st, **out))
