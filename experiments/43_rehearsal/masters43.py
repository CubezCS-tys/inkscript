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
import rechunk43  # noqa: E402
rechunk43.install(ST)                 # chunks re-cut after a MAX_TOKENS failure (out/rechunk43.json)
import reader as R  # noqa: E402
import masters as M  # noqa: E402
from lxml import etree  # noqa: E402
import numpy as np  # noqa: E402

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
                ws.append(dict(text=w["content"], box=[min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s],
                               conf=w.get("confidence")))
            cache[lid] = ws
        return cache[lid]

    def ink(p, mask):
        """rules43.pictures: dark regions of page p that no box in mask (0-1000) accounts for (ink43)."""
        import ink43
        return ink43.blobs(ST.page_image(a, p), mask)
    def dark(p, box):
        import ink43
        return ink43.dark_share(ST.page_image(a, p), box)
    words.ink = ink
    words.dark = dark
    words.image = lambda p: ST.page_image(a, p)          # rules43.guillemets: the page render (300 dpi)
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
        self.picture_junk = set()
        for ans in answers:
            for o in ans.get("_ornaments") or []:
                self.take_ornament(o, words)
            self.picture_junk.update(str(i) for i in ans.get("_picture_junk") or [])
        self.show_through = {str(i) for ans in answers for i in ans.get("_show_through") or []}

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
        gap = None
        if wbox and o.get("picture"):                  # the picture fills the gap between its real neighbours
            others = [x["box"] for j, x in enumerate(ws) if j != w - 1 and x["box"] not in T.get("orn_boxes", [])]
            c = (wbox[0] + wbox[2]) / 2
            lh = (T["px"][3] - T["px"][1]) or (wbox[3] - wbox[1])
            left = max([b[2] for b in others if b[2] <= c] or [wbox[0] - 2 * lh])
            right = min([b[0] for b in others if b[0] >= c] or [wbox[2] + 2 * lh])
            x0, x1 = max(left + 0.1 * lh, wbox[0] - 3 * lh), min(right - 0.1 * lh, wbox[2] + 3 * lh)
            x0, x1 = min(x0, wbox[0]), max(x1, wbox[2])
            gap = [round(x0, 1), round(min(wbox[1], T["px"][1]) - 0.25 * lh, 1), round(x1, 1),
                   round(max(wbox[3], T["px"][3]) + 0.25 * lh, 1)]
        self.ornaments.append(dict(id=f"{base}o{w}", base=base, at=target, page=T["page"], text=o["text"],
                                   px=[round(v, 1) for v in wbox] if wbox else None, source=o.get("source"),
                                   picture=bool(o.get("picture")), k=local - 1, pic_px=gap))


# ------------------------------------------------------------------------------------------------ MathML names
NAME_RUN = re.compile(r"(?:(?<=\\ln )|(?<=\\log )|(?<=\\Delta )|(?<![\\A-Za-z{]))([A-Z]{3,})(?=_|\s*\))"
                      r"|(?:(?<=\\ln )|(?<=\\log )|(?<=\\Delta ))([A-Z]{3,})(?![A-Za-z])")
FUNC = re.compile(r"(?<![\\A-Za-z])(ln|log|exp|sin|cos|tan|max|min|lim|det)(?![A-Za-z])")
_MATHML41 = M.mathml


def latex_names(latex: str) -> str:
    r"""Multi-letter names written plain in the LaTeX: a run of 3+ capitals with a subscript or under \ln / \log /
    \Delta becomes \mathrm{...} (one name: END_{it}, \ln EGR in 2382's regressions); a plain ln / log / sin ...
    becomes the function. Other capital runs are products of matrices (VRV', IWX in 1147) and stay letters;
    so do two capitals (VX, AT) and lower-case runs (xy)."""
    latex = FUNC.sub(lambda m: "\\" + m.group(1) + " ", latex)
    return NAME_RUN.sub(lambda m: "\\mathrm{" + (m.group(1) or m.group(2)) + "}", latex)


def mathml43(parent, latex: str, display: str):
    """experiment 41's latex2mathml conversion, with multi-letter names as one <mml:mi> (fix 5a)."""
    m = _MATHML41(parent, latex_names(latex), display)
    if m is None:
        return None
    MI = f"{{{M.MML}}}mi"
    for row in list(m.iter()):
        kids = list(row)
        k = 0
        while k < len(kids):
            e = kids[k]
            if e.tag == MI and e.get("mathvariant") == "normal" and len(e.text or "") == 1:
                j = k
                while j + 1 < len(kids) and kids[j + 1].tag == MI and kids[j + 1].get("mathvariant") == "normal" \
                        and len(kids[j + 1].text or "") == 1 and not (kids[j].tail or "").strip():
                    j += 1
                if j > k:
                    e.text = "".join(x.text for x in kids[k:j + 1])
                    del e.attrib["mathvariant"]
                    e.tail = kids[j].tail
                    for x in kids[k + 1:j + 1]:
                        row.remove(x)
                    MATH_STATS["mi_merged"] += 1
                k = j + 1
            else:
                k += 1
    # an mrow holding one element is that element
    return m


from collections import Counter as _Counter  # noqa: E402
MATH_STATS = _Counter()
M.mathml = mathml43


def insert_after_words(t, k, el):
    """Put el into the text of the printed line that target t starts, after its first k words (an element inside
    the line, e.g. a fix or a note call, counts as its words and is never cut)."""
    node, text = t, t.tail or ""
    count = 0
    while True:
        toks = list(re.finditer(r"\S+", text))
        if count + len(toks) >= k and k > count:
            cut = toks[k - count - 1].end()
            node.tail, el.tail = text[:cut] + " ", text[cut:]
            node.addnext(el)
            return
        if k <= count:                                   # before this text run
            node.tail = ""
            el.tail = (" " + text.lstrip()) if text.strip() else text
            node.addnext(el)
            return
        count += len(toks)
        nxt = node.getnext()
        if nxt is None or (isinstance(nxt.tag, str) and nxt.tag == "target"):
            node.addnext(el)                             # the end of the line
            el.tail = " "
            return
        count += len(" ".join(nxt.itertext()).split())
        node, text = nxt, nxt.tail or ""
        if count >= k:
            el.tail = text
            nxt.tail = " "
            nxt.addnext(el)
            return


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
        self.pending_inline = []
        A = super().build()
        self.put_inline(A)
        A = J.fill_slots(self, A)
        import meta43                                  # D33: metadata corrected, printed kept, changes logged
        meta43.apply(self, A)
        return A

    def tb(self, p, bid, role, ids, target=None, lang=None, seq=None, own=True):
        if role in ("pageHeader", "pageFooter", "pageNumber") and seq is None and \
                0 <= self.seq < len(self.recs) and self.recs[self.seq].get("_other"):
            role = "otherArticle"
            self.stats["other_article_lines"] += len(ids)
        if role == "noise" and ids and all(i in getattr(self.S, "picture_junk", ()) for i in ids):
            role = "pictureJunk"                    # rules43.pictures: Azure's reading of a picture's ink
            self.stats["picture_junk_lines"] += len(ids)
        elif role == "noise" and ids and all(i in getattr(self.S, "show_through", ()) for i in ids):
            role = "showThrough"                    # rules43.show_through: pale ink, not this page's print
            self.stats["show_through_lines"] += len(ids)
        return super().tb(p, bid, role, ids, target, lang, seq, own)

    def other_figure(self, rec, cap_rec):
        """A picture of another article (rules43.pictures: level "other"): not in this article's JATS; its crop and
        an ALTO Illustration tagged role.otherArticle (FILEID = the crop) so the Layout view draws it, muted with
        the other article's text; its caption and words as otherArticle text."""
        p = rec["page"]
        W, H = self.S.dims[p]
        x0, y0, x1, y1 = rec["fig_box"]
        box = [min(x0, x1) * W / 1000, min(y0, y1) * H / 1000, max(x0, x1) * W / 1000, max(y0, y1) * H / 1000]
        fid = self.kid(p, "f")
        g = self.crop(p, box, f"{fid}.jpg", rel_pad=True)
        self.alto[self.lp(p)].append(dict(kind="ill", id=fid, type="figure", box=box, target=None, seq=self.seq,
                                          role="otherArticle", file=g))
        if cap_rec is not None and cap_rec.get("ids"):
            M.Master.tb(self, p, self.bid(p), "otherArticle", cap_rec["ids"])
        if rec.get("ids"):                         # words printed in the picture: the picture shows them
            M.Master.tb(self, p, self.bid(p), "pictureText", rec["ids"])
        self.stats["figures_other_article"] += 1

    def fill(self, el, ids, sep_first=False, tbid=None, of=None):
        """experiment 41's fill (one space between lines); a Latin word cut at a line end with a hyphen
        (rules43.latin_join) is joined: no space, the hyphen out (kept for a compound, «well-known»). The line break
        stays (the target), and the ALTO keeps the printed line with its hyphen (2026-10-20, 2483 / 0310)."""
        import rules43 as RU
        of = of if of is not None else ids
        if el.text is None and not len(el):
            el.text = ""
        for k, lid in enumerate(ids):
            if k or sep_first:
                how = RU.latin_join(self.S.lines[ids[k - 1]]["text"], self.S.lines[lid]["text"]) if k else None
                tail = (el[-1].tail if len(el) else el.text) or ""
                if how and tail.rstrip().endswith(("-", "‐", "‑")):
                    t = tail.rstrip()
                    t = t[:-1] if how == "join" else t
                    if len(el):
                        el[-1].tail = t
                    else:
                        el.text = t
                    self.stats["latin_hyphen_" + how] += 1
                else:
                    M.add_text(el, " ")
            if tbid and self.S.lines[lid]["text"].split():
                M.sub(el, "target", {"id": f"{tbid}l{of.index(lid) + 1}"})
            self.put_runs(el, self.runs(lid))

    def crop(self, p, box_px, name, rel_pad=False) -> str | None:
        """experiment 41's crop; a picture's crop (rel_pad) has the page's own text lines that run into it painted
        out (paper colour), so the view does not draw the printed words twice (2026-10-20, 0729 p2: the drawing's
        box over the ends of three verse lines, «المتاجر ،» drawn from the scan inside the picture). Lines of the
        picture itself (its words) stay."""
        if not rel_pad:
            return super().crop(p, box_px, name, rel_pad)
        import cv2
        img = cv2.imread(str(ST.page_image(self.a, p)), cv2.IMREAD_COLOR)
        if img is None:
            return None
        H, W = img.shape[:2]
        x0, y0, x1, y1 = box_px
        px, py = 4 * W / 1000, 4 * H / 1000
        x0, y0 = max(0, int(x0 - px)), max(0, int(y0 - py))
        x1, y1 = min(W, int(x1 + px)), min(H, int(y1 + py))
        c = img[y0:y1, x0:x1].copy()
        if c.size == 0 or c.shape[0] < 6 or c.shape[1] < 6:
            return None
        own = set()
        for r in self.recs:
            if r.get("type") == "figure" and r.get("page") == p:
                own.update(r.get("ids") or [])
        paper = None
        n = 0
        for r in self.recs:
            if r.get("page") != p or r.get("type") in ("figure",):
                continue
            for i in r.get("ids") or []:
                L = self.S.lines.get(i)
                if i in own or not L or not L.get("px") or not L["text"].split():
                    continue
                a0, b0, a1, b1 = L["px"]
                if a1 <= x0 or a0 >= x1 or b1 <= y0 or b0 >= y1 or (y1 - y0) < 4 * (b1 - b0):
                    continue                     # not in the crop; or a picture inside a printed line (its row)
                if paper is None:
                    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
                    sel = c[g >= np.percentile(g, 60)]
                    paper = [int(v) for v in np.median(sel, axis=0)] if len(sel) else [255, 255, 255]
                h = b1 - b0
                cv2.rectangle(c, (int(a0 - x0 - 0.15 * h), int(b0 - y0 - 0.1 * h)),
                              (int(a1 - x0 + 0.15 * h), int(b1 - y0 + 0.1 * h)), paper, -1)
                n += 1
        if n:
            self.stats["picture_text_painted_out"] += n
        if c.shape[1] > 1600:
            c = cv2.resize(c, (1600, int(c.shape[0] * 1600 / c.shape[1])), interpolation=cv2.INTER_AREA)
        self.crops.mkdir(parents=True, exist_ok=True)
        if R._colourless(c):
            c = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
        (self.crops / name).write_bytes(cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes())
        return f"{self.stem}.crops/{name}"

    def table(self, rec, parent, cap_rec, caption_into):
        """experiment 41's table; then a table printed in two columns (rules43.table_parts) is drawn as one ALTO
        block per part (one JATS table-wrap; the later parts point at it and are tagged flow.continued)."""
        al = self.alto[self.lp(rec["page"])]
        n = len(al)
        super().table(rec, parent, cap_rec, caption_into)
        n = next((k for k in range(n, len(al)) if al[k].get("kind") == "table"), None)
        if n is None:
            return
        import rules43 as RU
        L = self.S.lines
        rbs = [ST.union([L[i]["px"] for c in r for i in c.get("ids") or [] if i in L]) for r in rec.get("rows") or []]
        parts = RU.table_parts(rbs)
        if len(parts) < 2:
            return
        T, at = al.pop(n), n
        for k, rows in enumerate(parts):
            ids = {i for ri in rows for c in rec["rows"][ri] for i in c.get("ids") or []}
            cells = [c for c in T["cells"] if set(c["ids"]) & ids]
            box = ST.union([L[i]["px"] for i in ids if i in L])
            if not box:
                continue
            al.insert(at, dict(T, id=T["id"] if k == 0 else f"{T['id']}p{k + 1}", box=box, cells=cells, part=k))
            at += 1
        self.stats["tables_in_columns"] += 1

    def alto_block(self, parent, b, lp, q):
        if b.get("kind") == "table" and b.get("part"):          # a later part of a table printed in two columns
            super().alto_block(parent, b, lp, q)
            parent[-1].set("TAGREFS", "flow.continued")
            return
        if b.get("kind") == "ill" and (b.get("role") or b.get("file")):
            el = M.sub(parent, q("Illustration"), {"ID": b["id"], "TYPE": b["type"]})
            for k, v in zip(("HPOS", "VPOS", "WIDTH", "HEIGHT"),
                            (b["box"][0], b["box"][1], b["box"][2] - b["box"][0], b["box"][3] - b["box"][1])):
                el.set(k, f"{max(0.0, v):.1f}".removesuffix(".0"))
            if b.get("file"):
                el.set("FILEID", b["file"])
            if b.get("role"):
                el.set("TAGREFS", f"role.{b['role']}")
            return
        return super().alto_block(parent, b, lp, q)

    def figure(self, rec, parent, cap_rec, caption_into):
        """experiment 41's fig, then the words printed inside the picture (rules43 text_in_figure, or Argon's
        figure "lines") as the figure's own text: <p content-type="text-in-figure"> after the graphic (JATS allows
        paragraphs in fig after caption / alt-text / graphic). In the ALTO they stay role.pictureText (41).
        rules43.pictures: a picture of another article goes to other_figure; a picture found from the ink is a fig
        with specific-use="ink-without-text" (fig-type="decoration" when small and wordless)."""
        lv = str(rec.get("level") or "")
        if "other" in lv.split():
            return self.other_figure(rec, cap_rec)
        if cap_rec is None and self.inline_figure(rec):
            return
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
        if "ink" in lv.split() and len(figs) > n0:
            figs[-1].set("specific-use", "ink-without-text")
            if "decoration" in lv.split():
                figs[-1].set("fig-type", "decoration")
            self.stats["figures_from_ink"] += 1
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

    # ---------------------------------------------------------------- pictures inside a printed line (fix 3)
    INLINE_TYPES = {"paragraph", "list_item", "quote", "footnote", "heading", "abstract", "reference", "boxed",
                    "keywords"}

    def inline_place(self, p, box):
        """(line id, words before the picture) when a picture sits inside a printed row of running text: no taller
        than ~3 of the row's lines, overlapping the row vertically by half, with the row's words beside it or
        round it (1769 p5: hieroglyph groups inside a sentence). None otherwise."""
        kind = {}
        for r in self.recs:
            if r["type"] in self.INLINE_TYPES and r["page"] == p:
                for i in r.get("ids") or []:
                    kind[i] = r["type"]
        fh = box[3] - box[1]
        cand = []
        for i in kind:
            L = self.S.lines.get(i)
            if not L or not L["text"].split():
                continue
            lb = L["px"]
            lh = lb[3] - lb[1]
            vo = min(lb[3], box[3]) - max(lb[1], box[1])
            if lh <= 0 or vo < 0.5 * min(lh, fh) or fh > 3.2 * lh:
                continue
            hgap = max(box[0] - lb[2], lb[0] - box[2], 0)
            if hgap > 3 * lh:
                continue
            cand.append((hgap, i, lb))
        if not cand:
            return None
        straddle = [c for c in cand if c[0] == 0 and c[2][0] < box[0] and c[2][2] > box[2]]
        rtl = self.lang == "ar"
        cx = (box[0] + box[2]) / 2
        if straddle:
            _, i, lb = straddle[0]
            ws = self.az_words(self.S.lines[i]) if hasattr(self, "az_words") else []
            n = len(self.S.lines[i]["text"].split())
            if ws and len(ws) == n:
                k = sum(1 for w in ws if ((w["box"][0] + w["box"][2]) / 2 > cx) == rtl)
            else:
                k = round(n * ((lb[2] - cx) if rtl else (cx - lb[0])) / max(1, lb[2] - lb[0]))
            return i, k
        before = [c for c in cand if ((c[2][0] + c[2][2]) / 2 > cx) == rtl]       # the text that comes first
        if before:
            _, i, _ = min(before, key=lambda c: c[0])
            return i, len(self.S.lines[i]["text"].split())
        _, i, _ = min(cand, key=lambda c: c[0])
        return i, 0

    def inline_figure(self, rec, box=None, place=None, desc=None) -> bool:
        """A picture inside a printed line: an <inline-graphic> at its place in the paragraph's text (put in after
        the article is built, put_inline), its crop, an ALTO Illustration pointing at it."""
        p = rec["page"]
        W, H = self.S.dims[p]
        if box is None:
            x0, y0, x1, y1 = rec["fig_box"]
            box = [min(x0, x1) * W / 1000, min(y0, y1) * H / 1000, max(x0, x1) * W / 1000, max(y0, y1) * H / 1000]
        place = place or self.inline_place(p, box)
        if place is None:
            return False
        fid = self.kid(p, "f")
        g = self.crop(p, box, f"{fid}.jpg", rel_pad=True)
        if not g:
            return False
        el = etree.Element("inline-graphic", {"id": fid, f"{{{M.XL}}}href": g, "specific-use": "picture-in-line"})
        d = desc if desc is not None else rec.get("description")
        if isinstance(d, dict):
            d = d.get(self.lang) or next(iter(d.values()), None)
        if isinstance(d, str) and d.strip():
            etree.SubElement(el, "alt-text").text = d.strip()
        self.pending_inline.append((place[0], place[1], el))
        self.alto[self.lp(p)].append(dict(kind="ill", id=fid, type="figure", box=box, target=fid,
                                          seq=self.seq if rec.get("_seq") is None else rec["_seq"]))
        if rec.get("ids"):
            self.tb(p, self.bid(p), "pictureText", rec["ids"])
        self.stats["inline_pictures"] += 1
        return True

    def tight_picture(self, p, win, seed):
        """The ink of a picture Azure read as a junk word: inside the search window (the gap between the line's real
        words, the row's height and a little more), the dark pixels outside every real word's box, joined; the
        pieces touching the junk word's box (seed) give the picture's box. The window itself if no ink is found."""
        import cv2
        import numpy as np
        import ink43
        d0 = ink43._dark(str(ST.page_image(self.a, p)))
        if d0 is None:
            return win
        k = ink43.SCALE
        d = d0.copy()
        for L in self.S.lines.values():
            if L["page"] != p or L.get("split") or not L["text"].split():
                continue
            for w in self.az_words(L):
                b = w["box"]
                if b[2] < win[0] or b[0] > win[2] or b[3] < win[1] or b[1] > win[3]:
                    continue
                ib = [max(b[0], seed[0]), max(b[1], seed[1]), min(b[2], seed[2]), min(b[3], seed[3])]
                if ib[2] > ib[0] and ib[3] > ib[1] and \
                        (ib[2] - ib[0]) * (ib[3] - ib[1]) > 0.5 * max(1, (b[2] - b[0]) * (b[3] - b[1])):
                    continue                             # the junk word itself (its ink is the picture)
                d[int(b[1] // k):int(b[3] // k) + 1, int(b[0] // k):int(b[2] // k) + 1] = 0
        x0, y0 = max(0, int(win[0] // k)), max(0, int(win[1] // k))
        x1, y1 = min(d.shape[1], int(win[2] // k) + 1), min(d.shape[0], int(win[3] // k) + 1)
        sub_ = d[y0:y1, x0:x1]
        if sub_.size == 0 or not sub_.any():
            return win
        lh = max(3, int((seed[3] - seed[1]) / k))
        j = cv2.morphologyEx(sub_, cv2.MORPH_CLOSE, np.ones((3, max(3, int(0.8 * lh))), np.uint8))   # signs of a group
        n, lab, st, _ = cv2.connectedComponentsWithStats(j, 8)
        sx0, sy0, sx1, sy1 = (seed[0] // k - x0, seed[1] // k - y0, seed[2] // k - x0, seed[3] // k - y0)
        keep = []
        for c in range(1, n):
            cx, cy, cw, ch, ca = st[c]
            if ca < 4:
                continue
            if cx <= sx1 + 3 and cx + cw >= sx0 - 3 and cy <= sy1 + 3 and cy + ch >= sy0 - 3:
                keep.append((cx, cy, cx + cw, cy + ch))
        if not keep:
            return win
        bx = [min(b[0] for b in keep), min(b[1] for b in keep), max(b[2] for b in keep), max(b[3] for b in keep)]
        self.stats["picture_boxes_from_ink"] += 1
        return [round((bx[0] + x0) * k, 1), round((bx[1] + y0) * k, 1), round((bx[2] + x0) * k, 1),
                round((bx[3] + y0) * k, 1)]

    def picture_fig(self, p, box):
        """A picture (v3.1 picture ornament) on a line of its own: a fig after the block printed just above it."""
        above = [(L["px"][3], L["id"]) for L in self.S.lines.values() if L["page"] == p and L["px"][3] <= box[1] + 5
                 and L["id"] in self.tl_of and L["text"].split()]
        tg = {t.get("id"): t for t in self.A.iter("target")}
        anchor = None
        for _, lid in sorted(above, reverse=True):
            t = tg.get(self.tl_of[lid])
            if t is not None:
                anchor = t
                break
        while anchor is not None and anchor.getparent() is not None and \
                anchor.getparent().tag not in ("body", "sec", "boxed-text"):
            anchor = anchor.getparent()
        fid = self.kid(p, "f")
        g = self.crop(p, box, f"{fid}.jpg", rel_pad=True)
        if not g or anchor is None or anchor.getparent() is None:
            self.stats["picture_ornaments_lost"] += 1
            return
        fig = etree.Element("fig", {"id": fid, "specific-use": "ink-without-text"})
        etree.SubElement(fig, "graphic", {f"{{{M.XL}}}href": g})
        anchor.addnext(fig)
        self.alto[self.lp(p)].append(dict(kind="ill", id=fid, type="figure", box=box, target=fid, seq=self.seq))
        self.stats["figures_from_picture_ornaments"] += 1

    def put_inline(self, A):
        """Each pending inline picture into its line's text, after the words that come before it."""
        tg = {t.get("id"): t for t in A.iter("target")}
        for lid, k, el in self.pending_inline:
            t = tg.get(self.tl_of.get(lid))
            if t is None:
                self.stats["inline_pictures_unplaced"] += 1
                continue
            insert_after_words(t, k, el)
            self.stats["inline_pictures_placed"] += 1
        self.pending_inline = []

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
            self.tb(o["page"], self.bid(o["page"]), "pictureJunk" if o.get("picture") else "ornament", [o["id"]],
                    seq=self.seq, own=False)
            self.stats["ornaments_alto"] += 1
        # v3.1 picture ornaments: the picture itself, inline at its place (consecutive junk words: one picture)
        groups = []
        for o in sorted((o for o in getattr(self.S, "ornaments", []) if o.get("picture") and o.get("pic_px")),
                        key=lambda o: (o["at"], o["k"])):
            g = groups[-1] if groups else None
            if g and g["at"] == o["at"] and o["k"] <= g["k"] + 1:
                g["box"] = ST.union([g["box"], o["pic_px"]])
                g["seed"] = ST.union([g["seed"], o["px"]])
                continue
            groups.append(dict(at=o["at"], k=o["k"], page=o["page"], box=list(o["pic_px"]), seed=list(o["px"])))
        for g in groups:
            g["box"] = self.tight_picture(g["page"], g["box"], g["seed"])
            self.seq = seq_of_line.get(g["at"], 10 ** 9 - 1)
            in_text = g["at"] in seq_of_line and self.S.lines[g["at"]]["text"].split()
            rec = dict(page=g["page"], ids=[])
            if self.inline_figure(rec, box=g["box"], place=(g["at"], g["k"]) if in_text else None, desc=""):
                self.stats["inline_pictures_from_ornaments"] += 1
            else:                                        # a line that was only the picture: a figure of its own
                self.picture_fig(g["page"], g["box"])
        if self.pending_inline:
            self.put_inline(self.A)

    def alto_xml(self):
        A = super().alto_xml()
        ns = M.ALTO
        T = A.find(f"{{{ns}}}Tags")
        first_other = T.find(f"{{{ns}}}OtherTag")
        for r, d in (("otherArticle", "text of a different article printed on a page this article shares "
                                      "(experiment 43, prompt v2 other_article): not in the JATS"),
                     ("ornament", "a decorative mark Azure read as a word (between the halves of a verse): left out "
                                  "of the text, its ink kept here"),
                     ("pictureJunk", "what Azure read from a picture's ink (hieroglyphs, symbols, a drawing): not text, "
                                     "left out of the JATS; the picture is drawn from the page image (experiment 43, "
                                     "rules43.pictures)"),
                     ("showThrough", "a line Azure read from ink that is not this page's print: the reverse side "
                                     "showing through, a watermark, a faint ghost (pale against the page's text; "
                                     "rules43.show_through, 2026-10-20): left out of the JATS")):
            el = etree.Element(f"{{{ns}}}StructureTag", {"ID": f"role.{r}", "TYPE": "paragraph-role", "LABEL": r,
                                                         "DESCRIPTION": d})
            first_other.addprevious(el)
        return A


# ------------------------------------------------------------------------------------------------ version stamp

CODE_FILES = [HERE / "rules43.py", HERE / "masters43.py", HERE / "ink43.py", HERE / "jats43.py", HERE / "refs43.py", HERE / "meta43.py", E41 / "structure.py", E41 / "reader.py", E41 / "masters.py"]
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
            import refs43                       # v3.2 parsed references / cited works (no-op on older answers)
            refs43.add_parsed(Mo, art, raw_dir)
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
    if rules:                                          # D33 change log (empty list: nothing corrected)
        (mast / f"{a['stem']}.metachanges.json").write_text(json.dumps(
            dict(stem=a["stem"], rule="docs/decisions.md D33", changes=getattr(Mo, "meta_changes", [])),
            ensure_ascii=False, indent=1))
    (mast / "stats").mkdir(parents=True, exist_ok=True)
    (mast / "stats" / f"{a['stem']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r
