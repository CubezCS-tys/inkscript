"""Experiment 41: downloadable formats of Argon's 55 articles (no model calls; local work only).

Turns each article's Argon structure (reader.capture: structure.assemble on out/argon/raw/, so the text, fixes, flags,
blocks, footnote links, tables, equations, verse halves and figures are exactly the experiment's) and Azure's lines
into the master files `inkscript edition` reads (JATS 1.4 + ALTO 4.4, the shape of experiment 29's masters and
src/inkscript/edition/model.py), then gathers every format under out/views/formats/<stem>/ for the owner's views page.

    masters.py prep   [--stems ...]   out/native_in/<stem>/<stem>.json + .pdf: the input of `inkscript native`. A window
                                      of a long article is cut to its pages (renumbered 1..k); Argon's fixes of Azure
                                      misreadings are written into Azure's words where they map word for word
    masters.py build  [--stems ...]   out/masters/<stem>.jats.xml, .alto.xml, .pdf (link to the scan PDF), crops/
    masters.py link   [--stems ...]   formats/<stem>/<stem>.scan.pdf (the ink PDF) and <stem>.jats.xml next to the
                                      edition's files; formats/formats.json (files, sizes, checks)
    masters.py check                  out/formats_check.json: edition's checks summed, our own word counts
                                      (Argon's block text vs each format), JATS well-formed + DTD, ALTO XSD

The commands in between (README "Formats"):
    inkscript native --azure-dir out/native_in --out out/native/<stem> --only <stem> --verify     (one per article)
    inkscript edition out/masters --out out/views/formats --only html,layout,onecol,md,jsonl --workers 2

Mapping (Argon block -> JATS / ALTO):
  title (article's first page)  article-title (id = its block); other title blocks there point at it
  byline (first page)           contrib (id = the block) when the block is exactly one of Argon's author names, else a
                                printed front-matter block (custom-meta front-matter-block, id = the block)
  heading / later title         sec/title, nested by Argon's level
  paragraph, abstract, keywords, other, caption (alone), byline (later)
                                p (content-type = the type when not a paragraph): abstracts stay where printed
  quote                         disp-quote/p
  list_item                     list/list-item/p
  reference                     back/ref-list/ref/mixed-citation (a heading just before the run is its title)
  footnote                      back/fn-group/fn (label = marker, id fn-p<page>-<k>); calls are xref ref-type="fn"
  verse                         verse-group/verse-line, one verse-line per half (hemistich)
  table                         table-wrap (caption = an adjoining caption block) / XHTML table; ALTO ComposedBlock
                                with one TextBlock per cell
  equation with LaTeX           disp-formula (MathML from latex2mathml + tex-math + scan crop); ALTO Illustration;
                                Azure's words of it kept in a TextBlock "formulaInk" (the typeset formula shows them)
  inline maths                  inline-formula; its ALTO words tagged kind.formula
  figure                        fig (caption = an adjoining caption block, graphic = crop of the 300 dpi page); ALTO
                                Illustration; the words printed inside the picture in a TextBlock "pictureText"
  header / footer               ALTO only (pageHeader / pageFooter / pageNumber)
  noise, dropped lines          ALTO only, TextBlock "noise" (counted; the layout PDF shows them grey)
  missed (data-added)           p content-type="added" (no ink box: Azure did not read it)
  sic (D30)                     named-content content-type="sic" xlink:title="<proposed correction>" around the printed
                                text, which stays; listed in back/notes notes-type="suspected-misprints"
  fixes of Azure misreadings    applied (the text is the print); ALTO String ALTERNATIVE keeps Azure's reading when the
                                fix maps word for word; all listed in back/notes notes-type="reader-fixes"
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reader as R  # noqa: E402
import structure as ST  # noqa: E402
from structure import OUT, is_rtl, sample  # noqa: E402

NIN = OUT / "native_in"
NOUT = OUT / "native"
MAST = OUT / "masters"
FMT = OUT / "views" / "formats"


def jdump(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def nows(s):
    return re.sub(r"\s+", "", s or "")


# ------------------------------------------------------------------------------------------------ Azure words

def azure_raw(a) -> dict:
    j = json.loads(Path(a["azure"]).read_text(encoding="utf-8"))
    return j.get("analyzeResult", j)


def line_words(pg: dict, ln: dict) -> list[dict]:
    """Azure's words of one line (by span offsets), in logical order."""
    rng = [(s["offset"], s["offset"] + s["length"]) for s in ln.get("spans") or []]
    ws = [w for w in pg.get("words", []) if any(a <= (w.get("span") or {}).get("offset", -1) < b for a, b in rng)]
    return sorted(ws, key=lambda w: w["span"]["offset"])


def nonempty_lines(pg: dict) -> list[dict]:
    """Azure's lines as structure.page_lines numbers them (empty lines skipped)."""
    return [ln for ln in pg.get("lines", []) if (ln.get("content") or "").strip()]


def map_fix(words: list[dict], frm: str, to: str) -> bool:
    """Write one fix into Azure's words when it maps word for word: the words covering `frm` in the line's text
    become as many words after the fix. Returns whether it was written."""
    texts = [w["content"] for w in words]
    joined = " ".join(texts)
    i = joined.find(frm)
    if i < 0 or not frm:
        return False
    starts, pos = [], 0
    for t in texts:
        starts.append(pos)
        pos += len(t) + 1
    j = i + len(frm)
    cover = [k for k, s in enumerate(starts) if s < j and s + len(texts[k]) > i]
    if not cover:
        return False
    s0, s1 = starts[cover[0]], starts[cover[-1]] + len(texts[cover[-1]])
    seg = joined[s0:s1].replace(frm, to, 1)
    new = seg.split()
    if len(new) != len(cover):
        return False
    for k, t in zip(cover, new):
        words[k]["content"] = t
    return True


# ------------------------------------------------------------------------------------------------ prep: native input

def prep(a: dict, cap: dict) -> dict:
    """out/native_in/<stem>/: Azure JSON + PDF of the article's pages (a window cut to its pages, renumbered 1..k),
    with Argon's fixes written into Azure's words where they map word for word."""
    import pymupdf
    stem = a["stem"]
    d = NIN / stem
    d.mkdir(parents=True, exist_ok=True)
    ar = copy.deepcopy(azure_raw(a))
    pages = list(range(a["first"], a["last"] + 1))
    S = cap["S"]
    done = skipped = 0
    for f in S.applied:
        L = S.lines[f["at"]]
        base = L.get("split_of") or L["id"]
        p, k = (int(x) for x in base.split(":"))
        pg = ar["pages"][p - 1]
        ln = nonempty_lines(pg)[k - 1]
        ws = line_words(pg, ln)
        if map_fix(ws, f.get("from") or "", f.get("to") or ""):
            done += 1
            ln["content"] = " ".join(w["content"] for w in ws)
        else:
            skipped += 1
    keep = [copy.deepcopy(ar["pages"][p - 1]) for p in pages]
    for i, pg in enumerate(keep, 1):
        pg["pageNumber"] = i
    paras = []
    for para in ar.get("paragraphs") or []:
        br = (para.get("boundingRegions") or [{}])[0]
        if br.get("pageNumber") in pages:
            para = copy.deepcopy(para)
            for b in para["boundingRegions"]:
                b["pageNumber"] = b["pageNumber"] - a["first"] + 1
            paras.append(para)
    out = dict(ar, pages=keep, paragraphs=paras)
    out.pop("styles", None)
    (d / f"{stem}.json").write_text(json.dumps(dict(analyzeResult=out), ensure_ascii=False), encoding="utf-8")
    pdf = d / f"{stem}.pdf"
    if pdf.exists() or pdf.is_symlink():
        pdf.unlink()
    with pymupdf.open(a["pdf"]) as src:
        if len(pages) == src.page_count:
            os.symlink(a["pdf"], pdf)
        else:
            src.select([p - 1 for p in pages])
            src.save(str(pdf), garbage=3, deflate=True)
    return dict(stem=stem, pages=len(pages), fixes_written=done, fixes_not_word_for_word=skipped)


# ------------------------------------------------------------------------------------------------ build: masters

from lxml import etree  # noqa: E402

XL = "http://www.w3.org/1999/xlink"
MML = "http://www.w3.org/1998/Math/MathML"
ALTO = "http://www.loc.gov/standards/alto/ns-v4#"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
JOIN = {"paragraph", "quote", "list_item", "reference", "abstract", "keywords", "other", "caption", "footnote"}
BODY_P = {"paragraph": None, "abstract": "abstract", "keywords": "keywords", "other": "other", "caption": "caption",
          "byline": "byline"}
SKIP_FOR_JOIN = {"figure", "table", "equation", "caption", "header", "footer", "footnote", "other"}
NOT_TEXT = re.compile(r"^[\s\W\d_]*$")          # a line with no letters
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def lang_of(text: str, given=None) -> str:
    if given in ("ar", "en", "fr"):
        return given
    if is_rtl(text):
        return "ar"
    return "fr" if re.search(r"[éèàçêùâôîûœ]", text) else "en"


def add_text(el, s: str):
    if not s:
        return
    if len(el):
        el[-1].tail = (el[-1].tail or "") + s
    else:
        el.text = (el.text or "") + s


def sub(parent, tag, attrib=None, text=None):
    el = etree.SubElement(parent, tag, {k: str(v) for k, v in (attrib or {}).items() if v is not None})
    if text is not None:
        el.text = text
    return el


def mathml(parent, latex: str, display: str):
    """latex2mathml's MathML rebuilt under `parent` in the mml: prefix (the JATS DTD is not namespace-aware)."""
    from latex2mathml.converter import convert
    try:
        src = etree.fromstring(convert(latex).encode("utf-8"))
    except Exception:
        return None

    def copy_(e, into):
        n = etree.SubElement(into, f"{{{MML}}}{etree.QName(e).localname}")
        for k, v in e.attrib.items():
            if not k.startswith("{") and k != "xmlns":
                n.set(k, v)
        n.text = e.text
        for c in e:
            if isinstance(c.tag, str):
                cc = copy_(c, n)
                cc.tail = c.tail
        return n
    m = copy_(src, parent)
    m.set("display", display)
    return m


class Master:
    """One article: Argon's blocks -> JATS tree + ALTO page lists."""

    def __init__(self, a: dict, cap: dict):
        self.a, self.cap, self.S = a, cap, cap["S"]
        self.stem = a["stem"]
        self.meta = cap["meta"] or {}
        self.recs = cap["blocks"]
        self.pages = cap["pages"]
        self.az = azure_raw(a)
        self.whole_start = a["first"] == 1
        self.lang = lang_of("", self.meta.get("language")) if self.meta.get("language") in ("ar", "en", "fr") \
            else "ar"
        self.alto = {self.lp(p): [] for p in self.pages}       # local page -> [ALTO block dicts], reading order
        self.nb = Counter()                                      # per local page: TextBlock counter
        self.nk = Counter()                                      # per (page, kind): table / formula / figure
        self.wn = Counter()                                      # per page: word counter
        self.used = set()
        self.calls = {}                                          # line id -> [call]
        for rec in self.recs:
            for c in rec.get("calls") or []:
                self.calls.setdefault(str(c.get("line")), []).append(c)
        for lid, cs in R.VERSE_CALLS.items():            # a verse's calls (structure.assemble keeps them per block)
            for c in cs:
                key = (str(c.get("line")), c.get("marker"), ST.fn_norm(c.get("fn")))
                if not any((str(x.get("line")), x.get("marker"), ST.fn_norm(x.get("fn"))) == key
                           for x in self.calls.get(lid, [])):
                    self.calls.setdefault(lid, []).append(c)
        self.fn_map = {}                                         # Argon footnote id -> JATS fn id
        k = Counter()
        for rec in self.recs:
            if rec["type"] == "footnote" and not rec["continued"] and rec.get("fn_id") not in self.fn_map:
                lp = self.lp(rec["page"])
                k[lp] += 1
                self.fn_map[rec["fn_id"]] = f"fn-p{lp}-{k[lp]}"
        self.stats = Counter()
        self.crops = MAST / f"{self.stem}.crops"

    # ---------------------------------------------------------------- ids and pages
    def lp(self, p: int) -> int:
        return p - self.a["first"] + 1

    def bid(self, p: int) -> str:
        lp = self.lp(p)
        self.nb[lp] += 1
        return f"p{lp}b{self.nb[lp]}"

    def kid(self, p: int, kind: str) -> str:
        lp = self.lp(p)
        self.nk[(lp, kind)] += 1
        return f"p{lp}{kind}{self.nk[(lp, kind)]}"

    # ---------------------------------------------------------------- words with boxes
    def az_words(self, L) -> list[dict]:
        base = L.get("split_of") or L["id"]
        p, k = (int(x) for x in base.split(":"))
        pg = self.az["pages"][p - 1]
        s = 300.0 if pg.get("unit", "inch") == "inch" else 1.0
        ws = []
        for w in line_words(pg, nonempty_lines(pg)[k - 1]):
            xs, ys = w["polygon"][0::2], w["polygon"][1::2]
            ws.append(dict(text=w["content"], conf=w.get("confidence"),
                           box=[min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s]))
        if L.get("split_of"):
            x0, x1 = L["px"][0], L["px"][2]
            ws = [w for w in ws if x0 - 2 <= (w["box"][0] + w["box"][2]) / 2 <= x1 + 2]
        return ws

    def words_of(self, lid: str) -> list[dict]:
        """The line's words (Argon's text, after fixes) with boxes: Azure's own word boxes when the count matches,
        else the line's box shared by letters (right to left for Arabic)."""
        L = self.S.lines[lid]
        toks = L["text"].split()
        az = self.az_words(L)
        math_rng = []
        for m in self.S.math.get(lid, []):
            i = L["text"].find(m["from"])
            if i >= 0:
                math_rng.append((i, i + len(m["from"])))
        starts, pos = [], 0
        for t in toks:
            i = L["text"].find(t, pos)
            starts.append(i)
            pos = i + len(t)
        out = []
        if len(az) == len(toks):
            for t, w, s0 in zip(toks, az, starts):
                out.append(dict(text=t, box=w["box"], conf=w["conf"], alt=w["text"] if w["text"] != t else None))
            self.stats["words_azure_boxes"] += len(toks)
        else:
            x0, y0, x1, y1 = L["px"]
            tot = sum(len(t) for t in toks) + max(0, len(toks) - 1)
            acc, rtl = 0, is_rtl(L["text"])
            for t in toks:
                f0, f1 = acc / tot, (acc + len(t)) / tot
                acc += len(t) + 1
                w = x1 - x0
                bx = [x1 - f1 * w, y0, x1 - f0 * w, y1] if rtl else [x0 + f0 * w, y0, x0 + f1 * w, y1]
                out.append(dict(text=t, box=bx, conf=None, alt=None))
            self.stats["words_shared_boxes"] += len(toks)
        for w, s0 in zip(out, starts):
            w["math"] = any(s0 < e and s0 + len(w["text"]) > b for b, e in math_rng)
            if w["alt"]:
                self.stats["words_with_azure_alternative"] += 1
        return out

    # ---------------------------------------------------------------- inline content
    def runs(self, lid: str) -> list[tuple]:
        """A line's text as runs: plain text, maths, misprint flags (D30) and footnote calls."""
        L = self.S.lines[lid]
        t = L["text"]
        marks = []

        def place(s, kind, data):
            if not s:
                return False
            start = 0
            while True:
                i = t.find(s, start)
                if i < 0:
                    return False
                if not any(i < e and i + len(s) > b for b, e, _, _ in marks):
                    marks.append((i, i + len(s), kind, data))
                    return True
                start = i + 1
        for m in self.S.math.get(lid, []):
            self.stats["inline_math"] += place(m["from"], "math", m)
        for s in self.S.sic.get(lid, []):
            self.stats["sic_placed"] += place(s["text"], "sic", s)
        for c in self.calls.get(lid, []) + self.calls.get(L.get("split_of") or "\0", []):
            fid = self.fn_map.get(ST.fn_norm(c.get("fn")))
            if fid and c.get("marker"):
                ok = place(c["marker"], "xref", fid)
                self.stats["calls_linked"] += ok
                self.stats["calls_not_found_in_line"] += not ok
            else:
                self.stats["calls_without_note"] += 1
        out, pos = [], 0
        for b, e, kind, data in sorted(marks):
            if b > pos:
                out.append(("t", t[pos:b]))
            out.append((kind, t[b:e], data))
            pos = e
        if pos < len(t):
            out.append(("t", t[pos:]))
        return out

    def put_runs(self, el, runs):
        for r in runs:
            if r[0] == "t":
                add_text(el, r[1])
            elif r[0] == "xref":
                sub(el, "xref", {"ref-type": "fn", "rid": r[2]}, r[1])
            elif r[0] == "sic":
                n = sub(el, "named-content", {"content-type": "sic", "specific-use": "argon",
                                              f"{{{XL}}}title": r[2]["corr"]}, r[1])
                n.set(f"{{{XL}}}type", "simple")
            elif r[0] == "math":
                f = sub(el, "inline-formula")
                alt = sub(f, "alternatives")
                if mathml(alt, r[2]["latex"], "inline") is None:
                    self.stats["mathml_failed"] += 1
                sub(alt, "tex-math", text=r[2]["latex"])
                f.tail = None
                # the printed symbols stay in the ALTO (kind.formula); the JATS holds the formula

    def fill(self, el, ids, sep_first=False):
        for k, lid in enumerate(ids):
            if k or sep_first:
                add_text(el, " ")
            self.put_runs(el, self.runs(lid))

    def text(self, ids) -> str:
        return " ".join(self.S.lines[i]["text"] for i in ids)

    # ---------------------------------------------------------------- ALTO blocks
    def tb(self, p, bid, role, ids, target=None, lang=None):
        """An ALTO TextBlock of these lines on page p (local numbering)."""
        self.used.update(ids)
        b = dict(kind="text", id=bid, role=role, ids=list(ids), target=target, lang=lang)
        self.alto[self.lp(p)].append(b)
        return b

    def box_px(self, ids):
        return ST.union([self.S.lines[i]["px"] for i in ids])

    # ---------------------------------------------------------------- the article
    def build(self):
        A = etree.Element("article", nsmap={"xlink": XL, "mml": MML})
        A.set("article-type", "research-article")
        A.set("dtd-version", "1.4")
        A.set(XML_LANG, self.lang)
        self.A = A
        front = sub(A, "front")
        body = sub(A, "body")
        back = etree.Element("back")
        self.body, self.back = body, back
        self.fn_group = None
        self.notes = {}                                          # JATS fn id -> fn element
        front_blocks, contribs_by_block = [], {}
        title_el_id, title_text = None, ""

        # captions: each attaches to the table or figure next to it on its page
        cap_of, caption_taken = {}, set()
        flow = [r for r in self.recs if r["type"] not in ("header", "footer", "footnote")]
        for i, r in enumerate(flow):
            if r["type"] != "caption":
                continue
            nxt = flow[i + 1] if i + 1 < len(flow) else None
            prv = flow[i - 1] if i else None
            for c in (nxt, prv):
                if c is not None and c["type"] in ("table", "figure") and c["page"] == r["page"] and \
                        c["n"] not in cap_of and (c["type"] != "figure" or c.get("fig_box")):
                    cap_of[c["n"]] = r
                    caption_taken.add(r["n"])
                    break
        # a heading right before a run of references titles their list
        ref_title = set()
        for i, r in enumerate(flow):
            if r["type"] == "heading" and i + 1 < len(flow) and flow[i + 1]["type"] == "reference":
                ref_title.add(r["n"])

        stack = [(0, body)]
        state = dict(list=None, list_parent=None, refs=None, last=None)   # last: (type, element, id)
        pending_ref_title = None

        def container():
            return stack[-1][1]

        def close_list():
            state["list"] = None

        def body_p(rec, ctype=None, parent=None):
            bid = self.bid(rec["page"])
            t = self.text(rec["ids"])
            lg = lang_of(t, rec.get("lang"))
            par = parent if parent is not None else container()
            p = sub(par, "p", {"id": bid, "content-type": ctype})
            if lg != self.lang or lg != "ar":
                p.set(XML_LANG, lg)
            self.fill(p, rec["ids"])
            self.tb(rec["page"], bid, ROLE.get(rec["type"], "body"), rec["ids"], bid, lg)
            return p, bid

        def added(rec, parent):
            for m in rec.get("missed") or []:
                t = (m.get("text") or "").strip()
                if t and m.get("type") in ("header", "footer"):     # a running head Azure missed: no ink box,
                    self.stats["added_furniture_left_out"] += 1     # not part of the article
                    continue
                if t and m.get("type") == "equation":               # a formula Azure missed, as Argon's LaTeX
                    host = sub(parent, "p") if parent.tag in ("list-item", "fn", "disp-quote") else parent
                    f = sub(host, "disp-formula", {"specific-use": "added-by-argon"})
                    alt = sub(f, "alternatives")
                    if mathml(alt, t, "block") is None:
                        self.stats["mathml_failed"] += 1
                    sub(alt, "tex-math", text=t)
                    self.stats["added_equations"] += 1
                    continue
                if t:
                    p = sub(parent, "p", {"content-type": "added", "specific-use": "argon"}, t)
                    if not is_rtl(t):
                        p.set(XML_LANG, lang_of(t))
                    self.stats["added_paragraphs"] += 1
                    self.stats["added_words"] += len(t.split())

        def caption_into(parent_cap, rec):
            bid = self.bid(rec["page"])
            p = sub(parent_cap, "p", {"id": bid})
            self.fill(p, rec["ids"])
            self.tb(rec["page"], bid, "caption", rec["ids"], bid, lang_of(self.text(rec["ids"]), rec.get("lang")))
            self.stats["captions_attached"] += 1

        for rec in self.recs:
            T, p, ids = rec["type"], rec["page"], rec["ids"]
            lp = self.lp(p)
            if T in ("header", "footer"):
                self.stats["added_furniture_left_out"] += len(rec.get("missed") or [])
                t = self.text(ids)
                role = "pageHeader" if T == "header" else (
                    "pageNumber" if re.fullmatch(r"[\s\-–—()\[\]0-9٠-٩۰-۹]+", t) else "pageFooter")
                self.tb(p, self.bid(p), role, ids)
                continue
            if T == "caption" and rec["n"] in caption_taken:
                continue
            # ---- continuation of the previous element of the same type
            if rec["continued"] and T in JOIN:
                if T == "footnote" and state.get("last_fn") is not None:
                    el, tid = state["last_fn"]
                    self.fill(el, ids, sep_first=True)
                    self.tb(p, self.bid(p), "footnote", ids, tid)
                    added(rec, el.getparent())
                    self.stats["joined_across_pages"] += 1
                    continue
                if state["last"] is not None and state["last"][0] == T:
                    el, tid = state["last"][1], state["last"][2]
                    self.fill(el, ids, sep_first=True)
                    self.tb(p, self.bid(p), ROLE.get(T, "body"), ids, tid)
                    added(rec, container())
                    self.stats["joined_across_pages"] += 1
                    continue
            # ---- front matter (the article's first page)
            if T == "title" and self.whole_start and p == 1 and title_el_id is None:
                bid = self.bid(p)
                title_el_id, title_text = bid, self.text(ids)
                self.title_ids = ids
                self.tb(p, bid, "title", ids, bid)
                continue
            if T in ("title", "byline") and self.whole_start and p == 1 and title_el_id is not None or \
                    T == "byline" and self.whole_start and p == 1:
                bid = self.bid(p)
                t = self.text(ids)
                who = next((au for au in self.authors() if nows(au["name"]) == nows(t)), None)
                if who is not None and id(who) not in contribs_by_block.values():
                    contribs_by_block[bid] = id(who)
                    who["block"] = bid
                    self.tb(p, bid, "author", ids, bid)
                else:
                    front_blocks.append((bid, t))
                    self.tb(p, bid, "author" if T == "byline" else "title", ids, bid)
                continue
            # ---- footnotes
            if T == "footnote":
                if self.fn_group is None:
                    self.fn_group = sub(back, "fn-group")
                fid = self.fn_map.get(rec.get("fn_id")) or f"fn-p{lp}-x{rec['n']}"
                fn = sub(self.fn_group, "fn", {"id": fid})
                if rec.get("marker"):
                    sub(fn, "label", text=str(rec["marker"]))
                pp, bid = body_p(rec, parent=fn)
                pp.attrib.pop("content-type", None)
                state["last_fn"] = (pp, bid)
                added(rec, fn)
                self.stats["footnotes"] += 1
                continue
            # ---- references
            if T == "reference":
                close_list()
                if state["refs"] is None:
                    state["refs"] = sub(back, "ref-list")
                    if pending_ref_title is not None:
                        prec = pending_ref_title
                        bid = self.bid(prec["page"])
                        tt = sub(state["refs"], "title", {"id": bid})
                        self.fill(tt, prec["ids"])
                        self.tb(prec["page"], bid, "sectionHeading", prec["ids"], bid)
                        pending_ref_title = None
                n = len(state["refs"].findall("ref")) + 1
                ref = sub(state["refs"], "ref", {"id": f"r{len(back.findall('.//ref')) + 1}"})
                bid = self.bid(p)
                mc = sub(ref, "mixed-citation", {"id": bid})
                lg = lang_of(self.text(ids), rec.get("lang"))
                if lg != "ar":
                    mc.set(XML_LANG, lg)
                self.fill(mc, ids)
                self.tb(p, bid, "body", ids, bid, lg)
                state["last"] = ("reference", mc, bid)
                added(rec, container())
                del n
                continue
            if T != "reference" and T not in ("figure", "table", "equation", "caption"):
                state["refs"] = None if T in ("heading", "title", "paragraph") else state["refs"]
            if pending_ref_title is not None:           # the heading was not followed by references after all
                self.heading(pending_ref_title, stack, 1)
                pending_ref_title = None
            # ---- headings
            if T in ("heading", "title"):
                close_list()
                if rec["n"] in ref_title:
                    pending_ref_title = rec
                    continue
                lvl = rec.get("level")
                lvl = int(lvl) if str(lvl or "").isdigit() else 1
                if T == "title":
                    lvl = 1
                el, bid = self.heading(rec, stack, max(1, min(6, lvl)))
                state["last"] = ("heading", el, bid)
                continue
            # ---- lists
            if T == "list_item":
                if state["list"] is None or state["list_parent"] is not container():
                    lt = "bullet" if rec.get("list") == "ul" else "order"
                    state["list"] = sub(container(), "list", {"list-type": lt})
                    state["list_parent"] = container()
                li = sub(state["list"], "list-item")
                pp, bid = body_p(rec, parent=li)
                state["last"] = ("list_item", pp, bid)
                added(rec, li)
                continue
            close_list()
            if T == "quote":
                dq = sub(container(), "disp-quote")
                pp, bid = body_p(rec, parent=dq)
                state["last"] = ("quote", pp, bid)
                added(rec, container())
                continue
            if T == "verse":
                bid = self.bid(p)
                vg = sub(container(), "verse-group", {"id": bid})
                hs = [h for h in rec.get("hemistichs") or [] if h]
                lg = lang_of(self.text(ids), rec.get("lang"))
                for k, h in enumerate(hs, 1):
                    vl = sub(vg, "verse-line", {"id": f"{bid}-{k}"})
                    if lg != "ar":
                        vl.set(XML_LANG, lg)
                    self.fill(vl, h)
                self.tb(p, bid, "body", ids, bid, lg)
                self.stats["verses"] += 1
                self.stats["hemistichs"] += len(hs)
                state["last"] = ("verse", vg, bid)
                added(rec, container())
                continue
            if T == "equation":
                if rec.get("latex"):
                    self.equation(rec, container())
                    added(rec, container())
                    continue
                pp, bid = body_p(rec, "equation")
                state["last"] = ("equation", pp, bid)
                added(rec, container())
                continue
            if T == "table":
                self.table(rec, container(), cap_of.get(rec["n"]), caption_into)
                added(rec, container())
                continue
            if T == "figure":
                if rec.get("fig_box"):
                    self.figure(rec, container(), cap_of.get(rec["n"]), caption_into)
                    added(rec, container())
                    continue
                if ids:
                    pp, bid = body_p(rec, "figure-text")
                    added(rec, container())
                continue
            # paragraph, abstract, keywords, other, caption (alone), byline (later pages), title elsewhere
            pp, bid = body_p(rec, BODY_P.get(T, T if T != "paragraph" else None))
            state["last"] = (T, pp, bid)
            added(rec, container())
        if pending_ref_title is not None:
            self.heading(pending_ref_title, stack, 1)

        # ---- lines no block holds: Argon's noise and the lines it dropped (ALTO only, counted)
        noise = {str(x) for x in (self.cap["book"].get("noise") or [])}
        for lid, L in self.S.lines.items():
            if L.get("split") or lid in self.used:
                continue
            kind = "noise" if (lid in noise or (L.get("split_of") or "") in noise) else "dropped"
            self.tb(L["page"], self.bid(L["page"]), "noise", [lid])
            self.stats[f"{kind}_lines"] += 1
            if not NOT_TEXT.match(L["text"]):
                self.stats[f"{kind}_lines_with_words"] += 1
                self.stats[f"{kind}_words"] += len(L["text"].split())

        self.front(front, title_el_id, title_text, front_blocks)
        self.back_notes(back)
        if len(back):
            A.append(back)
        if not len(body):
            sub(body, "p")
        return A

    def authors(self):
        if not hasattr(self, "_authors"):
            self._authors = [dict(name=(au.get("name") or "").strip(), aff=(au.get("affiliation") or "").strip(),
                                  email=(au.get("email") or "").strip())
                             for au in (self.meta.get("authors") or []) if isinstance(au, dict) and au.get("name")]
        return self._authors

    def heading(self, rec, stack, lvl):
        while stack[-1][0] >= lvl and len(stack) > 1:
            stack.pop()
        sec = sub(stack[-1][1], "sec", {"id": f"s{rec['n']}"})
        stack.append((lvl, sec))
        bid = self.bid(rec["page"])
        t = sub(sec, "title", {"id": bid})
        lg = lang_of(self.text(rec["ids"]), rec.get("lang"))
        if lg != "ar":                          # <title> takes no xml:lang; its section does
            sec.set(XML_LANG, lg)
        self.fill(t, rec["ids"])
        self.tb(rec["page"], bid, "sectionHeading", rec["ids"], bid, lg)
        self.stats["headings"] += 1
        return t, bid

    def crop(self, p, box_px, name) -> str | None:
        """A crop of the 300 dpi page (out/pages/), box in pixels, padded a little."""
        import cv2
        img = cv2.imread(str(ST.page_image(self.a, p)), cv2.IMREAD_COLOR)
        if img is None:
            return None
        H, W = img.shape[:2]
        x0, y0, x1, y1 = box_px
        pad = 8
        x0, y0 = max(0, int(x0 - pad)), max(0, int(y0 - pad))
        x1, y1 = min(W, int(x1 + pad)), min(H, int(y1 + pad))
        c = img[y0:y1, x0:x1]
        if c.size == 0 or c.shape[0] < 6 or c.shape[1] < 6:
            return None
        if c.shape[1] > 1600:
            c = cv2.resize(c, (1600, int(c.shape[0] * 1600 / c.shape[1])), interpolation=cv2.INTER_AREA)
        self.crops.mkdir(parents=True, exist_ok=True)
        if R._colourless(c):
            c = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
        (self.crops / name).write_bytes(cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes())
        return f"{self.stem}.crops/{name}"

    def equation(self, rec, parent):
        p, ids = rec["page"], rec["ids"]
        eid = self.kid(p, "eq")
        f = sub(parent, "disp-formula", {"id": eid})
        alt = sub(f, "alternatives")
        if mathml(alt, rec["latex"], "block") is None:
            self.stats["mathml_failed"] += 1
        sub(alt, "tex-math", text=rec["latex"])
        box = self.box_px(ids) if ids else None
        if box:
            g = self.crop(p, box, f"{eid}.jpg")
            if g:
                sub(alt, "graphic", {f"{{{XL}}}href": g, "specific-use": "scan-crop"})
            self.alto[self.lp(p)].append(dict(kind="ill", id=eid, type="formula", box=box, target=eid))
            self.tb(p, self.bid(p), "formulaInk", ids)
            self.stats["formula_ink_words"] += sum(len(self.S.lines[i]["text"].split()) for i in ids)
        self.stats["equations_typeset"] += 1

    def figure(self, rec, parent, cap_rec, caption_into):
        p = rec["page"]
        W, H = self.S.dims[p]
        x0, y0, x1, y1 = rec["fig_box"]
        box = [min(x0, x1) * W / 1000, min(y0, y1) * H / 1000, max(x0, x1) * W / 1000, max(y0, y1) * H / 1000]
        fid = self.kid(p, "f")
        fig = sub(parent, "fig", {"id": fid})
        if cap_rec is not None:
            caption_into(sub(fig, "caption"), cap_rec)
        g = self.crop(p, box, f"{fid}.jpg")
        if g:
            sub(fig, "graphic", {f"{{{XL}}}href": g})
            self.stats["figures"] += 1
        else:
            self.stats["figures_without_crop"] += 1
        if rec.get("description"):
            fig.insert(0 if cap_rec is None else 1, etree.Element("alt-text"))
            fig.find("alt-text").text = rec["description"]
        # JATS order: caption, alt-text, graphic
        kids = {c.tag: c for c in fig}
        for tag in ("caption", "alt-text", "graphic"):
            if tag in kids:
                fig.remove(kids[tag])
                fig.append(kids[tag])
        self.alto[self.lp(p)].append(dict(kind="ill", id=fid, type="figure", box=box, target=fid))
        if rec["ids"]:
            self.tb(p, self.bid(p), "pictureText", rec["ids"])
            self.stats["picture_text_words"] += sum(len(self.S.lines[i]["text"].split()) for i in rec["ids"])

    def table(self, rec, parent, cap_rec, caption_into):
        p = rec["page"]
        tid = self.kid(p, "t")
        tw = sub(parent, "table-wrap", {"id": tid})
        if cap_rec is not None:
            caption_into(sub(tw, "caption"), cap_rec)
        tab = sub(tw, "table")
        rows = rec.get("rows") or []
        nhead = 0
        for r in rows:
            if r and all(c.get("th") for c in r):
                nhead += 1
            else:
                break
        if nhead == len(rows):
            nhead = 0
        thead = sub(tab, "thead") if nhead else None
        tbody = sub(tab, "tbody")
        cells_alto = []
        allt = self.text(rec["ids"])
        lg = lang_of(allt, rec.get("lang"))
        if lg != "ar":
            tw.set(XML_LANG, lg)
        for ri, r in enumerate(rows):
            tr = sub(thead if ri < nhead else tbody, "tr")
            for ci, c in enumerate(r):
                cid = f"{tid}c{ri:02d}{ci:02d}" if c["ids"] else None
                cell = sub(tr, "th" if c.get("th") else "td",
                           {"id": cid, "colspan": c.get("colspan"), "rowspan": c.get("rowspan")})
                if c["ids"]:
                    self.fill(cell, c["ids"])
                    self.used.update(c["ids"])
                    cells_alto.append(dict(kind="text", id=cid, role="body", ids=list(c["ids"]), target=cid, lang=lg))
        box = self.box_px(rec["ids"]) if rec["ids"] else None
        if box:
            self.alto[self.lp(p)].append(dict(kind="table", id=tid, box=box, target=tid, cells=cells_alto))
        self.stats["tables"] += 1
        self.stats["table_cells"] += len(cells_alto)

    # ---------------------------------------------------------------- front and back
    def front(self, front, title_id, title_text, front_blocks):
        m = self.meta
        cat = None
        if self.a.get("jats") and Path(self.a["jats"]).exists():
            cat = etree.parse(self.a["jats"], etree.XMLParser(load_dtd=False, no_network=True)).getroot().find("front")
        jm = cat.find("journal-meta") if cat is not None else None
        if jm is not None:
            front.append(copy.deepcopy(jm))
        else:
            jm = sub(front, "journal-meta")
            sub(jm, "journal-id", {"journal-id-type": "mandumah"}, self.stem.split("-")[0])
            jtg = sub(jm, "journal-title-group")
            sub(jtg, "journal-title", None, m.get("journal") or self.a.get("journal") or "")
        am = sub(front, "article-meta")
        cam = cat.find("article-meta") if cat is not None else None

        def take(tag):
            return [copy.deepcopy(e) for e in cam.findall(tag)] if cam is not None else []
        ids_ = take("article-id")
        if not ids_:
            sub(am, "article-id", {"pub-id-type": "other", "assigning-authority": "Mandumah"}, self.stem)
        for e in ids_:
            am.append(e)
        for e in take("article-categories"):
            for s in e.iter("subject"):
                s.attrib.pop("id", None)
            am.append(e)
        tg = sub(am, "title-group")
        title = title_text or (m.get("title") or "").strip()
        if not title and cam is not None:
            title = " ".join("".join(cam.find("title-group/article-title").itertext()).split())
        at = sub(tg, "article-title", {"id": title_id})
        if title_id:
            self.fill(at, self.title_ids)
        else:
            at.text = title
        sub_t = (m.get("subtitle") or "").strip()
        printed = nows(" ".join(t for _, t in front_blocks) + title_text)
        if sub_t and nows(sub_t) not in printed:
            sub(tg, "subtitle", None, sub_t)
        if cam is not None:
            for tt in cam.findall("title-group/trans-title-group"):
                tg.append(copy.deepcopy(tt))
        aus = self.authors()
        if aus:
            cg = sub(am, "contrib-group")
            for k, au in enumerate(aus, 1):
                c = sub(cg, "contrib", {"contrib-type": "author", "id": au.get("block") or f"contrib{k}"})
                sub(c, "string-name", None, au["name"])
                if au["email"]:
                    sub(c, "email", None, au["email"])
                if au["aff"]:
                    sub(c, "aff", None, au["aff"])
        for tag in ("pub-date", "volume", "issue", "fpage", "lpage"):
            got = take(tag)
            for e in got:
                am.append(e)
            if got:
                continue
            if tag == "pub-date" and m.get("year"):
                y = str(m["year"]).translate(DIGITS)
                yy = re.search(r"\d{4}", y)
                if yy:
                    pd = sub(am, "pub-date", {"publication-format": "print", "date-type": "pub"})
                    sub(pd, "year", None, yy.group(0))
            elif tag in ("volume", "issue") and m.get(tag):
                sub(am, tag, None, str(m[tag]))
            elif tag in ("fpage", "lpage") and m.get("pages_printed"):
                pp = re.findall(r"\d+", str(m["pages_printed"]).translate(DIGITS))
                if pp:
                    sub(am, tag, None, pp[0] if tag == "fpage" else pp[-1])
        for e in take("kwd-group"):
            am.append(e)
        cnt = sub(am, "counts")
        sub(cnt, "page-count", {"count": len(self.pages)})
        cmg = sub(am, "custom-meta-group")

        def cm(name, value, id_=None):
            c = sub(cmg, "custom-meta", {"id": id_})
            sub(c, "meta-name", None, name)
            sub(c, "meta-value", None, str(value))
        cm("text-direction", "rtl (text stored in logical order; xml:lang carries the script)" if self.lang == "ar"
           else "ltr")
        cm("text-source", "Azure Document Intelligence prebuilt-read (API 2024-11-30); Gemini 4 Argon's fixes of "
                          "Azure misreadings applied (strict rule v5, experiment 40); the printed text is kept "
                          "(D30: suspected misprints flagged, never corrected)")
        cm("structure-source", "Gemini 4 Argon (experiment 41): blocks in reading order as Azure line ids, block "
                               "types, heading levels, continuations across pages, footnote calls, tables, verse "
                               "halves, equations as LaTeX, figures; converted by "
                               "experiments/41_azure_structure/masters.py. Owner's hand check: five articles.")
        if self.a.get("kind") == "window":
            cm("window", f"pages {self.a['first']}-{self.a['last']} of {self.a.get('pages_total')} "
                         f"(numbered 1-{len(self.pages)} here and in the ALTO file); page 1 was context only")
        if cam is not None:
            cm("front-sources", "journal, ids, subjects, date, volume, issue, pages and subject terms: Mandumah's "
                                "catalogue (experiment 29's master); title and authors: as printed (Argon)")
        cm("faithful-pdf", f"{self.stem}.scan.pdf (the scan, each word drawn with its own ink: inkscript native)")
        cm("alto-file", f"{self.stem}.alto.xml")
        st = self.stats
        cm("counts", f"{len(self.S.applied)} reader fixes applied, {sum(len(v) for v in self.S.sic.values())} "
                     f"suspected misprints flagged, {st['noise_lines_with_words']} noise lines with words and "
                     f"{st['dropped_lines_with_words']} dropped lines with words kept in the ALTO only, "
                     f"{st['added_paragraphs']} lines Azure missed added from Argon")
        for bid, t in front_blocks:
            cm("front-matter-block", t, bid)

    def back_notes(self, back):
        sic = [s for v in self.S.sic.values() for s in v]
        if sic:
            n = sub(back, "notes", {"notes-type": "suspected-misprints"})
            sub(n, "title", None, "Suspected misprints (D30: the printed text is kept; proposed corrections only)")
            for s in sic:
                sub(n, "p", None, f"{s['text']} → {s['corr']}" + (f" ({s['why']})" if s.get("why") else "")
                    + f" [line {s['at']}]")
        if self.S.applied:
            n = sub(back, "notes", {"notes-type": "reader-fixes"})
            sub(n, "title", None, "Azure misreadings fixed by Gemini 4 Argon (Azure's reading → the print)")
            for f in self.S.applied:
                sub(n, "p", None, f"{f.get('from')} → {f.get('to')}" + (f" ({f['why']})" if f.get("why") else "")
                    + f" [line {f['at']}]")

    # ---------------------------------------------------------------- ALTO
    def alto_xml(self):
        A = etree.Element(f"{{{ALTO}}}alto", nsmap={None: ALTO, "xlink": XL,
                                                    "xsi": "http://www.w3.org/2001/XMLSchema-instance"})
        A.set("SCHEMAVERSION", "4.4")
        A.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
              f"{ALTO} https://www.loc.gov/standards/alto/v4/alto-4-4.xsd")
        q = lambda t: f"{{{ALTO}}}{t}"  # noqa: E731
        D = sub(A, q("Description"))
        sub(D, q("MeasurementUnit"), None, "pixel")
        si = sub(D, q("sourceImageInformation"))
        sub(si, q("fileName"), None, f"{self.stem}.scan.pdf")
        sub(si, q("documentIdentifier"), {"documentIdentifierLocation": "Mandumah"}, self.stem)
        op = sub(D, q("OCRProcessing"), {"ID": "azure"})
        st = sub(op, q("ocrProcessingStep"))
        sub(st, q("processingCategory"), None, "contentGeneration")
        sub(st, q("processingStepDescription"), None, "Text recognition: words, boxes, lines, word confidence (WC).")
        sw = sub(st, q("processingSoftware"))
        sub(sw, q("softwareCreator"), None, "Microsoft")
        sub(sw, q("softwareName"), None, "Azure Document Intelligence")
        sub(sw, q("softwareVersion"), None, "prebuilt-read API 2024-11-30")
        pr = sub(D, q("Processing"), {"ID": "argon"})
        sub(pr, q("processingCategory"), None, "other")
        sub(pr, q("processingStepDescription"), None,
            "Structure by Gemini 4 Argon (experiment 41): blocks, reading order, types; fixes of Azure misreadings "
            "(ALTERNATIVE keeps Azure's reading). Boxes in pixels of the page at 300 dpi."
            + (f" A window: pages {self.a['first']}-{self.a['last']} of the article, numbered from 1."
               if self.a.get("kind") == "window" else ""))
        sw = sub(pr, q("processingSoftware"))
        sub(sw, q("softwareCreator"), None, "inkscript")
        sub(sw, q("softwareName"), None, "experiments/41_azure_structure/masters.py")
        T = sub(A, q("Tags"))
        for r in ("body", "title", "author", "sectionHeading", "footnote", "caption", "pageHeader", "pageFooter",
                  "pageNumber", "formulaInk", "pictureText", "noise"):
            sub(T, q("StructureTag"), {"ID": f"role.{r}", "TYPE": "paragraph-role", "LABEL": r,
                                        "DESCRIPTION": ROLE_DESC.get(r)})
        sub(T, q("OtherTag"), {"ID": "kind.formula", "TYPE": "content-kind", "LABEL": "formula",
                               "DESCRIPTION": "The ink of an inline formula: the JATS holds it as inline-formula."})
        sub(T, q("OtherTag"), {"ID": "fix.argon", "TYPE": "trust", "LABEL": "fixed",
                               "DESCRIPTION": "Azure's reading (ALTERNATIVE) fixed by Gemini 4 Argon to the print."})
        L = sub(A, q("Layout"))
        for lp in sorted(self.alto):
            p = lp + self.a["first"] - 1
            W, H = self.S.dims[p]
            P = sub(L, q("Page"), {"ID": f"page{lp}", "PHYSICAL_IMG_NR": lp, "WIDTH": W, "HEIGHT": H})
            PS = sub(P, q("PrintSpace"), {"HPOS": 0, "VPOS": 0, "WIDTH": W, "HEIGHT": H})
            for b in self.alto[lp]:
                self.alto_block(PS, b, lp, q)
        return A

    def alto_block(self, parent, b, lp, q):
        def pos(el, box):
            x0, y0, x1, y1 = box
            for k, v in (("HPOS", x0), ("VPOS", y0), ("WIDTH", x1 - x0), ("HEIGHT", y1 - y0)):
                el.set(k, f"{max(0.0, v):.0f}")

        def href(el, t):
            if t:
                el.set(f"{{{XL}}}href", f"{self.stem}.jats.xml#{t}")
                el.set(f"{{{XL}}}type", "simple")
        if b["kind"] == "ill":
            el = sub(parent, q("Illustration"), {"ID": b["id"], "TYPE": b["type"]})
            pos(el, b["box"])
            href(el, b["target"])
            return
        if b["kind"] == "table":
            el = sub(parent, q("ComposedBlock"), {"ID": b["id"], "TYPE": "table"})
            pos(el, b["box"])
            href(el, b["target"])
            for c in b["cells"]:
                self.alto_block(el, c, lp, q)
            return
        el = sub(parent, q("TextBlock"), {"ID": b["id"], "TAGREFS": f"role.{b['role']}"})
        lg = b.get("lang") or lang_of(self.text(b["ids"]))
        el.set("LANG", lg)
        el.set("BASEDIRECTION", "rtl" if lg == "ar" else "ltr")
        pos(el, ST.union([self.S.lines[i]["px"] for i in b["ids"]]))
        href(el, b["target"])
        for k, lid in enumerate(b["ids"], 1):
            Lx = self.S.lines[lid]
            if not Lx["text"].split():                  # a line a fix emptied (Argon: not printed)
                self.stats["lines_emptied_by_fixes"] += 1
                continue
            tl = sub(el, q("TextLine"), {"ID": f"{b['id']}l{k}"})
            tl.set("BASEDIRECTION", "rtl" if is_rtl(Lx["text"]) else "ltr")
            pos(tl, Lx["px"])
            ws = self.words_of(lid)
            for j, w in enumerate(ws):
                if j:
                    sub(tl, q("SP"))
                self.wn[lp] += 1
                tags = (["fix.argon"] if w["alt"] else []) + (["kind.formula"] if w["math"] else [])
                s = sub(tl, q("String"), {"ID": f"p{lp}w{self.wn[lp]:04d}", "CONTENT": w["text"]})
                if w["conf"] is not None:
                    s.set("WC", f"{w['conf']:.3f}")
                if tags:
                    s.set("TAGREFS", " ".join(tags))
                pos(s, w["box"])
                if w["alt"]:
                    sub(s, q("ALTERNATIVE"), {"PURPOSE": "azure"}, w["alt"])


ROLE = {"title": "title", "heading": "sectionHeading", "footnote": "footnote", "caption": "caption",
        "byline": "author"}
ROLE_DESC = {"formulaInk": "Azure's words of a display formula; the JATS holds the formula (MathML + LaTeX)",
             "pictureText": "words printed inside a picture; the picture shows them",
             "noise": "a line Gemini 4 Argon left out of the article (called noise, or dropped): kept here, counted"}


def build_master(a: dict) -> dict:
    cap = R.capture(a)
    if cap is None:
        return dict(stem=a["stem"], error="no answers")
    M = Master(a, cap)
    MAST.mkdir(parents=True, exist_ok=True)
    if M.crops.exists():
        shutil.rmtree(M.crops)
    art = M.build()
    alto = M.alto_xml()
    jp = MAST / f"{a['stem']}.jats.xml"
    doctype = ('<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with '
               'MathML3 v1.4 20241031//EN" "JATS-archivearticle1-4-mathml3.dtd">')
    jp.write_bytes(etree.tostring(art, xml_declaration=True, encoding="UTF-8", pretty_print=True,
                                  doctype=doctype))
    (MAST / f"{a['stem']}.alto.xml").write_bytes(etree.tostring(alto, xml_declaration=True, encoding="UTF-8",
                                                                pretty_print=True))
    pdf = MAST / f"{a['stem']}.pdf"            # edition takes page sizes and scan pictures from <stem>.pdf
    src = NOUT / a["stem"] / f"{a['stem']}.pdf"
    if not src.exists():
        src = NIN / a["stem"] / f"{a['stem']}.pdf"
    if pdf.exists() or pdf.is_symlink():
        pdf.unlink()
    os.symlink(os.path.relpath(src.resolve(), MAST), pdf)
    r = dict(stem=a["stem"], pages=len(M.pages), blocks=len(M.recs), **M.stats)
    jdump(MAST / "stats" / f"{a['stem']}.json", r)
    return r


# ------------------------------------------------------------------------------------------------ link and check

FORMATS = [("scan", "Scan PDF", "{s}.scan.pdf"), ("layout", "Layout PDF", "{s}.layout.pdf"),
           ("onecol", "One-column PDF", "{s}.onecol.pdf"), ("html", "Web page", "{s}.html"),
           ("jats", "JATS XML", "{s}.jats.xml"), ("md", "Markdown", "{s}.md"), ("jsonl", "JSON", "{s}.jsonl")]


def hardlink(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        if dst.is_file() and src.exists() and os.path.samefile(src, dst):
            return
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def link_one(a) -> dict:
    s = a["stem"]
    d = FMT / s
    nat = NOUT / s / f"{s}.pdf"
    if nat.exists():
        hardlink(nat, d / f"{s}.scan.pdf")
    hardlink(MAST / f"{s}.jats.xml", d / f"{s}.jats.xml")
    cr = MAST / f"{s}.crops"                   # the Markdown's picture links point at <stem>.crops/ beside it
    if cr.exists():
        for f in cr.iterdir():
            hardlink(f, d / f"{s}.crops" / f.name)
    files = {}
    for k, label, pat in FORMATS:
        f = d / pat.format(s=s)
        if f.exists():
            files[k] = dict(label=label, href=f"formats/{s}/{f.name}", bytes=f.stat().st_size)
    return dict(stem=s, files=files)


def cmd_link(args):
    f = FMT / "formats.json"
    rows = {r["stem"]: r for r in json.loads(f.read_text())} if f.exists() else {}
    for a in stems_of(args):
        rows[a["stem"]] = link_one(a)
    rows = [rows[a["stem"]] for a in sample() if a["stem"] in rows]
    jdump(f, rows)
    n = Counter(k for r in rows for k in r["files"])
    print(f"{len(rows)} articles; files: " + ", ".join(f"{k} {v}" for k, v in n.items()))


def argon_tokens(M: Master) -> dict:
    """Argon's block text as check.tokens, split by what each format is meant to carry."""
    from inkscript.edition.check import tokens
    out = {k: Counter() for k in ("read", "furniture", "equation", "picture", "inline_math")}
    for rec in M.recs:
        T = rec["type"]
        key = ("furniture" if T in ("header", "footer") else "equation" if T == "equation" and rec.get("latex")
               else "picture" if T == "figure" and rec.get("fig_box") else "read")
        for lid in rec["ids"]:
            L = M.S.lines[lid]
            t = L["text"]
            if key == "read":
                for m in M.S.math.get(lid, []):            # inline maths: the formats carry the formula
                    if m["from"] in t:
                        out["inline_math"].update(tokens(m["from"]))
                        t = t.replace(m["from"], " ", 1)
            out[key].update(tokens(t))
        for m in rec.get("missed") or []:              # running heads Azure missed (and those Argon hung on one) and
            if m.get("type") not in ("header", "footer", "equation") and T not in ("header", "footer"):  # formulas
                out["read"].update(tokens(m.get("text") or ""))
    return out


def jats_text(path: Path) -> str:
    """What the JATS master holds as the article: title, printed front-matter blocks, authors, body, notes,
    references (not the catalogue's front matter, not the lists of fixes and flags)."""
    root = etree.parse(str(path), etree.XMLParser(load_dtd=False, no_network=True)).getroot()
    parts = []
    for el in root.iter("article-title", "subtitle", "string-name"):
        parts.append(" ".join(el.itertext()))
    for cm in root.iter("custom-meta"):
        if (cm.findtext("meta-name") or "") == "front-matter-block":
            parts.append(cm.findtext("meta-value") or "")
    for el in root.iter("tex-math"):
        el.text = ""
    for sec in [root.find("body")] + root.findall("back/fn-group") + root.findall("back/ref-list"):
        if sec is not None:
            for m in sec.iter(f"{{{MML}}}math"):
                m.getparent().remove(m)
            parts.append(" ".join(sec.itertext()))
    return "\n".join(parts)


def cmd_check(args):
    from inkscript.edition import check as C
    from inkscript.enrich.schemas import validate_jats, validate_alto
    rows = []
    for a in stems_of(args):
        s = a["stem"]
        d = FMT / s
        cap = R.capture(a)
        M = Master(a, cap)
        M.build()
        A = argon_tokens(M)
        texts = {}
        for k, f, fn in (("scan", f"{s}.scan.pdf", "pdf"), ("layout", f"{s}.layout.pdf", "pdf"),
                         ("onecol", f"{s}.onecol.pdf", "pdf"), ("html", f"{s}.html", "html"),
                         ("md", f"{s}.md", "md"), ("jsonl", f"{s}.jsonl", "jsonl"), ("jats", f"{s}.jats.xml", "jats")):
            p = d / f
            if not p.exists():
                continue
            t = {"pdf": lambda q: "\n".join(C.text_of_pdf(q)), "html": C.text_of_html, "md": C.text_of_md,
                 "jsonl": C.text_of_jsonl, "jats": jats_text}[fn](p)
            texts[k] = Counter(C.tokens(t))
        r = dict(stem=s, argon_words=sum(A["read"].values()), furniture_words=sum(A["furniture"].values()),
                 equation_words=sum(A["equation"].values()), picture_words=sum(A["picture"].values()),
                 inline_math_words=sum(A["inline_math"].values()), formats={})
        for k, G in texts.items():
            want = A["read"] + (A["furniture"] + A["equation"] + A["picture"] + A["inline_math"]
                                if k in ("scan", "layout") else Counter())
            miss = {t: n - G[t] for t, n in want.items() if G[t] < n}
            if k == "onecol":                        # it renumbers notes and pages: digits are not compared
                miss = {t: n for t, n in miss.items() if not t.isdigit()}
            r["formats"][k] = dict(expected=sum(want.values()) if k != "onecol" else
                                   sum(n for t, n in want.items() if not t.isdigit()),
                                   missing=sum(miss.values()),
                                   examples=sorted(miss.items(), key=lambda x: -x[1])[:8])
        ck = d / f"{s}.checks.json"
        r["edition"] = json.loads(ck.read_text()) if ck.exists() else {}
        for e in r["edition"].values():
            e.pop("order_pages", None) if isinstance(e, dict) else None
        r["jats_errors"] = validate_jats(MAST / f"{s}.jats.xml")[:5]
        r["alto_errors"] = validate_alto(MAST / f"{s}.alto.xml")[:5]
        nr = NOUT / s / "native_pdf_report.json"
        if nr.exists():
            rep = json.loads(nr.read_text())[0]
            v = rep.get("verify") or []
            r["scan_verify"] = dict(words=sum(x["words"] for x in v), intact=sum(x["intact"] for x in v),
                                    lines=sum(x["lines"] for x in rep.get("lines", [])),
                                    lines_in_order=sum(x["in_order"] for x in rep.get("lines", [])),
                                    inversions=(rep.get("order") or {}).get("inversions"),
                                    lost_image=len(rep.get("lost_image") or []))
        r["stats"] = dict(M.stats)
        rows.append(r)
        print(f"  {s:24} " + " ".join(f"{k}:{v['missing']}/{v['expected']}" for k, v in r["formats"].items())
              + f"  jats {len(r['jats_errors'])} alto {len(r['alto_errors'])}", flush=True)
        jdump(OUT / "formats_check" / f"{s}.json", r)     # one file per article: a stop loses nothing
    if args.stems:
        return
    tot = dict(articles=len(rows), own={}, edition={}, scan_verify=Counter(), stats=Counter(),
               jats_invalid=sum(1 for r in rows if r["jats_errors"]),
               alto_invalid=sum(1 for r in rows if r["alto_errors"]))
    for r in rows:
        for k, v in r["formats"].items():
            t = tot["own"].setdefault(k, Counter())
            t.update(dict(expected=v["expected"], missing=v["missing"], articles_with_missing=int(v["missing"] > 0)))
        for k, v in r["edition"].items():
            if not isinstance(v, dict) or "words" not in v:
                tot["edition"].setdefault(k, Counter())["errors"] += 1
                continue
            t = tot["edition"].setdefault(k, Counter())
            w = v["words"]
            t.update({x: w.get(x, 0) for x in ("expected", "found", "missing", "missing_front", "missing_body",
                                               "duplicated", "extra")})
            if v.get("order"):
                t.update(dict(order_expected=v["order"]["expected"], order_in_order=v["order"]["in_order"],
                              block_inversions=v["order"].get("block_inversions", 0)))
            for kind, n in (w.get("missing_by_kind") or {}).items():
                t[f"missing_{kind}"] += n
            if v.get("formulas"):
                t.update(dict(formulas_expected=v["formulas"]["expected"], formulas_found=v["formulas"]["found"]))
        tot["scan_verify"].update(r.get("scan_verify") or {})
        tot["stats"].update(r["stats"])
    jdump(OUT / "formats_check.json", dict(total=tot, articles=rows))
    print(json.dumps(tot, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------------------------------------ main

def stems_of(args):
    arts = sample()
    if args.stems:
        arts = [a for a in arts if a["stem"] in set(args.stems)]
    return arts


def cmd_prep(args):
    rows = []
    for a in stems_of(args):
        cap = R.capture(a)
        r = prep(a, cap)
        rows.append(r)
        print(f"  {r['stem']:24} p{r['pages']:>3} fixes in Azure's words {r['fixes_written']:>4}, "
              f"not word for word {r['fixes_not_word_for_word']}", flush=True)
    f = NIN / "prep.json"
    old = {r["stem"]: r for r in json.loads(f.read_text())} if f.exists() else {}
    old.update({r["stem"]: r for r in rows})
    jdump(f, list(old.values()))


def cmd_build(args):
    for a in stems_of(args):
        r = build_master(a)
        print(f"  {a['stem']:24} " + " ".join(f"{k}={v}" for k, v in r.items() if k != "stem"), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "build", "link", "check"])
    ap.add_argument("--stems", nargs="*")
    args = ap.parse_args()
    {"prep": cmd_prep, "build": cmd_build, "link": cmd_link, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()
