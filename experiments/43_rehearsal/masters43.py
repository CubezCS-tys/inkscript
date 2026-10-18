"""Experiment 43: experiment 41's masters (JATS 1.4 + ALTO 4.4) from answers that went through rules43, with the
code that v2 needs. Experiment 41's modules are imported and extended here; nothing in experiment 41 changes.

  * other_article blocks: kept out of the JATS (the article's text); in the ALTO as TextBlocks role.otherArticle
  * split lines (verse halves Azure read as one line, cut by word): each part's box is the union of its own Azure
    words (experiment 41 cut the line's box in proportion to characters, so the halves ran together)
  * ornaments (rules43): taken out of the text; their ink kept in the ALTO as TextBlocks role.ornament
  * lines put back by the never-noise rule are ordinary block lines (blocks of type "other" for runs)

    capture43(a, raw_dir, rules=True)  -> experiment 41's capture (structure.assemble on the answers in raw_dir)
    build43(a, raw_dir, mast_dir, rules=True) -> writes <mast_dir>/<stem>.jats.xml, .alto.xml, crops, stats
With rules=False the answers and code are exactly experiment 41's (the harness check: same masters as 41's).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
E41 = HERE.parent / "41_azure_structure"
sys.path.insert(0, str(E41))
sys.path.insert(0, str(HERE))
import structure as ST  # noqa: E402
import reader as R  # noqa: E402
import masters as M  # noqa: E402
from lxml import etree  # noqa: E402

OUT = HERE / "out"
ST.COARSE.setdefault("other_article", "other")
ORIG_STORE = ST.Store


def azure_words(a):
    """line id -> Azure's words [{"text", "box" (px, 300 dpi)}] (experiment 41's frame)."""
    az = M.azure_raw(a)
    cache = {}

    def words(lid):
        if lid not in cache:
            p, k = (int(x) for x in lid.split(":"))
            pg = az["pages"][p - 1]
            s = 300.0 if pg.get("unit", "inch") == "inch" else 1.0
            ws = []
            for w in M.line_words(pg, M.nonempty_lines(pg)[k - 1]):
                xs, ys = w["polygon"][0::2], w["polygon"][1::2]
                ws.append(dict(text=w["content"], box=[min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s]))
            cache[lid] = ws
        return cache[lid]
    return words


def px_to_b(px, W, H):
    return [round(px[0] * 1000 / W, 1), round(px[1] * 1000 / H, 1), round(px[2] * 1000 / W, 1),
            round(px[3] * 1000 / H, 1)]


class Store43(ORIG_STORE):
    """experiment 41's Store, then: word boxes for split parts; ornaments out of the text."""

    def __init__(self, a, pages, answers, apply=True):
        super().__init__(a, pages, answers, apply)
        words = azure_words(a)
        self.ornaments = []
        self.word_boxed = 0
        for lid in list(self.orig):
            L = self.lines[lid]
            if not L.get("split"):
                continue
            parts = [x for x in self.lines.values() if x.get("split_of") == lid]
            ws = words(lid)
            toks = L["text"].split()
            cnt = [len(x.get("azure_text", x["text"]).split()) for x in parts]
            if len(ws) != len(toks) or sum(cnt) != len(toks):
                continue
            W, H = self.dims[L["page"]]
            k = 0
            for x, n in zip(parts, cnt):
                bx = ST.union([w["box"] for w in ws[k:k + n]])
                k += n
                if bx:
                    x["px"] = [round(v, 1) for v in bx]
                    x["b"] = px_to_b(bx, W, H)
                    x["word_span"] = (k - n, k)
            self.word_boxed += 1
        for ans in answers:
            for o in ans.get("_ornaments") or []:
                self.take_ornament(o, words)

    def take_ornament(self, o, words):
        base = o["line"]
        L = self.lines.get(base)
        if L is None:
            return
        w = o["word"]                                        # 1-based in Azure's text of the base line
        target, local = base, w
        if L.get("split"):
            for x in self.lines.values():
                if x.get("split_of") == base and x.get("word_span") and x["word_span"][0] < w <= x["word_span"][1]:
                    target, local = x["id"], w - x["word_span"][0]
                    break
            else:
                return
        T = self.lines[target]
        toks = T["text"].split()
        if not (1 <= local <= len(toks) and toks[local - 1] == o["text"]):
            near = [k + 1 for k, t in enumerate(toks) if t == o["text"]]
            if not near:
                return
            local = min(near, key=lambda k: abs(k - local))
        ws = words(base)
        wbox = ws[w - 1]["box"] if len(ws) == len(L["text"].split()) and w <= len(ws) else None
        T.setdefault("azure_text", T["text"])
        T["text"] = " ".join(toks[:local - 1] + toks[local:])
        if wbox:
            T.setdefault("orn_boxes", []).append(wbox)
            rest = [x["box"] for x in ws if x["box"] not in T["orn_boxes"]]
            if T.get("word_span"):
                a0, a1 = T["word_span"]
                rest = [x["box"] for x in ws[a0:a1] if x["box"] not in T["orn_boxes"]]
            if rest:
                T["px"] = [round(v, 1) for v in ST.union(rest)]
                T["b"] = px_to_b(T["px"], *self.dims[T["page"]])
        self.ornaments.append(dict(id=f"{base}o{w}", base=base, at=target, page=T["page"], text=o["text"],
                                   px=[round(v, 1) for v in wbox] if wbox else None, source=o.get("source")))


class Master43(M.Master):
    def __init__(self, a, cap):
        for rec in cap["blocks"]:
            if rec["type"] == "other_article":
                rec["type"], rec["_other"] = "header", True
        super().__init__(a, cap)

    def tb(self, p, bid, role, ids, target=None, lang=None, seq=None, own=True):
        if role in ("pageHeader", "pageFooter", "pageNumber") and seq is None and \
                0 <= self.seq < len(self.recs) and self.recs[self.seq].get("_other"):
            role = "otherArticle"
            self.stats["other_article_lines"] += len(ids)
        return super().tb(p, bid, role, ids, target, lang, seq, own)

    def az_words(self, L):
        ws = super().az_words(L)
        ob = L.get("orn_boxes")
        if ob:
            ws = [w for w in ws if w["box"] not in ob]
        return ws

    def add_ornaments(self):
        seq_of_line = {}
        for k, rec in enumerate(self.recs):
            for i in rec.get("ids") or []:
                seq_of_line[i] = k
        for o in getattr(self.S, "ornaments", []):
            if not o["px"]:
                continue
            W, H = self.S.dims[o["page"]]
            self.S.lines[o["id"]] = dict(id=o["id"], page=o["page"], text=o["text"], px=o["px"],
                                         b=px_to_b(o["px"], W, H), split_of=o["base"])
            self.seq = seq_of_line.get(o["at"], 10 ** 9 - 1)
            self.tb(o["page"], self.bid(o["page"]), "ornament", [o["id"]], seq=self.seq, own=False)
            self.stats["ornaments_alto"] += 1

    def alto_xml(self):
        A = super().alto_xml()
        ns = M.ALTO
        T = A.find(f"{{{ns}}}Tags")
        first_other = T.find(f"{{{ns}}}OtherTag")
        for r, d in (("otherArticle", "text of a different article printed on a page this article shares "
                                      "(experiment 43, prompt v2 other_article): not in the JATS"),
                     ("ornament", "a decorative mark Azure read as a word (between the halves of a verse): left out "
                                  "of the text, its ink kept here")):
            el = etree.Element(f"{{{ns}}}StructureTag", {"ID": f"role.{r}", "TYPE": "paragraph-role", "LABEL": r,
                                                         "DESCRIPTION": d})
            first_other.addprevious(el)
        return A


def verse_calls(a, raw_dir: Path) -> dict:
    out = {}
    for x, y in ST.chunks(a):
        rf = raw_dir / f"{a['stem']}_c{x:03d}-{y:03d}.json"
        if not rf.exists():
            continue
        for pg in (ST.jl(rf).get("answer") or {}).get("pages") or []:
            for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
                if isinstance(b, dict) and b.get("type") == "verse":
                    for c in b.get("calls") or []:
                        if isinstance(c, dict):
                            out.setdefault(str(c.get("line")), []).append(dict(c))
    return out


def capture43(a: dict, raw_dir: Path, rules: bool = True) -> dict | None:
    """reader.capture on the answers in raw_dir (experiment 41's raw file format)."""
    cap = {}
    R.VERSE_CALLS.clear()
    R.VERSE_CALLS.update(verse_calls(a, raw_dir))
    real = ST.OUT, ST.raw_file, ST.article_view, ST.Store
    with tempfile.TemporaryDirectory() as td:
        ST.OUT = Path(td)
        ST.raw_file = lambda run, stem, x, y: raw_dir / f"{stem}_c{x:03d}-{y:03d}.json"
        ST.article_view = lambda meta, blocks, pages: cap.update(meta=meta, blocks=blocks, pages=pages) or ""
        if rules:
            ST.Store = Store43
        try:
            book = ST.assemble("argon", a)
        finally:
            ST.OUT, ST.raw_file, ST.article_view, ST.Store = real
    if not book:
        return None
    cap["book"] = book
    cap["S"] = R._LAST[0]
    return cap


def build43(a: dict, raw_dir: Path, mast: Path, rules: bool = True) -> dict:
    cap = capture43(a, raw_dir, rules)
    if cap is None:
        return dict(stem=a["stem"], error="no answers")
    real_mast = M.MAST
    M.MAST = mast
    try:
        Mo = (Master43 if rules else M.Master)(a, cap)
        mast.mkdir(parents=True, exist_ok=True)
        if Mo.crops.exists():
            shutil.rmtree(Mo.crops)
        art = Mo.build()
        if rules:
            Mo.add_ornaments()
        alto = Mo.alto_xml()
    finally:
        M.MAST = real_mast
    doctype = ('<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with '
               'MathML3 v1.4 20241031//EN" "JATS-archivearticle1-4-mathml3.dtd">')
    (mast / f"{a['stem']}.jats.xml").write_bytes(etree.tostring(art, xml_declaration=True, encoding="UTF-8",
                                                                pretty_print=True, doctype=doctype))
    alto_b = etree.tostring(alto, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    if rules:   # the processing note names this experiment
        alto_b = alto_b.replace(b"experiments/41_azure_structure/masters.py",
                                b"experiments/43_rehearsal/masters43.py (on experiments/41_azure_structure/masters.py)")
    (mast / f"{a['stem']}.alto.xml").write_bytes(alto_b)
    pdf = mast / f"{a['stem']}.pdf"
    src = M.NOUT / a["stem"] / f"{a['stem']}.pdf"
    if not src.exists():
        src = M.NIN / a["stem"] / f"{a['stem']}.pdf"
    if pdf.exists() or pdf.is_symlink():
        pdf.unlink()
    os.symlink(os.path.relpath(src.resolve(), mast), pdf)
    r = dict(stem=a["stem"], pages=len(Mo.pages), blocks=len(Mo.recs), **Mo.stats)
    if rules:
        r["split_lines_word_boxed"] = getattr(cap["S"], "word_boxed", 0)
        r["ornaments"] = len(getattr(cap["S"], "ornaments", []))
    (mast / "stats").mkdir(parents=True, exist_ok=True)
    (mast / "stats" / f"{a['stem']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r
