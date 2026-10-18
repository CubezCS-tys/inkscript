"""Experiment 43: experiment 41's masters (JATS 1.4 + ALTO 4.4) from answers that went through rules43, with the
code that v2 needs. Experiment 41's modules are imported and extended here; nothing in experiment 41 changes.

  * other_article blocks: kept out of the JATS (the article's text); in the ALTO as TextBlocks role.otherArticle
  * split lines (verse halves Azure read as one line, cut by word): each part's box is the union of its own Azure
    words (experiment 41 cut the line's box in proportion to characters, so the halves ran together)
  * ornaments (rules43): taken out of the text; their ink kept in the ALTO as TextBlocks role.ornament
  * figures with words printed inside them (rules43 text_in_figure): the words go into the fig as
    <p content-type="text-in-figure">; the Layout view draws the picture only, with a "copy text" button
  * lines put back by the never-noise rule are ordinary block lines (blocks of type "other" for runs)

    capture43(a, raw_dir, rules=True)  -> experiment 41's capture (structure.assemble on the answers in raw_dir)
    build43(a, raw_dir, mast_dir, rules=True) -> writes <mast_dir>/<stem>.jats.xml, .alto.xml, crops, stats
With rules=False the answers and code are exactly experiment 41's (the harness check: same masters as 41's).

Version stamp (rules=True only): every master says which prompt (name + hash of its text), which code (hash of
rules43.py, masters43.py and experiment 41's structure/reader/masters.py), which model and run made it, and when:
JATS custom-meta "stamp-*" and a sidecar <stem>.stamp.json. versions() gives the current ones; strip_stamp() takes
the stamp out of JATS bytes (byte comparisons with experiment 41).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
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
ST.COARSE.setdefault("trans_title", "heading")     # v3: a printed translated title (rules43 from "translated": true)
ST.COARSE.setdefault("boxed", "body")              # v3: text in a frame or tinted box (JATS boxed-text)
M.ROLE.setdefault("trans_title", "title")
import jats43 as J  # noqa: E402
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
        J.retype_trans_title(self)

    def build(self):
        """experiment 41's article, then the JATS slots it left empty (jats43: abstracts, keywords, translated title,
        history dates, affiliation parts, boxed text, endnotes, acknowledgements / appendices)."""
        return J.fill_slots(self, super().build())

    def tb(self, p, bid, role, ids, target=None, lang=None, seq=None, own=True):
        if role in ("pageHeader", "pageFooter", "pageNumber") and seq is None and \
                0 <= self.seq < len(self.recs) and self.recs[self.seq].get("_other"):
            role = "otherArticle"
            self.stats["other_article_lines"] += len(ids)
        return super().tb(p, bid, role, ids, target, lang, seq, own)

    def figure(self, rec, parent, cap_rec, caption_into):
        """experiment 41's fig, then the words printed inside the picture (rules43 text_in_figure, or Argon's
        figure "lines") as the figure's own text: <p content-type="text-in-figure"> after the graphic (JATS allows
        paragraphs in fig after caption / alt-text / graphic). In the ALTO they stay role.pictureText (41)."""
        n0 = len(parent.findall("fig"))
        desc = rec.get("description")
        both = {}
        if isinstance(desc, str) and desc.startswith("{"):     # v3 via rules43: {"ar": ..., "en": ...} as JSON
            try:
                desc = json.loads(desc)
            except ValueError:
                pass
        if isinstance(desc, dict):        # v3: {"ar": ..., "en": ...}; the article's language first
            both = {str(k): v.strip() for k, v in desc.items() if isinstance(v, str) and v.strip()}
            rec = dict(rec, description=both.get(self.lang) or next(iter(both.values()), None))
        super().figure(rec, parent, cap_rec, caption_into)
        figs = parent.findall("fig")
        if len(figs) > n0:
            alt = figs[-1].find("alt-text")
            if alt is not None:
                first = next((k for k, v in both.items() if v == alt.text), None) or M.lang_of(alt.text or "")
                if first != self.lang:
                    alt.set(M.XML_LANG, first)
                for k, v in both.items():
                    if k != first:
                        e = etree.Element("alt-text", {M.XML_LANG: k} if k != self.lang else {})
                        e.text = v
                        alt.addnext(e)
                        self.stats["figure_alt_text_second_language"] += 1
                self.stats[f"figure_alt_text_{first}_first"] += 1
        ids = [i for i in rec.get("ids") or [] if self.S.lines[i]["text"].split()]
        figs = parent.findall("fig")
        if not ids or len(figs) <= n0:
            return
        fig = figs[-1]
        t = self.text(ids)
        p = M.sub(fig, "p", {"content-type": "text-in-figure"})
        lg = M.lang_of(t, rec.get("lang")) if hasattr(M, "lang_of") else None
        if lg and lg != self.lang:
            p.set(M.XML_LANG, lg)
        self.fill(p, ids)
        self.stats["figure_text_blocks"] += 1

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


# ------------------------------------------------------------------------------------------------ version stamp

CODE_FILES = [HERE / "rules43.py", HERE / "masters43.py", E41 / "structure.py", E41 / "reader.py", E41 / "masters.py"]
RAW41 = E41 / "out" / "argon" / "raw"
DEFAULT_MODEL = "gemini-4-argon"


def _h(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()[:10]


def prompt_text(name: str) -> str | None:
    if name == "v1":
        return ST.PROMPT
    import prompt43 as P
    return P.PROMPTS[name][0] if name in P.PROMPTS else None


def versions(prompt: str = "v2") -> dict:
    """The current prompt (name + hash of its text) and code (hash of the rule and masters sources)."""
    t = prompt_text(prompt)
    return dict(prompt=prompt, prompt_hash=_h(t.encode()) if t else None,
                rules_hash=_h(b"".join(f.read_bytes() for f in CODE_FILES)))


def run_name(raw_dir: Path) -> str:
    raw_dir = Path(raw_dir).resolve()
    if raw_dir == RAW41.resolve():
        return "41-argon"
    if raw_dir == (OUT / "replay" / "raw").resolve():
        return "replay (41-argon answers)"
    return raw_dir.parent.name if raw_dir.name in ("raw", "rules") else raw_dir.name


def stamp_of(a: dict, raw_dir: Path, run: str | None = None) -> dict:
    """What made this article's masters: prompt and model from the answers (a v1 answer has no "prompt"), code now."""
    prompts, models = set(), set()
    for x, y in ST.chunks(a):
        f = Path(raw_dir) / f"{a['stem']}_c{x:03d}-{y:03d}.json"
        if f.exists():
            r = ST.jl(f)
            prompts.add(r.get("prompt") or "v1")
            models.add(r.get("model") or DEFAULT_MODEL)
    pr = sorted(prompts)[-1] if prompts else "?"
    v = versions(pr)
    return dict(v, prompt="+".join(sorted(prompts)) or "?", model="+".join(sorted(models)) or "?",
                run=run or run_name(raw_dir), made=time.strftime("%Y-%m-%d %H:%M"))


def put_stamp(art, st: dict):
    cmg = art.find(".//article-meta/custom-meta-group")
    if cmg is None:
        return
    for k in ("prompt", "prompt_hash", "rules_hash", "model", "run", "made"):
        c = etree.SubElement(cmg, "custom-meta", {"id": f"stamp-{k.replace('_', '-')}"})
        etree.SubElement(c, "meta-name").text = f"pipeline-{k.replace('_', '-')}"
        etree.SubElement(c, "meta-value").text = str(st.get(k))


STAMP_RE = re.compile(rb'\s*<custom-meta id="stamp-[^"]*">.*?</custom-meta>', re.S)


def strip_stamp(b: bytes) -> bytes:
    return STAMP_RE.sub(b"", b)


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


def build43(a: dict, raw_dir: Path, mast: Path, rules: bool = True, run: str | None = None) -> dict:
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
    st = stamp_of(a, raw_dir, run) if rules else None
    if st:
        put_stamp(art, st)
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
    if st:
        (mast / f"{a['stem']}.stamp.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))
    (mast / "stats").mkdir(parents=True, exist_ok=True)
    (mast / "stats" / f"{a['stem']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r
