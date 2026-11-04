"""Experiment 47: one master (one run's reading of one document) -> the rows of its version, tied to the ink.

Experiment 46's parse_article (imported) gives the article-level rows (titles, authors, notes, works, fixes, D33...);
this module adds what v2 needs on top: the character position of every line, fix, misprint and note call inside its
block's printed text (so a value can be pinned to its Azure words), sections, block parts per page, page regions, the
line crosswalk, table cells, verse lines, byline mentions with their titles, and citation mentions in reading order
(full citations, short forms, every «المرجع السابق»/«نفسه»/ibid./op. cit. marker of a note, Quran references)."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from lxml import etree

import ink47
from common47 import E46, fold, key, name_parts, split_titles, script, stemmed, to_int, year_of, SURA_KEYS, AYAT
import sys
sys.path.insert(0, str(E46))
from parse46 import BLOCK_ID, XML_LANG, ln, parse_article, text_of, ancestors  # noqa: E402

XLINK_T = "{http://www.w3.org/1999/xlink}title"
_HARAKAT = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ‌-‏‪-‮⁦-⁩﻿]")
_FMAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ئ": "ي", "ى": "ي", "ی": "ي", "ة": "ه",
                       "ک": "ك", "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7",
                       "٨": "8", "٩": "9"})

ROLE = {"title": "title", "title-printed": "title", "title-en": "title-translated", "subtitle": "title",
        "keywords": "keywords", "front-matter": "front-matter", "reference": "ref", "verse": "verse-group",
        "table-cell": "table-cell", "caption": "caption", "references-heading": "heading", "heading": "heading",
        "abstract": "abstract", "footnote": "footnote", "endnote": "endnote", "byline": "byline",
        "list-item": "list-item", "quote": "quote", "boxed": "paragraph", "appendix": "back-matter",
        "acknowledgements": "back-matter", "paragraph": "paragraph", "text-in-figure": "caption", "added": "paragraph",
        "other": "paragraph", "affiliation": "affiliation"}
REGION_ROLES = {"pageHeader", "pageNumber", "pageFooter", "noise", "pictureText", "pictureJunk", "formulaInk",
                "ornament", "showThrough", "otherArticle"}

# back-reference markers (longest first); kind ibid = the work cited just before, op_cit = an earlier work (named by
# its author / title before the marker), loc_cit = the same place
MARKERS = [
    (r"نفس\s+المرجع\s+السابق|نفس\s+المصدر\s+السابق|المرجع\s+السابق\s+نفسه|المصدر\s+السابق\s+نفسه|السابق\s+نفسه|السابق\s+ذاته", "ibid"),
    (r"المرجع\s+نفسه|المصدر\s+نفسه|المرجع\s+ذاته|المصدر\s+ذاته|نفس\s+المرجع|نفس\s+المصدر|المرجع\s+عينه|المصدر\s+عينه",
     "ibid"),
    (r"\bibid\b\.?|\bibidem\b|\bid\.(?=\s)|\bidem\b", "ibid"),
    (r"المرجع\s+السابق|مرجع\s+سابق|المصدر\s+السابق|مصدر\s+سابق|المراجع\s+السابقة|م\s?\.\s?س\s?\.?", "op_cit"),
    (r"\bop\.?\s?cit\b\.?|\bopus\s+citatum\b|\bouvr\.?\s+cit[ée]?\b\.?|\bart\.?\s+cit[ée]?\b\.?", "op_cit"),
    (r"\bloc\.?\s?cit\b\.?", "loc_cit"),
]
MARKER_RE = re.compile("|".join(f"(?P<k{i}>{p})" for i, (p, _) in enumerate(MARKERS)), re.I)
# a bare «السابق» / «نفسه» / «ذاته» is a marker only near the start of a note segment and before a locator or the end
BARE_RE = re.compile(r"(?<![\w\u0600-\u06ff])(?P<w>السابق|نفسه|ذاته)(?=\s*(?:[،,.:؛;)\]]|ص|ج|[0-9٠-٩]|$))")
LOCATOR_RE = re.compile(r"(?:(?:ج|جـ|مج|vol\.?|t\.)\s*(?P<vol>[0-9٠-٩]+))?[،,\s]*"
                        r"(?:(?:ص\s*ص|ص|pp?\.?|s\.)\s*[:.]?\s*)?(?P<pg>[0-9٠-٩]+(?:\s*[-–/]\s*[0-9٠-٩]+)*)", re.I)
VOLPAGE_RE = re.compile(r"(?P<vol>[0-9٠-٩]{1,2})\s*/\s*(?P<pg>[0-9٠-٩]+(?:\s*[-–]\s*[0-9٠-٩]+)?)")

SURA_NAME = r"(?P<sura>(?:آل\s+عمران|بني\s+إسرائيل|حم\s+السجدة|[^\s،,:؛()\[\]0-9٠-٩]{1,12}))"
AYA = r"(?P<a1>[0-9٠-٩]{1,3})(?:\s*[-–]\s*(?P<a2>[0-9٠-٩]{1,3}))?"
QURAN_RES = [
    re.compile(r"سورة\s+" + SURA_NAME + r"\s*[،,:]?\s*(?:من\s+)?(?:الآيات|الآية|الايات|الاية|آية|اية|آيه|الآيتان|الآيتين|رقم)?\s*[:：]?\s*(?:رقم\s*)?" + AYA),
    re.compile(r"(?:الآيات|الآية|الايات|الاية|آية|اية|الآيتان|الآيتين)\s*[:：]?\s*" + AYA.replace("a1", "a1").replace("a2", "a2")
               + r"\s*(?:من\s+)?سورة\s+" + SURA_NAME),
    re.compile(r"[\(\[]\s*" + SURA_NAME + r"\s*[:：،,]\s*" + AYA + r"\s*[\)\]]"),
]


def fold_map(s: str):
    """Folded string (fold46 without whitespace collapsing) and, for each folded char, its index in s."""
    out, idx = [], []
    for i, ch in enumerate(s):
        if _HARAKAT.match(ch):
            continue
        out.append(ch.translate(_FMAP).lower())
        idx.append(i)
    return "".join(out), idx


def ffind(hay_f: str, hay_idx: list, needle: str, start: int = 0) -> int:
    """Index in the original string where `needle` (folded) occurs at or after original index `start`; -1 if not."""
    nf = " ".join(fold_map(needle)[0].split())
    if len(nf) < 2:
        return -1
    fs = next((k for k, i in enumerate(hay_idx) if i >= start), len(hay_idx))
    k = hay_f.find(nf, fs)
    return hay_idx[k] if k >= 0 else -1


# ------------------------------------------------------------------ text of an element with event positions
def marked_text(e):
    """Same string as parse46.text_of(e), plus positions of line starts (<target>), reader-fix / sic spans and note
    calls in it: events = [(pos, kind, data)]."""
    raw, ev = [], []
    n = [0]

    def emit(s):
        if s:
            raw.append(s)
            n[0] += len(s)

    def walk(x):
        if not isinstance(x.tag, str):
            emit(x.tail)
            return
        name = ln(x)
        if name == "p" and x.get("content-type") == "parsed-citations":
            emit(x.tail)
            return
        if name == "target" and x.get("id"):
            ev.append((n[0], "line", x.get("id")))
        start = n[0]
        emit(x.text)
        for c in x:
            walk(c)
        if name == "named-content" and x.get("content-type") in ("reader-fix", "sic", "model-suggestion"):  # exp 66/68
            ev.append((start, x.get("content-type"), dict(rid=x.get("rid"), end=n[0], title=x.get(XLINK_T))))
        elif name == "xref" and x.get("ref-type") == "fn":
            ev.append((start, "call", dict(rid=x.get("rid"), end=n[0])))
        elif name in ("inline-formula", "inline-graphic"):
            ev.append((start, name, dict(end=n[0])))
        if x is not e:
            emit(x.tail)

    walk(e)
    s = "".join(raw)
    # collapse whitespace exactly as text_of does, mapping raw positions to collapsed ones
    out, pos_map, prev_space = [], [], True
    for ch in s:
        pos_map.append(len(out))
        if ch.isspace():
            if not prev_space:
                out.append(" ")
            prev_space = True
        else:
            out.append(ch)
            prev_space = False
    pos_map.append(len(out))
    t = "".join(out)
    if t.endswith(" "):
        t = t[:-1]
    L = len(t)

    def m(p):
        return min(pos_map[p], L)

    events = []
    for p, k, d in ev:
        if isinstance(d, dict) and "end" in d:
            d = dict(d, end=m(d["end"]))
        events.append((m(p), k, d))
    return t, events


# ------------------------------------------------------------------ anchors on the ink
class Ink:
    """One version's ALTO matched to the document's Azure pages."""

    def __init__(self, stem: str, azure: dict, alto: dict):
        self.stem, self.azure, self.alto = stem, azure, alto
        self.wmap, self.lmap, self.line, self.line_page, self.block_lines, self.tblock = {}, {}, {}, {}, {}, {}
        for p, P in alto.items():
            az = azure["pages"].get(p)
            if not az:
                continue
            wm = ink47.match_words(az, P)
            self.wmap.update(wm)
            self.lmap.update(ink47.line_map(az, P, wm))
            for b in P["blocks"]:
                self.tblock[b["id"]] = dict(b, page=p)
                self.block_lines[b["id"]] = [L["id"] for L in b["lines"]]
                for L in b["lines"]:
                    self.line[L["id"]] = L
                    self.line_page[L["id"]] = p

    def words_of_line(self, lid, tok_from=None, tok_to=None):
        L = self.line.get(lid)
        if not L:
            return []
        ss = L["strings"]
        if tok_from is not None:
            ss = ss[tok_from:tok_to]
        return [n for s in ss for n in self.wmap.get(s["id"], [])]

    def strings_of_line(self, lid):
        L = self.line.get(lid)
        return L["strings"] if L else []

    def place(self, page, ords, method):
        """-> anchor dict for a span of Azure words on one page (box = union of the words, text in Azure order)."""
        az = self.azure["pages"].get(page)
        if not az or not ords:
            return None
        a, b = min(ords), max(ords)
        ws = az["words"][a - 1:b]
        x0 = min(w["x"] for w in ws)
        y0 = min(w["y"] for w in ws)
        x1 = max(w["x"] + w["w"] for w in ws)
        y1 = max(w["y"] + w["h"] for w in ws)
        confs = [w["conf"] for w in ws if w["conf"] is not None]
        return dict(anchor_key=f"{self.stem}|p{page}|w{a}-{b}", stem=self.stem, page=page, first_word=a, last_word=b,
                    x=round(x0, 1), y=round(y0, 1), w=round(x1 - x0, 1), h=round(y1 - y0, 1),
                    text_azure=" ".join(w["text"] or "" for w in ws), wc_min=min(confs) if confs else None,
                    method=method)

    def place_box(self, page, box, method="box"):
        if not box:
            return None
        x, y, w, h = box
        return dict(anchor_key=f"{self.stem}|p{page}|b{round(x)},{round(y)},{round(w)},{round(h)}", stem=self.stem,
                    page=page, first_word=None, last_word=None, x=x, y=y, w=w, h=h, text_azure=None, wc_min=None,
                    method=method)

    def place_lines(self, lids, method="line"):
        """Anchors (one per page, in order) for whole lines."""
        byp = defaultdict(list)
        for lid in lids:
            p = self.line_page.get(lid)
            if p is None:
                continue
            byp[p] += self.words_of_line(lid)
        return [a for p in sorted(byp) for a in [self.place(p, byp[p], method)] if a]


class Block:
    """A JATS block's printed text with its line starts, for placing a character span on Azure words."""

    def __init__(self, bid, text, events, ink: Ink):
        self.id, self.text, self.ink = bid, text, ink
        self.lines = [(p, d) for p, k, d in events if k == "line"]
        self.events = events

    def span_lines(self, a, b):
        """[(line_id, tok_from, tok_to)] covering text[a:b] (tokens by whitespace; None when the line's tokens do
        not match its ALTO words one to one)."""
        out = []
        L = self.lines
        for i, (p, lid) in enumerate(L):
            q = L[i + 1][0] if i + 1 < len(L) else len(self.text)
            if q <= a or p >= b:
                if not (p == q == a):
                    continue
            seg = self.text[p:q]
            toks = seg.split()
            ss = self.ink.strings_of_line(lid)
            if len(toks) != len(ss) or not toks:
                out.append((lid, None, None))
                continue
            # token index of a and b inside the line
            starts, pos = [], 0
            for t in toks:
                j = seg.find(t, pos)
                starts.append(p + j)
                pos = j + len(t)
            ta = max([k for k, s in enumerate(starts) if s <= max(a, p)] or [0])
            tb = max([k for k, s in enumerate(starts) if s < min(b, q)] or [ta]) + 1
            out.append((lid, ta, tb))
        return out

    def place(self, a, b):
        """Anchors (one per page) for text[a:b]; method words when every line maps word for word, else line."""
        if not self.lines:
            return []
        parts = self.span_lines(a, b) or [(self.lines[0][1], None, None)]
        byp, exact = defaultdict(list), True
        for lid, ta, tb in parts:
            p = self.ink.line_page.get(lid)
            if p is None:
                continue
            if ta is None:
                exact = False
                byp[p] += self.ink.words_of_line(lid)
            else:
                byp[p] += self.ink.words_of_line(lid, ta, tb)
        m = "words" if exact else "line"
        return [x for p in sorted(byp) for x in [self.ink.place(p, byp[p], m)] if x]


# ------------------------------------------------------------------ the version
def parse_version(mdir: Path, stem: str, run: str, azure: dict) -> dict:
    R = parse_article(mdir, stem, run)                       # experiment 46's rows (article, notes, works, ...)
    root = etree.parse(str(mdir / f"{stem}.jats.xml")).getroot()
    alto = ink47.read_alto(mdir / f"{stem}.alto.xml")
    ink = Ink(stem, azure, alto)
    V = dict(R=R, ink=ink, alto=alto, anchors={}, extra_anchors=[])
    art_lang = root.get(XML_LANG)
    fix_works_v35(root, R, stem)                             # v3.5b: editors / translators apart, both years, cited page
    cx = contrib_extras(root)

    def anchor(a, owner_kind=None, owner_key=None):
        """Register anchors (list, one per page); return the first one's key; others go to anchor_links."""
        if not a:
            return None
        if isinstance(a, dict):
            a = [a]
        for x in a:
            V["anchors"].setdefault(x["anchor_key"], x)
        for k, x in enumerate(a[1:], 2):
            if owner_kind:
                V["extra_anchors"].append(dict(anchor_key=x["anchor_key"], owner_kind=owner_kind,
                                               owner_key=owner_key, role="continued", seq=k))
        return a[0]["anchor_key"]

    # ---- blocks with positions
    blocks, bobj, line_block = [], {}, {}
    # the ALTO TextBlocks that carry a JATS block's text by id or by xlink:href (#p2b7): a block whose own line list
    # is empty (kwd-group, contrib) takes their lines, so flags and fixes on them land on the block (fix round 1)
    jats_ids = {b["block_id"] for b in R["blocks"]}
    tb_lines = defaultdict(list)
    for p_, P_ in alto.items():
        for tb in P_["blocks"]:
            tgt = tb["id"] if tb["id"] in jats_ids else ((tb.get("href") or "").rsplit("#", 1)[-1] or None)
            if tgt in jats_ids:
                tb_lines[tgt] += [L["id"] for L in tb["lines"]]
    els = {}
    for e in root.iter():
        if isinstance(e.tag, str) and e.get("id") and BLOCK_ID.match(e.get("id")) and e.get("id") not in els:
            els[e.get("id")] = e
    for b in R["blocks"]:
        e = els.get(b["block_id"])
        t, ev = b["text"], []
        if e is not None:
            if ln(e) in ("verse-group", "kwd-group"):
                kids = e.findall("verse-line") if ln(e) == "verse-group" else e.findall("kwd")
                sep = " / " if ln(e) == "verse-group" else "؛ "
                parts_t, parts_e, off = [], [], 0
                for kd in kids:
                    kt, ke = marked_text(kd)
                    parts_t.append(kt)
                    parts_e += [(p + off, k, dict(d, end=d["end"] + off) if isinstance(d, dict) else d)
                                for p, k, d in ke]
                    off += len(kt) + len(sep)
                t2, ev2 = sep.join(parts_t), parts_e
            elif ln(e) == "custom-meta":
                mv = e.find("meta-value")
                t2, ev2 = marked_text(mv) if mv is not None else ("", [])
            else:
                t2, ev2 = marked_text(e)
            if t2 == b["text"]:
                t, ev = t2, ev2
            else:                      # should not happen; keep the line targets only
                lids = [x.get("id") for x in e.iter("target") if x.get("id")]
                ev = [(0, "line", lid) for lid in lids[:1]]
                V.setdefault("text_mismatch", []).append(b["block_id"])
        bo = Block(b["block_id"], t, ev, ink)
        bobj[b["block_id"]] = bo
        lids = json.loads(b["alto_lines"]) or tb_lines.get(b["block_id"], [])
        for lid in lids:
            line_block.setdefault(lid, b["block_id"])
        # stats from the ALTO words of the block's lines (Azure confidences)
        wcs = [s["wc"] for lid in lids for s in ink.strings_of_line(lid) if s["wc"] is not None]
        anc = ink.place_lines(lids, "line") if lids else []
        if not anc and b["hpos"] is not None:
            anc = [ink.place_box(b["page"], (b["hpos"], b["vpos"], b["width"], b["height"]))]
        b2 = dict(block_id=b["block_id"], ord=b["ord"], page=b["page"], last_page=b["last_page"],
                  role=ROLE.get(b["kind"], "paragraph"), section_id=b["section"], lang=b["lang"], text=b["text"],
                  role_source=f"reader:{b['kind']}", text_source="reader", n_words=len(wcs),
                  wc_mean=round(sum(wcs) / len(wcs), 4) if wcs else None, wc_min=min(wcs) if wcs else None,
                  n_low_wc=sum(1 for w in wcs if w < 0.5), anchor_key=anchor(anc, "block", b["block_id"]),
                  _lines=lids)
        blocks.append(b2)
    V["blocks"] = blocks
    V["bobj"] = bobj
    bmap = {b["block_id"]: b for b in blocks}

    # ---- block parts (one per ALTO TextBlock the block's lines sit in)
    parts = []
    for b in blocks:
        groups = []
        for lid in b["_lines"]:
            ab = re.sub(r"l\d+$", "", lid)
            if not groups or groups[-1][0] != ab:
                groups.append((ab, [lid]))
            else:
                groups[-1][1].append(lid)
        for k, (ab, lids) in enumerate(groups, 1):
            tb = ink.tblock.get(ab)
            page = tb["page"] if tb else ink.line_page.get(lids[0])
            box = tb["box"] if tb else None
            anc = ink.place_lines(lids, "line")
            parts.append(dict(block_id=b["block_id"], part=k, page=page, alto_block_id=ab if tb else None,
                              x=box[0] if box else None, y=box[1] if box else None, w=box[2] if box else None,
                              h=box[3] if box else None, first_line_id=lids[0], last_line_id=lids[-1],
                              anchor_key=anchor(anc[:1])))
    V["block_parts"] = parts

    # ---- page regions (ink that is not article text) and the line crosswalk
    regions, lmap = [], []
    for p, P in alto.items():
        for tb in P["blocks"]:
            role = ink47.role_of(tb["tags"])
            if role in REGION_ROLES:
                lids = [L["id"] for L in tb["lines"]]
                txt = " ".join(s["content"] or "" for L in tb["lines"] for s in L["strings"])
                anc = ink.place_lines(lids, "line") if lids else [ink.place_box(p, tb["box"])]
                regions.append(dict(region_id=tb["id"], page=p, role=role, text=txt,
                                    x=tb["box"][0] if tb["box"] else None, y=tb["box"][1] if tb["box"] else None,
                                    w=tb["box"][2] if tb["box"] else None, h=tb["box"][3] if tb["box"] else None,
                                    decided_by="reader", anchor_key=anchor(anc[:1])))
            for L in tb["lines"]:
                m = ink.lmap.get(L["id"], {})
                blk = line_block.get(L["id"])
                if not blk and ink47.role_of(tb["tags"]) not in REGION_ROLES:
                    ref = tb["id"] if tb["id"] in bmap else (tb.get("href") or "").rsplit("#", 1)[-1]
                    blk = ref if ref in bmap else None
                lmap.append(dict(alto_line_id=L["id"], page=p, azure_line_no=m.get("azure_line_no"),
                                 block_id=blk, region_id=None if blk else tb["id"],
                                 x=L["box"][0] if L["box"] else None, y=L["box"][1] if L["box"] else None,
                                 w=L["box"][2] if L["box"] else None, h=L["box"][3] if L["box"] else None,
                                 map_method="box-overlap" if m.get("azure_line_no") else "none"))
    V["page_regions"], V["line_map"] = regions, lmap
    azl = {}       # (page, azure line no) -> alto line id (first)
    for r in lmap:
        if r["azure_line_no"]:
            azl.setdefault((r["page"], r["azure_line_no"]), r["alto_line_id"])
    V["azl"] = azl

    # ---- sections
    secs = []
    for o, s in enumerate(root.iter("sec")):
        par = next((a.get("id") for a in ancestors(s) if ln(a) == "sec"), None)
        t = s.find("title")
        depth = sum(1 for a in ancestors(s) if ln(a) == "sec") + 1
        secs.append(dict(section_id=s.get("id"), parent_id=par, level=to_int(s.get("disp-level")) or depth, ord=o,
                         heading_block_id=t.get("id") if t is not None else None,
                         heading=text_of(t) if t is not None else None))
    V["sections"] = [x for x in secs if x["section_id"]]

    # ---- notes, calls and their targets
    note_ids = {n["note_id"] for n in R["notes"]}
    notes = []
    fns = {fn.get("id"): fn for fn in root.iter("fn")}
    for n in R["notes"]:
        fn = fns.get(n["note_id"])
        fb = next((p.get("id") for p in fn.iter("p") if p.get("id") and BLOCK_ID.match(p.get("id"))), None) \
            if fn is not None else None
        b = bmap.get(fb)
        kind, by = n["kind"], None
        if fn is not None:
            if fn.get("custom-type") == "author-note" or (fn.getparent() is not None and
                                                          ln(fn.getparent()) == "author-notes"):
                kind = "author-note"                          # v3.5b: the starred note about an author
            elif fn.get("fn-type") == "custom" and fn.get("custom-type") in NOTE_BY:
                by = fn.get("custom-type")                    # v3.5b: a translator's / editor's / publisher's note
        notes.append(dict(note_id=n["note_id"], kind=kind, label=n["label"], label_int=to_int(n["label"]),
                          ord=n["ord"], page=n["page"], first_block_id=fb, text=n["text"],
                          anchor_key=b["anchor_key"] if b else None, written_by=by))
    V["notes"] = notes
    calls, targets = [], []
    seq = 0
    for bid, bo in bobj.items():
        for p, k, d in bo.events:
            if k != "call":
                continue
            seq += 1
            rids = (d.get("rid") or "").split()
            ok = [r for r in rids if r in note_ids]
            st = "no-target" if not ok else ("multi" if len(ok) > 1 else "ok")
            anc = bo.place(p, d["end"])
            calls.append(dict(call_seq=seq, call_text=bo.text[p:d["end"]], block_id=bid, char_offset=p, status=st,
                              anchor_key=anchor(anc[:1])))
            targets += [dict(call_seq=seq, note_id=r) for r in ok]
    V["note_calls"], V["note_call_targets"] = calls, targets
    V["n_calls_46"] = len(R["note_calls"])

    # ---- figures (+ boxes from ALTO), table cells, inline formulas
    figs = []
    illus = {i: dict(v, page=p) for p, P in alto.items() for i, v in P.get("illustrations", {}).items()}
    composed = {c["id"]: dict(c, page=p) for p, P in alto.items() for c in P["composed"]}
    inl = defaultdict(int)
    fig_els = {}
    for tag in ("fig", "table-wrap", "disp-formula"):
        for e in root.iter(tag):
            if e.get("id"):
                fig_els[e.get("id")] = e
    for f in R["figures"]:
        fid = f["xml_id"]
        e = fig_els.get(fid)
        box, page = None, f["page"]
        if fid in illus:
            box, page = illus[fid]["box"], illus[fid]["page"]
        elif fid in composed:
            box, page = composed[fid]["box"], composed[fid]["page"]
        cap_id = None
        if e is not None:
            cap = e.find("caption")
            if cap is not None:
                c1 = next((x.get("id") for x in cap.iter() if isinstance(x.tag, str) and x.get("id")), None)
                cap_id = c1
        mathml = None
        if e is not None and f["kind"] == "equation":
            mm = e.find(".//{http://www.w3.org/1998/Math/MathML}math")
            if mm is not None:
                mathml = etree.tostring(mm, encoding="unicode")
        anchor_block = None
        if e is not None:
            pe = e.getparent()
            while pe is not None and not (pe.get("id") and BLOCK_ID.match(pe.get("id"))):
                pe = pe.getparent()
            anchor_block = pe.get("id") if pe is not None else None
        if f["kind"] in ("inline-equation", "inline-picture"):
            continue      # positional ids (inline-formula<k>): rebuilt below from their block
        anc = ink.place_box(page, box) if box and page else None
        figs.append(dict(figure_id=fid, kind=f["kind"], page=page, x=box[0] if box else None,
                         y=box[1] if box else None, w=box[2] if box else None, h=box[3] if box else None,
                         alto_id=fid if (fid in illus or fid in composed) else None, caption_block_id=cap_id,
                         anchor_block_id=anchor_block, label=f["label"], caption=f["caption"], alt_ar=f["alt_ar"],
                         alt_en=f["alt_en"], text_in_figure=f["text_in_figure"], tex=f["tex"], mathml=mathml,
                         specific_use=f["specific_use"], crop_key=f["graphic"], anchor_key=anchor(anc),
                         fig_type=e.get("fig-type") if e is not None and ln(e) == "fig" else None))
    # inline formulas / pictures: id from their block and order in it (a reread of another block cannot renumber)
    MML = "{http://www.w3.org/1998/Math/MathML}math"
    for tag, kind in (("inline-formula", "inline-equation"), ("inline-graphic", "inline-picture")):
        for q in root.iter(tag):
            pe = q.getparent()
            while pe is not None and not (pe.get("id") and BLOCK_ID.match(pe.get("id"))):
                pe = pe.getparent()
            bid = pe.get("id") if pe is not None else "x"
            inl[(bid, tag)] += 1
            fid = f"{'if' if tag == 'inline-formula' else 'ig'}-{bid}-{inl[(bid, tag)]}"
            tex = q.find(".//tex-math")
            mm = q.find(".//" + MML)
            b = bmap.get(bid)
            figs.append(dict(figure_id=fid, kind=kind, page=b["page"] if b else None, x=None, y=None, w=None, h=None,
                             alto_id=None, caption_block_id=None, anchor_block_id=bid if b else None, label=None,
                             caption=None, alt_ar=None, alt_en=None, text_in_figure=None,
                             tex=(tex.text or "").strip() if tex is not None else None,
                             mathml=etree.tostring(mm, encoding="unicode") if mm is not None else None,
                             specific_use=q.get("specific-use"),
                             crop_key=q.get("{http://www.w3.org/1999/xlink}href"),
                             anchor_key=b["anchor_key"] if b else None, fig_type=None))
    V["figures"] = figs
    V["figure_notes"] = figure_notes(root, bmap, {n["note_id"]: n for n in notes})
    cells = []
    for t in root.iter("table-wrap"):
        tid = t.get("id")
        if not tid:
            continue
        occupied = set()
        r = 0
        for tr in t.iter("tr"):
            c = 0
            for cell in tr:
                if not isinstance(cell.tag, str) or ln(cell) not in ("td", "th"):
                    continue
                while (r, c) in occupied:
                    c += 1
                rs, cs = int(cell.get("rowspan") or 1), int(cell.get("colspan") or 1)
                for dr in range(rs):
                    for dc in range(cs):
                        occupied.add((r + dr, c + dc))
                txt = text_of(cell)
                if txt or cell.get("id"):
                    cells.append(dict(figure_id=tid, row=r, col=c, rowspan=rs, colspan=cs,
                                      is_header=int(ln(cell) == "th" or ln(tr.getparent()) == "thead"),
                                      block_id=cell.get("id"), text=txt))
                c += cs
            r += 1
    V["table_cells"] = cells

    # ---- verse lines
    verses = []
    for vg in root.iter("verse-group"):
        gid = vg.get("id")
        prev = vg.getprevious()
        hint = None
        if prev is not None and isinstance(prev.tag, str):
            pt = text_of(prev)
            m = re.search(r"(قال|يقول|وقال|قول|كقول)\s+(الشاعر|[^\s:،]+(?:\s+[^\s:،]+)?)", pt[-80:])
            hint = m.group(0) if m else None
        for k, vl in enumerate(vg.findall("verse-line"), 1):
            t, ev = marked_text(vl)
            calls_ = [d.get("rid") for p, kk, d in ev if kk == "call"]
            for p, kk, d in sorted([x for x in ev if x[1] == "call"], key=lambda x: -x[0]):
                t = (t[:p] + t[d["end"]:]).strip()
            lids = [x.get("id") for x in vl.iter("target") if x.get("id")]
            anc = ink.place_lines(lids, "line")
            parts_ = re.split(r"\s{3,}|\s\*\s|\s…\s", t)
            verses.append(dict(verse_id=vl.get("id") or f"{gid}-{k}", group_block_id=gid, seq=k, part="line", text=t,
                               text_bare=" ".join(fold(t).split()), call_ids=" ".join(c for c in calls_ if c) or None,
                               poet_hint=hint, anchor_key=anchor(anc[:1])))
    V["verse_lines"] = verses

    # ---- text corrections (fixes of Azure misreadings, suspected misprints)
    inline, suggested = {}, set()
    for bid, bo in bobj.items():
        for p, k, d in bo.events:
            if k in ("reader-fix", "sic", "model-suggestion") and d.get("rid"):
                inline.setdefault(d["rid"], (bid, p, d["end"], d.get("title")))
                if k == "model-suggestion":     # exp 66 D30 guard: a refused Gemini fix, its own layer (never applied)
                    suggested.add(d["rid"])
    corr = []
    for kind, rows in (("azure-misread", R["fixes"]), ("misprint", R["misprints"])):
        for x in rows:
            xid = x["fix_id"] if kind == "azure-misread" else x["sic_id"]
            bid, a, b, title = inline.get(xid, (None, None, None, None))
            anc, am = [], "none"
            if bid:
                anc = bobj[bid].place(a, b)
                am = "word" if anc and anc[0]["method"] == "words" else ("line-only" if anc else "none")
            if not anc and x["alto_line"]:
                anc = ink.place_lines([x["alto_line"]], "line")
                am = "line-only" if anc else "none"
                bid = bid or line_block.get(x["alto_line"])
            wcs = []
            if bid and a is not None:
                for lid, ta, tb in bobj[bid].span_lines(a, b):
                    ss = ink.strings_of_line(lid)
                    ss = ss[ta:tb] if ta is not None else [s for s in ss if "fix.argon" in s["tags"]] or ss
                    wcs += [s["wc"] for s in ss if s["wc"] is not None]
            if kind == "misprint" and str(x.get("why") or "").startswith("model suggestion, not applied (D30 guard"):
                suggested.add(xid)              # a refused fix on a line no block holds (a running head): no inline span
            corr.append(dict(xml_id=xid, layer="model-suggestion" if xid in suggested else kind, block_id=bid,
                             char_start=a, char_end=b,
                             azure_reading=x.get("azure_reading") if kind == "azure-misread" else None,
                             azure_wc=min(wcs) if wcs else None,
                             printed=x.get("print") if kind == "azure-misread" else x.get("printed"),
                             proposed=x.get("proposed") if kind == "misprint" else None,
                             applied_to_text=1 if kind == "azure-misread" else 0, why=x.get("why"),
                             asserted_by="reader", actor_id="model:gemini-4-argon", status="open",
                             anchor_key=anchor(anc[:1]), anchor_method=am, _line_label=x.get("line_label"),
                             _alto_line=x.get("alto_line")))
    V["text_corrections"] = corr
    nfix = defaultdict(int)
    nsic = defaultdict(int)
    for c in corr:
        if c["block_id"]:
            (nfix if c["layer"] == "azure-misread" else nsic)[c["block_id"]] += 1
    for b in blocks:
        b["n_fixes"], b["n_misprints"] = nfix.get(b["block_id"], 0), nsic.get(b["block_id"], 0)

    # ---- byline mentions (each printed name in the byline, titles kept) and affiliations
    bylines = [b for b in blocks if b["role"] in ("byline", "title") or "author" in (b["role_source"] or "")]
    author_regions = [tb for p, P in alto.items() for tb in P["blocks"] if ink47.role_of(tb["tags"]) == "author"]
    bm = []
    for a in R["authors"]:
        name = a["printed_name"] or ""
        nk = fold(name)
        hit = None
        for b in [x for x in blocks if x["role"] == "byline"] + [x for x in blocks if x["page"] == 1]:
            bo = bobj.get(b["block_id"])
            if not bo or not nk:
                continue
            hf, hidx = fold_map(bo.text)
            i = ffind(hf, hidx, name)
            if i >= 0:
                hit = (b, bo, i, i + len(name))
                break
        titles, printed, anc, bid = None, name, [], None
        if hit:
            b, bo, i, j = hit
            pre = bo.text[max(0, i - 25):i]
            m = re.search(r"((?:(?:أ\s*\.\s*م\s*\.\s*د|ا\s*\.\s*د|أ\s*\.\s*د|م\s*\.\s*م|د|أ|م)\s*[./]\s*|الدكتورة?\s+|"
                          r"الأستاذة?\s+(?:الدكتورة?\s+)?|الاستاذة?\s+|الشيخ\s+|Prof\.?\s*|Dr\.?\s*|Pr\.?\s*)+)\s*$",
                          pre, re.I)
            if m:
                titles = " ".join(m.group(1).split())
                printed = bo.text[i - len(pre) + m.start():j]
            anc = bo.place(i - (len(pre) - m.start() if m else 0), j)
            bid = b["block_id"]
        else:
            t2, rest = split_titles(name)
            titles = t2 or None
            for tb in author_regions:
                txt = " ".join(s["content"] or "" for L in tb["lines"] for s in L["strings"])
                if nk and fold(rest)[:12] and fold(rest)[:12] in fold(txt):
                    anc = ink.place_lines([L["id"] for L in tb["lines"]], "line")
                    break
        x = cx[a["seq"]] if a["seq"] < len(cx) else {}
        titles = titles or x.get("prefix")                   # experiment 65: the honorific kept in the masters
        bm.append(dict(byline_pos=a["seq"], printed=printed, titles=titles, name_text=split_titles(name)[1] or name,
                       script=script(name), email=a.get("email"), block_id=bid,
                       min_word_conf=anc[0]["wc_min"] if anc else None, reader_fixes=None,
                       anchor_key=anchor(anc[:1]), _parts=name_parts(name),
                       is_corresponding=x.get("corresp"), ids=json.dumps(x["ids"], ensure_ascii=False, sort_keys=True)
                       if x.get("ids") else None, contrib_type=x.get("contrib_type"), role_phrase=x.get("role"),
                       position=x.get("position"), contacts=json.dumps(x["contacts"], ensure_ascii=False,
                                                                       sort_keys=True) if x.get("contacts") else None))
        # v3.5b same_as (and fix round 3's twins): the person printed again in another script, a mention of its own
        for tw in x.get("twins") or []:
            if not tw or script(tw) == script(name) or script(tw) is None:
                continue
            thit, tanc = None, []
            for b in [y for y in blocks if y["role"] == "byline"] + [y for y in blocks if y["page"] == 1]:
                bo = bobj.get(b["block_id"])
                if not bo:
                    continue
                hf, hidx = fold_map(bo.text)
                i = ffind(hf, hidx, tw)
                if i >= 0:
                    thit = b["block_id"]
                    tanc = bo.place(i, i + len(tw))
                    break
            lg = (x.get("twin_lang") or {}).get(tw)
            bm.append(dict(byline_pos=a["seq"], printed=tw,
                           titles=split_titles(tw)[0] or (x.get("tw_prefix") or {}).get(lg) or None,
                           name_text=split_titles(tw)[1] or tw, script=script(tw), email=None, block_id=thit,
                           min_word_conf=tanc[0]["wc_min"] if tanc else None, reader_fixes=None,
                           anchor_key=anchor(tanc[:1]), _parts=name_parts(tw), is_corresponding=None, ids=None,
                           contrib_type=x.get("contrib_type"),
                           role_phrase=" | ".join((x.get("tw_roles") or {}).get(lg) or []) or None,
                           position=" | ".join((x.get("tw_pos") or {}).get(lg) or []) or None, contacts=None,
                           _twin_of=a["seq"]))
    V["byline_mentions"] = bm
    V["affiliations"] = affiliations_v35(root, R)

    # ---- citation mentions
    V["citation_mentions"] = citation_mentions(root, R, bobj, bmap, ink, anchor, stem)

    # ---- Quran references (notes and body) and quotations (﴿…﴾)
    V["quran"] = quran_places(blocks, bobj, V["citation_mentions"], anchor)
    # ---- v3.5b: handwriting, stamps and scan problems the reader saw (custom-meta; the ALTO is unchanged)
    V["page_marks"] = page_marks(root, V, ink, anchor)
    # ---- experiment 65: identifiers found by code on every line (sidecar <stem>.ids.json)
    V["printed_ids"] = printed_ids(mdir, stem, V, ink, anchor)
    return V


# ------------------------------------------------------------------ prompt v3.5b fields (2026-10-22)
# Where experiment 43 writes them: enrich43.py / meta43.enrich / refs43.v35_parts (its README "Prompt v3.5"). Each
# reader below returns nothing for a master without them, so every v3.3 master loads as before.
NOTE_BY = {"translator", "editor", "publisher"}
CAL = {"islamic": "hijri", "hijri": "hijri", "gregorian": "gregorian"}
NONAUTHOR_GROUPS = {"editor", "translator", "supervisor"}


def _names_of(el) -> list:
    out = []
    for x in el:
        if not isinstance(x.tag, str):
            continue
        if ln(x) == "name":
            out.append(((x.findtext("surname") or "").strip(), (x.findtext("given-names") or "").strip()))
        elif ln(x) in ("string-name", "collab"):
            out.append((text_of(x), ""))
    return out


def ec_v35(ec) -> tuple:
    """(v3.5b parts, the authors without the editors and translators or None when there are none to remove, field
    overrides) of one element-citation."""
    v, over = {}, {}
    groups = {}
    for pg in ec.findall("person-group"):
        groups.setdefault(pg.get("person-group-type") or "author", []).extend(_names_of(pg))
    for k, t in (("editors", "editor"), ("translators", "translator")):
        if groups.get(t):
            v[k] = [list(x) for x in groups[t]]
    died = [text_of(c) for c in ec.findall("comment") if c.get("content-type") == "death-date"]
    if died:
        v["died"] = died
    ed = ec.find("edition")
    if ed is not None and text_of(ed):
        v["edition"] = text_of(ed)
    years = ec.findall("year")
    if years:
        if years[0].get("calendar"):
            v["year_calendar"] = CAL.get(years[0].get("calendar"))
        if len(years) > 1:
            v["year2"] = text_of(years[1])
            v["year2_calendar"] = CAL.get(years[1].get("calendar") or "")
            over["year"] = text_of(years[0])            # parse46 kept the last year element: the first is the year
    prs = ec.findall("page-range")
    plain = [text_of(x) for x in prs if not x.get("content-type")]
    for x in prs:
        if x.get("content-type") == "cited-pages":
            v["cited_pages"] = text_of(x)
        elif x.get("content-type") == "folio":
            v["folio"] = text_of(x)
    if len(plain) != len(prs):
        over["page_range"] = plain[-1] if plain else None   # the work's own range, not the page pointed to
    for tag, ct, k in (("date-in-citation", "access-date", "access_date"), ("institution", "library", "library"),
                       ("comment", "shelfmark", "shelfmark"), ("comment", "degree", "degree")):
        x = next((e for e in ec.findall(tag) if e.get("content-type") == ct), None)
        if x is not None and text_of(x):
            v[k] = text_of(x)
    for tag, k in (("conf-name", "conf_name"), ("conf-loc", "conf_loc")):
        x = ec.find(tag)
        if x is not None and text_of(x):
            v[k] = text_of(x)
    authors = None
    if any(t in groups for t in NONAUTHOR_GROUPS):
        # parse46 took every name of the citation (ec.iter("name")): an editor became a co-author. The same order,
        # without the names inside an editor / translator / supervisor group.
        def keep(x):
            return not any(ln(a) == "person-group" and (a.get("person-group-type") or "author") in NONAUTHOR_GROUPS
                           for a in x.iterancestors())
        authors = [((n.findtext("surname") or "").strip(), (n.findtext("given-names") or "").strip())
                   for n in ec.iter("name") if keep(n)]
        authors += [(text_of(n), "") for n in ec.iter("string-name") if keep(n)]
        authors += [(text_of(n), "") for n in ec.iter("collab") if keep(n)]
    return v, authors, over


def fix_works_v35(root, R, stem):
    """Each of parse46's works gets its element-citation's v3.5b parts (w["_v35"]) and its people by role
    (w["_people"]); its authors, year and page range are corrected where parse46 mixed them (editors read as
    authors, the second year, the cited page)."""
    ecs = {}
    for ref in root.iter("ref"):
        for s_, ec in enumerate(ref.findall("element-citation")):
            ecs[f"{stem}|ref:{ref.get('id')}|{s_}"] = ec
    fns = {fn.get("id"): fn for fn in root.iter("fn")}
    for n in R["notes"]:
        fn = fns.get(n["note_id"])
        for s_, ec in enumerate(fn.findall(".//element-citation") if fn is not None else []):
            ecs[f"{stem}|note:{n['note_id']}|{s_}"] = ec
    for w in R["works"]:
        ec = ecs.get(w["work_id"])
        if ec is None:
            continue
        v, authors, over = ec_v35(ec)
        w["_v35"] = v
        if authors is not None:
            w["authors"] = json.dumps(authors, ensure_ascii=False) if authors else None
            w["first_author"] = " ".join(x for x in (authors[0][1], authors[0][0]) if x) if authors else None
            w["first_author_key"] = key(authors[0][0]) if authors else None
        if "year" in over:
            w["year"], w["year_int"] = over["year"], year_of(over["year"])
        if "page_range" in over:
            w["page_range"] = over["page_range"]
        try:
            au = json.loads(w["authors"] or "[]")
        except Exception:                                    # noqa: BLE001
            au = []
        died = v.get("died") or []
        people = []
        for k, (sn, gn) in enumerate(au):
            # refs43 writes one death-date comment per author who has one, in author order, not tied to the name:
            # one date goes to the first author; as many dates as authors go one each
            d = died[k] if len(died) == len(au) else (died[0] if k == 0 and len(died) == 1 else
                                                     (died[k] if k < len(died) else None))
            people.append(dict(role="author", seq=k + 1, surname=sn, given=gn, died=d))
        for role, k_ in (("editor", "editors"), ("translator", "translators")):
            for k, (sn, gn) in enumerate(v.get(k_) or []):
                people.append(dict(role=role, seq=k + 1, surname=sn, given=gn, died=None))
        w["_people"] = people


def mention_v35(w, in_ref_list: bool) -> dict:
    """The v3.5b columns of one citation mention (all None for a back reference or a citation without them)."""
    v = (w or {}).get("_v35") or {}
    src = None
    if w:
        src = "cited-pages" if v.get("cited_pages") else ("page-range" if w.get("page_range") else
                                                          ("fpage" if w.get("fpage") else None))
        if in_ref_list and not v.get("cited_pages"):
            src = None                       # a reference-list entry's pages are the work's own, not a page cited
    wp = None
    if w and (in_ref_list or v.get("cited_pages")):
        wp = w.get("page_range") or ("-".join(x for x in (w.get("fpage"), w.get("lpage")) if x) or None)
    return dict(edition=v.get("edition"), year_calendar=v.get("year_calendar"), year2=v.get("year2"),
                year2_calendar=v.get("year2_calendar"), work_pages=wp, cited_pages_source=src,
                died=" | ".join(v["died"]) if v.get("died") else None, access_date=v.get("access_date"),
                ms_library=v.get("library"), ms_shelfmark=v.get("shelfmark"), ms_folio=v.get("folio"),
                thesis_degree=v.get("degree"), conf_name=v.get("conf_name"), conf_loc=v.get("conf_loc"),
                _people=(w or {}).get("_people") or [])


def contrib_extras(root) -> list:
    """Per contrib, in parse46's order (article-meta iter("contrib")): corresp, printed ids, the reader's contrib-type,
    the printed role words, and its name printed again in another script (name-alternatives string-name[@xml:lang])."""
    am = root.find("front/article-meta")
    out = []
    for c in (am.iter("contrib") if am is not None else []):
        ids = {}
        for x in c.findall("contrib-id"):
            if x.get("contrib-id-type") and text_of(x):
                ids[x.get("contrib-id-type")] = text_of(x)
        # experiment 65: <role content-type="position"> is the post / rank, the others the printed role words; a
        # role, a post, an affiliation or e-mail with xml:lang belongs to the name printed in that language
        roles = [r for r in c.findall("role") if not r.get(XML_LANG)]
        role = next((r for r in roles if r.get("content-type") != "position"), None)
        pos = [text_of(r) for r in roles if r.get("content-type") == "position" and text_of(r)]
        twins = [text_of(x) for x in c.findall("name-alternatives/string-name") if x.get(XML_LANG)
                 and x.get("specific-use") != "printed-on-the-page"]
        twin_lang = {text_of(x): x.get(XML_LANG) for x in c.findall("name-alternatives/string-name")
                     if x.get(XML_LANG) and x.get("specific-use") != "printed-on-the-page"}
        tw_roles, tw_pos = {}, {}
        for r in c.findall("role"):
            lg = r.get(XML_LANG)
            if lg and text_of(r):
                (tw_pos if r.get("content-type") == "position" else tw_roles).setdefault(lg, []).append(text_of(r))
        pr = next((x for x in c.iter("string-name") if x.get("specific-use") == "printed-on-the-page"
                   and not x.get(XML_LANG)), None)
        prefix = text_of(pr.find("prefix")) if pr is not None and pr.find("prefix") is not None else None
        tw_prefix = {x.get(XML_LANG): text_of(x.find("prefix")) for x in c.iter("string-name")
                     if x.get("specific-use") == "printed-on-the-page" and x.get(XML_LANG) and x.find("prefix") is not None}
        contacts = {}
        ems = [text_of(e) for e in c.iter("email") if text_of(e)]
        if len(ems) > 1:
            contacts["emails"] = ems
        for tag, k in (("phone", "phones"), ("uri", "urls")):
            v = [text_of(e) for e in c.iter(tag) if text_of(e)]
            if v:
                contacts[k] = v
        printings = [x.get("rid") for x in c.findall("xref") if x.get("specific-use") == "printed-again"]
        if printings:
            contacts["printed_again_in"] = printings
        out.append(dict(corresp=1 if c.get("corresp") == "yes" else None, ids=ids or None,
                        contrib_type=c.get("contrib-type"), role=text_of(role) if role is not None else None,
                        position=" | ".join(pos) or None, twins=twins, twin_lang=twin_lang, tw_roles=tw_roles,
                        tw_pos=tw_pos, prefix=prefix or None, tw_prefix=tw_prefix, contacts=contacts or None))
    return out


def affiliations_v35(root, R) -> list:
    """parse46's affiliation rows (unchanged, so the institutions linked from them stay the same), with the faculty
    the reader gave apart (v3.5b institution[@content-type=faculty]; parse46 also keeps it inside orgname) and an
    extra affiliation the reader gave in parts marked assembled."""
    am = root.find("front/article-meta")
    els = {}
    for i, c in enumerate(am.iter("contrib") if am is not None else []):
        for j, a in enumerate(c.findall("aff")):
            els[(i, j)] = a
    out = []
    for r in R["affiliations"]:
        a = els.get((r["author_seq"], r["seq"]))
        r = dict(r, faculty=None, assembled=None)
        if a is not None:
            fac = [text_of(x) for x in a.findall("institution") if x.get("content-type") == "faculty"]
            if fac:
                r["faculty"] = " | ".join(fac)
            if a.get("content-type") == "additional":
                r["assembled"] = 1
            # experiment 65: the twin's affiliation (another script) and the one it translates
            r["_lang"], r["_id"], r["_rid"] = a.get(XML_LANG), a.get("id"), a.get("rid")
        out.append(r)
    return out


def figure_notes(root, bmap, notes) -> list:
    """Notes and «المصدر:» lines printed under a table or a figure, tied to it (v3.5b table-wrap-foot / fig p)."""
    out = []
    for t in root.iter("table-wrap", "fig"):
        fid = t.get("id")
        if not fid:
            continue
        holders = t.findall("table-wrap-foot") if ln(t) == "table-wrap" else [t]
        k = 0
        for h in holders:
            for x in h:
                if not isinstance(x.tag, str):
                    continue
                n = ln(x)
                if n == "p":
                    ct = x.get("content-type")
                    if ln(t) == "fig" and ct not in ("figure-note", "source"):
                        continue
                    kind = "source" if ct == "source" else ("table-note" if ln(t) == "table-wrap" else "figure-note")
                    bid, nid = x.get("id"), None
                elif n == "fn" and ln(t) == "table-wrap":
                    kind = "footnote"
                    nid = x.get("id")
                    bid = next((p.get("id") for p in x.iter("p") if p.get("id")), None)
                elif n == "attrib":
                    kind, bid, nid = "source", x.get("id"), None
                else:
                    continue
                k += 1
                b = bmap.get(bid)
                out.append(dict(figure_id=fid, seq=k, kind=kind, block_id=bid if b else None, note_id=nid,
                                text=(notes[nid]["text"] if nid in notes else text_of(x)) or None,
                                anchor_key=b["anchor_key"] if b else None))
    return out


def page_marks(root, V, ink, anchor) -> list:
    """custom-meta handwriting-lines / stamp-lines (Azure line labels P:N) and scan-problem («page 3: blur, faint»)."""
    out = {}
    for cm in root.iter("custom-meta"):
        nm = (cm.findtext("meta-name") or "").strip()
        val = text_of(cm.find("meta-value")) if cm.find("meta-value") is not None else ""
        if nm in ("handwriting-lines", "stamp-lines"):
            kind = nm.split("-")[0]
            for lab in val.split():
                m = re.match(r"^(\d+):(\d+)", lab)
                if not m:
                    continue
                pg, no = int(m.group(1)), int(m.group(2))
                al = V["azl"].get((pg, no))
                anc = ink.place_lines([al], "line") if al else []
                txt = " ".join(s["content"] or "" for s in ink.strings_of_line(al)) if al else None
                out[f"{kind}|{lab}"] = dict(mark_id=f"{kind}|{lab}", page=pg, kind=kind, problem=None, line_id=lab,
                                            text=txt or None, anchor_key=anchor(anc[:1]), source=nm)
        elif nm == "scan-problem":
            for m in re.finditer(r"page\s+(\d+)\s*:\s*([^;]+)", val):
                pg = int(m.group(1))
                for pr in [x.strip() for x in m.group(2).split(",") if x.strip()]:
                    out[f"scan-problem|{pg}|{pr}"] = dict(mark_id=f"scan-problem|{pg}|{pr}", page=pg,
                                                          kind="scan-problem", problem=pr, line_id=None, text=None,
                                                          anchor_key=None, source=nm)
    return [out[k] for k in sorted(out)]


BOOK_PARTS = (("source", "title"), ("article-title", "title"), ("chapter-title", "chapter"),
              ("publisher-name", "publisher"), ("publisher-loc", "place"), ("year", "year"), ("string-date", "date"),
              ("edition", "edition"), ("series", "series"), ("volume", "volume"), ("isbn", "isbn"))
GROUP_FIELD = {"author": "authors", "editor": "editors", "translator": "translators"}


def article_v35(root) -> dict:
    """The article-level v3.5b fields (meta43.enrich) as {field: value}: doc_type (the prompt's word) and
    article_type (JATS), conference.*, thesis.*, reviewed_book.*, original.*, series_part. Empty for a v3.3 master
    (its @article-type is the builder's default, not a reading, and is not taken)."""
    am = root.find("front/article-meta")
    out = {}
    if am is None:
        return out
    sub = am.find("article-categories/subj-group[@subj-group-type='document-type']/subject")
    if sub is not None and text_of(sub):
        out["doc_type"] = text_of(sub)
        out["article_type"] = root.get("article-type")
    cf = am.find("conference")
    if cf is not None:
        for tag, k in (("conf-name", "name"), ("conf-loc", "place"), ("conf-date", "date")):
            x = cf.find(tag)
            if x is not None and text_of(x):
                out[f"conference.{k}"] = text_of(x)
    for pr in am.findall("product"):
        typ = pr.get("product-type")
        if typ == "thesis":
            for tag, ct, k in (("comment", "degree", "degree"), ("institution", None, "university"),
                               ("year", None, "year")):
                x = next((e for e in pr.findall(tag) if e.get("content-type") == ct), None)
                if x is not None and text_of(x):
                    out[f"thesis.{k}"] = text_of(x)
            sv = pr.find("person-group[@person-group-type='supervisor']")
            if sv is not None:
                names = [" ".join(x for x in (g, s_) if x) for s_, g in _names_of(sv)]
                if names:
                    out["thesis.supervisor"] = "؛ ".join(names)
        elif typ == "book":
            for pg in pr.findall("person-group"):
                t = pg.get("person-group-type") or "author"
                names = [" ".join(x for x in (g, s_) if x) for s_, g in _names_of(pg)]
                if names:
                    out[f"reviewed_book.{GROUP_FIELD.get(t, t)}"] = "؛ ".join(names)
            for tag, k in BOOK_PARTS:
                x = pr.find(tag)
                if x is not None and text_of(x) and f"reviewed_book.{k}" not in out:
                    out[f"reviewed_book.{k}"] = text_of(x)
            for x in pr.findall("comment"):
                if x.get("content-type") == "death-date" and text_of(x):
                    out["reviewed_book.died"] = text_of(x)
    ra = am.find("related-article[@related-article-type='translated-from']")
    if ra is not None:
        for tag, k in (("article-title", "title"), ("string-name", "author"), ("source", "source")):
            x = ra.find(tag)
            if x is not None and text_of(x):
                out[f"original.{k}"] = text_of(x)
        if ra.get(XML_LANG):
            out["original.lang"] = ra.get(XML_LANG)
    for cm in am.iter("custom-meta"):
        if (cm.findtext("meta-name") or "").strip() == "series-part" and cm.find("meta-value") is not None:
            out["series_part"] = text_of(cm.find("meta-value"))
    # experiment 65: printed lines kept as fields (leaks43): how to cite, the journal's section, licence, copyright,
    # a closing signature's place and date, the journal's ISSN printed on the pages (several joined by " | ")
    many = defaultdict(list)
    for cm in am.iter("custom-meta"):
        nm = (cm.findtext("meta-name") or "").strip()
        if nm in ("how-to-cite", "signature") and cm.find("meta-value") is not None:
            many[nm.replace("-", "_")].append(text_of(cm.find("meta-value")))
    for sg in am.iter("subj-group"):
        if sg.get("subj-group-type") == "heading":
            many["journal_section"] += [text_of(x) for x in sg.findall("subject")]
    pm = am.find("permissions")
    if pm is not None:
        many["copyright"] += [text_of(x) for x in pm.findall("copyright-statement")]
        many["license"] += [text_of(x) for x in pm.findall("license")]
        many["license_url"] += [x.get("{http://www.w3.org/1999/xlink}href") for x in pm.findall("license")
                                if x.get("{http://www.w3.org/1999/xlink}href")]
    jm = root.find("front/journal-meta")
    for x in (jm.findall("issn") if jm is not None else []):
        if x.get("specific-use") == "printed":
            many["issn_printed"].append(text_of(x))
    for k, v in many.items():
        v = [y for y in dict.fromkeys(v) if y]
        if v:
            out[k] = " | ".join(v)
    return out


def printed_ids(mdir: Path, stem: str, V: dict, ink, anchor) -> list:
    """experiment 65: every identifier found by code on the pages (<stem>.ids.json beside the masters): kind, value,
    printed form, check, place, owner and the ink of its line."""
    p = mdir / f"{stem}.ids.json"
    if not p.exists():
        return []
    try:
        ids = json.loads(p.read_text(encoding="utf-8")).get("ids") or []
    except (OSError, ValueError):
        return []
    out = []
    for k, x in enumerate(ids, 1):
        al = x.get("alto_line")
        anc = ink.place_lines([al], "line") if al else []
        ow = x.get("owner") or {}
        out.append(dict(seq=k, kind=x.get("kind"), value=x.get("value"), printed=x.get("printed"),
                        valid=1 if x.get("valid") else 0, place=x.get("place"), owner_kind=ow.get("kind"),
                        owner_ref=ow.get("contrib") or ow.get("ref") or ow.get("where"), page=x.get("page"),
                        azure_line=x.get("line"), alto_line_id=al, block_id=x.get("block"), jats_home=x.get("home"),
                        jats_id=x.get("jats_id"), note=x.get("note"), anchor_key=anchor(anc[:1])))
    return out


# ------------------------------------------------------------------ citations
def _ec_fields(w: dict) -> dict:
    keep = ("pub_type", "authors", "first_author", "article_title", "chapter_title", "source_title", "year", "volume",
            "issue", "fpage", "lpage", "page_range", "publisher", "place", "doi", "url", "series", "extra")
    d = {k: w.get(k) for k in keep if w.get(k)}
    if d.get("authors"):
        d["authors"] = json.loads(d["authors"])
    if d.get("extra"):
        d["extra"] = json.loads(d["extra"])
    d.update({k: v for k, v in (w.get("_v35") or {}).items() if v})
    return d


RICH_RE = re.compile(r"تحقيق|تح\s*:|دار\s|مكتبة|مطبعة|منشورات|مؤسسة|ط\s*[0-9٠-٩]|الطبعة|طبعة|بيروت|القاهرة|دمشق|"
                     r"بغداد|عمان|الرياض|تونس|الجزائر|الكويت|(?<![0-9٠-٩])(?:1[3-9]|20)[0-9٠-٩]{2}(?![0-9٠-٩])|"
                     r"[0-9٠-٩]{3,4}\s*هـ|press|éd\.|ed\.|edition|verlag|paris|london|cairo|beirut", re.I)


def mention_kind(w: dict, printed: str | None = None) -> str:
    """full = a citation a reader could find the work from (title plus publisher, place, year, edition or a
    journal); short = a title or author+title alone («اللمع في النحو، 59»)."""
    t = w.get("source_title") or w.get("article_title") or ""
    if re.search(r"القرآن|القران|المصحف", t) and len(t.split()) <= 4:
        return "quran"
    has_title = bool(w.get("source_title") or w.get("article_title") or w.get("chapter_title"))
    rich = any(w.get(k) for k in ("publisher", "place", "year", "doi", "url")) or \
        (w.get("article_title") and w.get("source_title")) or "edition" in (w.get("extra") or "")
    if has_title and not rich and printed:
        rest = printed
        for k in ("source_title", "article_title", "chapter_title"):
            if w.get(k):
                rest = rest.replace(w[k], " ")
        rich = bool(RICH_RE.search(rest))
    if not has_title and w.get("first_author") and w.get("year") and (w.get("place") or w.get("publisher")) and \
            re.search(r"[«»“”]", printed or w.get("printed") or ""):
        # the reader's element-citation lost the title, but the print quotes one beside author, place and year
        # (0328 fn-p4-1 «Les principes généraux …», Chaudet, باريس ١٩٦٧): a reader can find the work (fix round 1)
        return "full"
    return "full" if has_title and rich else "short"


def citation_mentions(root, R, bobj, bmap, ink, anchor, stem) -> list:
    """Every citing place of the version, each with its span in the printed text, ink anchor and reading position."""
    by_container = defaultdict(list)
    for w in R["works"]:
        by_container[(w["origin"], w["container_id"])].append(w)
    out = []
    # reference list
    for ref in root.iter("ref"):
        mc = ref.find("mixed-citation")
        bid = mc.get("id") if mc is not None else None
        b, bo = bmap.get(bid), bobj.get(bid)
        for k, w in enumerate(by_container.get(("reference", ref.get("id")), [])):
            anc = bo.place(0, len(bo.text)) if bo else []
            out.append(dict(container_kind="ref-list", container_id=ref.get("id"), seq_in_container=k + 1,
                            kind=mention_kind(w, bo.text if bo else w["printed"]), marker=None,
                            printed=bo.text if bo else w["printed"],
                            parsed=_ec_fields(w), cited_volume=None,
                            cited_pages=(w.get("_v35") or {}).get("cited_pages"),
                            page=b["page"] if b else w["page"], block_id=bid, anchors=anc,
                            _y=anc[0]["y"] if anc else 0, _w=w, _hint=None, _note_ord=None, **mention_v35(w, True)))
    # notes, in their order; each note split into its citations and back-reference markers by position
    fns = {fn.get("id"): fn for fn in root.iter("fn")}
    for n in R["notes"]:
        fn = fns.get(n["note_id"])
        pblocks = [p.get("id") for p in fn.iter("p") if p.get("id") and p.get("id") in bobj] if fn is not None else []
        if not pblocks:
            continue
        # the note's text is its blocks' texts joined by a space (as parse46 does); keep the offsets per block
        segs, pos = [], 0
        for bid in pblocks:
            t = bobj[bid].text
            segs.append((pos, pos + len(t), bid))
            pos += len(t) + 1
        text = " ".join(bobj[bid].text for bid in pblocks)
        hf, hidx = fold_map(text)
        items = []           # (start, end, kind, payload)
        cursor = 0
        ws = by_container.get(("note", n["note_id"]), [])
        for w in ws:
            title = w["source_title"] or w["article_title"] or w["chapter_title"]
            i = ffind(hf, hidx, title, cursor) if title else -1
            if i < 0 and title:
                i = ffind(hf, hidx, title, 0)
            st = i
            if i >= 0:
                try:
                    names = json.loads(w["authors"] or "[]")
                except Exception:
                    names = []
                for sn, gn in names[:1]:
                    for nm in (f"{gn} {sn}".strip(), sn, gn):
                        j = ffind(hf, hidx, nm, max(0, i - 120)) if nm else -1
                        if 0 <= j < i and j >= cursor - 1:
                            st = min(st, j)
                            break
                end = i + len(title)
                items.append((st, end, "ec", w))
                cursor = end
            else:
                items.append((None, None, "ec", w))
        for m in MARKER_RE.finditer(text):
            kind = next(MARKERS[int(g[1:])][1] for g, v in m.groupdict().items() if v)
            items.append((m.start(), m.end(), kind, m.group(0)))
        for rx in QURAN_RES:
            for m in rx.finditer(text):
                if any(a is not None and a <= m.start() < b for a, b, k, _ in items):
                    continue
                items.append((m.start(), m.end(), "quran", m.group(0)))
        taken = [(a, b) for a, b, k, _ in items if a is not None]
        for m in BARE_RE.finditer(text):
            a = m.start()
            if any(x <= a < y for x, y in taken):
                continue
            before = text[:a]
            seg_start = max(before.rfind(sep) for sep in (".", "؛", ";", "انظر", "وانظر", "ينظر", "\n"))
            head = re.sub(r"^\s*[\(\[]?\s*[0-9٠-٩*]+\s*[\)\].\-–]?\s*", "", before[seg_start + 1 if seg_start >= 0 else 0:])
            if len(head.split()) <= 6 and not re.search(r"(قال|ذكر|يرى|أن|إن|هو|هي|في|الذي|التي)\s*$", head):
                kind = "ibid" if m.group("w") in ("نفسه", "ذاته") else "op_cit"
                if m.group("w") in ("نفسه", "ذاته") and len(head.split()) >= 1 and not re.search(r"[،,:]\s*$", head):
                    continue      # «الأمر نفسه»: an ordinary word, not a marker
                items.append((a, m.end(), kind, m.group(0)))
        items.sort(key=lambda x: (x[0] if x[0] is not None else 10 ** 9))
        prev_end = 0
        b0 = bmap.get(pblocks[0])
        for k, (a, b, kind, payload) in enumerate(items):
            nxt = next((x[0] for x in items[k + 1:] if x[0] is not None), len(text))
            if kind == "ec":
                w = payload
                s0, s1 = (a, max(b, nxt)) if a is not None else (None, None)
                if s0 is not None and nxt > b:
                    tail = text[b:nxt]
                    c2 = re.search(r"\s(?:وانظر|انظر|وينظر|ينظر|وللمزيد|وراجع|راجع|و?قارن|see also|voir aussi)\b|\.\s",
                                   tail)
                    s1 = b + c2.start() if c2 else nxt
                printed = text[s0:s1].strip(" ،,;؛") if s0 is not None else None
                rec = dict(container_kind="note", container_id=n["note_id"], kind=mention_kind(w, printed), marker=None,
                           printed=printed or w["printed"], parsed=_ec_fields(w),
                           cited_volume=w.get("volume"), cited_pages=(w.get("_v35") or {}).get("cited_pages") or
                           w.get("page_range") or w.get("fpage"), _w=w, _hint=None, _span=(s0, s1),
                           **mention_v35(w, False))
            elif kind == "quran":
                rec = dict(container_kind="note", container_id=n["note_id"], kind="quran", marker=None,
                           printed=payload, parsed=None, cited_volume=None, cited_pages=None, _w=None, _hint=None,
                           _span=(a, b), **mention_v35(None, False))
            else:
                hint_start = prev_end
                for sep in ("وانظر", "انظر", "ينظر", ". ", "؛"):
                    j = text.rfind(sep, prev_end, a)
                    if j >= 0:
                        hint_start = max(hint_start, j + len(sep))
                hint = text[hint_start:a]
                if not re.search(r"[^\W\d_]", hint) and hint_start > prev_end:
                    # fix round 2: «محمد مرشد ناجي. (المرجع السابق)»: the author ends with a period before the bracketed
                    # marker, so the segment after the last «. » holds only «(»; the hint is the segment before it
                    h0 = prev_end
                    for sep in ("وانظر", "انظر", "ينظر", ". ", "؛"):
                        j = text.rfind(sep, prev_end, hint_start - 2)
                        if j >= 0:
                            h0 = max(h0, j + len(sep))
                    hint_start = h0
                    hint = text[hint_start:a]
                hint = re.sub(r"^\s*[\(\[]?\s*[0-9٠-٩*]+\s*[\)\].\-–]?\s*", "", hint).strip(" ،,:.-()[]")
                tail = text[b:nxt][:40]
                vp = VOLPAGE_RE.search(tail)
                lm = LOCATOR_RE.search(tail)
                vol = vp.group("vol") if vp else (lm.group("vol") if lm else None)
                pg = vp.group("pg") if vp else (lm.group("pg") if lm else None)
                s1 = b + (lm.end() if lm and lm.start() < 6 else (vp.end() if vp else 0))
                rec = dict(container_kind="note", container_id=n["note_id"], kind=kind, marker=payload,
                           printed=text[hint_start:s1].strip(" ،,;؛:"), parsed=None, cited_volume=vol,
                           cited_pages=pg, _w=None, _hint=hint, _span=(hint_start, s1),
                           **dict(mention_v35(None, False), cited_pages_source="locator" if pg else None))
            s0, s1 = rec.pop("_span")
            anc = []
            if s0 is not None:
                for x0, x1, bid in segs:
                    a2, b2 = max(s0, x0), min(s1, x1)
                    if a2 < b2 or (a2 == b2 == x0):
                        anc += bobj[bid].place(a2 - x0, b2 - x0)
            if not anc and b0:
                anc = bobj[pblocks[0]].place(0, len(bobj[pblocks[0]].text))
            rec.update(seq_in_container=k + 1, page=n["page"] or (b0["page"] if b0 else None),
                       block_id=pblocks[0], anchors=anc, _y=anc[0]["y"] if anc else 0, _note_ord=n["ord"],
                       _note_text=n["text"])
            out.append(rec)
            if b is not None:
                prev_end = b if kind in ("ec", "quran") else s1
    # reading order: page, then position on the page (footnotes at the foot, the reference list where printed)
    # notes keep their printed order (labels); the reference list sits by page and position among them
    cy = {}
    for m in out:
        k = (m["container_kind"], m["container_id"])
        pg = m["anchors"][0]["page"] if m["anchors"] else (m["page"] or 0)
        pos = (m["page"] or pg, 0, m["_note_ord"]) if m["container_kind"] == "note" else (pg, 1, m["_y"])
        cy[k] = min(cy.get(k, (10 ** 6, 9, 10 ** 9)), pos)
    out.sort(key=lambda m: (cy[(m["container_kind"], m["container_id"])], m["container_id"] or "",
                            m["seq_in_container"]))
    counts = defaultdict(int)
    for o, m in enumerate(out, 1):
        m["reading_ord"] = o
        ak = anchor(m["anchors"][:1]) if m["anchors"] else None
        if len(m["anchors"]) > 1:
            anchor(m["anchors"])
        m["anchor_key"] = ak
        base = ak or f"{stem}|p{m['page']}|{m['container_id']}"
        counts[base] += 1
        m["mention_id"] = f"{base}|{counts[base]}"
        m["printed_fixed"] = None
    return out


def quran_places(blocks, bobj, mentions, anchor) -> list:
    rows = []

    def sura_no(name):
        k = key(name)
        return SURA_KEYS.get(k) or SURA_KEYS.get(re.sub(r"^ال", "", k))

    for b in blocks:
        bo = bobj.get(b["block_id"])
        if not bo or not bo.text:
            continue
        t = bo.text
        seen = []
        for rx in QURAN_RES:
            for m in rx.finditer(t):
                if any(x <= m.start() < y for x, y in seen):
                    continue
                s = sura_no(m.group("sura"))
                if not s:
                    continue
                a1 = to_int(m.group("a1"))
                a2 = to_int(m.group("a2")) if m.group("a2") else None
                if not a1 or a1 > AYAT[s - 1] or (a2 and (a2 < a1 or a2 > AYAT[s - 1])):
                    continue
                seen.append((m.start(), m.end()))
                anc = bo.place(m.start(), m.end())
                rows.append(dict(source_kind="note-ref" if b["role"] in ("footnote", "endnote") else "inline-ref",
                                 block_id=b["block_id"], quoted_text=None, printed_ref=m.group(0), sura=s,
                                 aya_from=a1, aya_to=a2 or a1, method="ref-only", score=None,
                                 anchor_key=anchor(anc[:1]), _pos=m.start()))
        for m in re.finditer(r"[﴿﴾]\s*([^﴿﴾]{3,400}?)\s*[﴿﴾]|\{\s*([^{}]{3,400}?)\s*\}", t):
            q = (m.group(1) or m.group(2) or "").strip()
            if not re.search("[؀-ۿ]", q):
                continue
            anc = bo.place(m.start(), m.end())
            # a reference right after the quotation («﴿…﴾ (البقرة: 255)») gives its sura and aya
            near = t[m.end():m.end() + 40]
            s = a1 = a2 = None
            for rx in QURAN_RES:
                mm = rx.search(near)
                if mm and mm.start() < 8 and sura_no(mm.group("sura")):
                    s = sura_no(mm.group("sura"))
                    a1 = to_int(mm.group("a1"))
                    a2 = to_int(mm.group("a2")) if mm.group("a2") else a1
                    if not a1 or a1 > AYAT[s - 1]:
                        s = a1 = a2 = None
                    break
            rows.append(dict(source_kind="inline-quote", block_id=b["block_id"], quoted_text=q,
                             printed_ref=near[:mm.end()] if s else None, sura=s, aya_from=a1, aya_to=a2,
                             method="bracket+ref" if s else "bracket-only", score=None,
                             anchor_key=anchor(anc[:1]), _pos=m.start()))
    return rows
