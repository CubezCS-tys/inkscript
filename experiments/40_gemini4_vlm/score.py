"""Experiment 40: one scoring harness for every approach's semantic HTML (FORMAT.md).

    /home/yassine/inkscript/.venv/bin/python score.py out/<approach> [out/<approach2> ...] [--prefix a1_]
                                                     [--pages sample|docs|all] [--name NAME]

Reads out/<approach>/<page_id>.html (or out/<approach>/docs/<stem>.html cut by <section class="page">), writes
out/<approach>/score.json (per-page rows + summary) and prints one summary block per approach.
--prefix: the approach's spend-log tag prefix (default: the folder name + "_").

Units scored: the sample's pages (out/sample.json) and, with --pages docs|all, every page of the sample's whole
documents (references for those: Azure's lines from the document's JSON; no Kraken, no referee labels).

Measures, per page then summed (micro) over page groups:
 (a) text: faithful and folded character error rate (CER) of the page's text in the reader's order, scored with
     inkscript's `score_page` exactly as experiment 36 did: vs the TRUTH where there is one (owner's gold pages:
     `cer_gold`; born-digital PDF text, digits folded: `cer_bd`) and vs AZURE on every page (`cer_az`: agreement,
     not accuracy — Azure is a reader too). Equations are not text on either side (FORMAT.md).
 (b) invented / dropped words per 1,000 reference words vs Azure, OUTSIDE TABLES (Azure cell lines, lines the
     referee called table, and lines inside a predicted table's box are left out of the reference; the reader's
     table cells out of the prediction), with experiment 36's word anchoring (evaluate.py: anchors, runs that are
     not misreadings, repetitions apart). `invented` = also unexplained by Kraken's reading where there is one (36's
     rule: Azure misses text Kraken sees); `invented_az` = Azure only. Also vs the truth on truth pages.
 (c) layout: each Azure line of a page with referee labels (experiment 39 out/score_test, Gemini Pro's labels, set:
     body heading footnote verse list references caption table equation furniture other) is mapped to the reader's
     block holding its text (letter-triple containment >= 0.5, best block) -> `layout_text_acc`; and to the block
     whose data-bbox covers most of it (>= 40% of the line) -> `layout_box_acc`; lines the referee called "other"
     are left out (as in 39). `box_hit`: share of text-mapped lines whose centre lies in their block's box.
 (d) reading order: Kendall concordance of the reader's anchored words' reference positions (36's word_order),
     reference = truth where there is one, else Azure; reported over all pages and over multi-column pages.
 (e) cost and seconds per page from out/gemini_spend.jsonl (or <page_id>.meta.json).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import B36, B39, DOCS, GOLD, OUT, SPEND, sample  # noqa: E402

sys.path.insert(0, str(HERE.parents[0] / "36_vlm_bakeoff"))
import evaluate as e36  # noqa: E402  (36's word anchoring and born-digital cleaning; read only)
from inkscript.gold.format import load as gold_load  # noqa: E402
from inkscript.gold.score import eq_sim, score_page, teds  # noqa: E402
from inkscript.gold.text import folded  # noqa: E402

LABELS = ["furniture", "heading", "body", "list", "verse", "footnote", "references", "caption", "table", "equation",
          "other"]
BLOCK = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "figcaption", "caption", "div", "aside",
         "header", "footer", "section", "figure", "blockquote", "article", "main", "nav", "dt", "dd", "pre", "ol",
         "ul", "table", "tr", "body", "html"}
SPACE_AT = BLOCK | {"br", "span", "sup", "sub"}
VOID = {"br", "img", "hr", "meta", "link", "input", "col", "wbr"}
SKIP = {"head", "style", "script", "title", "template"}
DIG = e36.DIG


# ------------------------------------------------------------------------------------------------ HTML -> blocks

class _Blocks(HTMLParser):
    """Leaf blocks in document order: each text run goes to its innermost block element."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # [tag, attrs dict, node id]
        self.nodes = {}          # id -> dict(tag, attrs, parent, text parts, math parts)
        self.order = []          # node ids of blocks in the order their first text arrived
        self.n = 0
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in SKIP:
            self.skip += 1
            return
        if tag in VOID:
            if tag == "br":
                self._text(" ")
            if tag == "img":
                self._figure(dict(attrs))
            return
        a = {k: (v or "") for k, v in attrs}
        self.n += 1
        parent = self.stack[-1][2] if self.stack else None
        self.nodes[self.n] = dict(tag=tag, attrs=a, parent=parent, text=[], math=[], id=self.n)
        self.stack.append([tag, a, self.n])
        if tag in SPACE_AT:
            self._text(" ")
        if tag == "figure":
            self._figure(a)

    def _figure(self, a):
        pass

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if tag in VOID:
            return
        for k in range(len(self.stack) - 1, -1, -1):        # tolerate unclosed inner tags
            if self.stack[k][0] == tag:
                if tag in SPACE_AT:
                    self._text(" ")
                del self.stack[k:]
                return

    def _text(self, s, math=False):
        if self.skip:
            return
        blk = next((x[2] for x in reversed(self.stack) if x[0] in BLOCK), None)
        if blk is None:
            self.n += 1
            self.nodes[self.n] = dict(tag="p", attrs={}, parent=None, text=[], math=[], id=self.n)
            self.stack.insert(0, ["p", {}, self.n])
            blk = self.n
        node = self.nodes[blk]
        if s.strip() and not node.get("seen"):
            node["seen"] = True
            self.order.append(blk)
        (node["math"] if math else node["text"]).append(s)

    def handle_data(self, data):
        if self.skip:
            return
        in_math = any("math" in x[1].get("class", "").split() or x[0] == "math" for x in self.stack)
        if in_math:
            self._text(data, math=True)
            d = data.strip()
            if d and not _MATH.fullmatch(d):        # span.math without delimiters: inline unless in an equation
                disp = any("equation" in x[1].get("class", "") or "display" in x[1].get("class", "")
                           for x in self.stack)
                d = f"\\[{d}\\]" if disp else f"\\({d}\\)"
            self._text(f" {d} " if d else data)
        else:
            self._text(data)


_MATH = re.compile(r"\\\((.*?)\\\)|\\\[(.*?)\\\]|\$\$(.*?)\$\$", re.S)


def _ancestors(nodes, nid):
    while nid is not None:
        yield nodes[nid]
        nid = nodes[nid]["parent"]


def _classes(n) -> set:
    return set(n["attrs"].get("class", "").lower().split())


def _bbox(nodes, nid):
    for n in _ancestors(nodes, nid):
        b = n["attrs"].get("data-bbox")
        if b:
            try:
                v = [float(x) for x in re.split(r"[,\s]+", b.strip().strip("[]")) if x]
                if len(v) == 4:
                    return v
            except ValueError:
                pass
    return None


def _label(nodes, nid) -> str:
    chain = list(_ancestors(nodes, nid))
    tags = [n["tag"] for n in chain]
    cls = set().union(*[_classes(n) for n in chain])
    if "furniture" in cls or any(t in ("header", "footer") for t in tags) and \
            any(t in ("header", "footer") and "furniture" in _classes(n) for n, t in zip(chain, tags)):
        return "furniture"
    if any(t in ("figcaption", "caption") for t in tags) or "caption" in cls:
        return "caption"
    if any(t in ("table", "td", "th", "tr") for t in tags):
        return "table"
    if "footnote" in cls or "footnotes" in cls:
        return "footnote"
    if "verse" in cls or "hemistich" in cls or "poem" in cls:
        return "verse"
    if "equation" in cls or "math-display" in cls:
        return "equation"
    if "references" in cls or "bibliography" in cls:
        return "references"
    if any(t in ("h1", "h2", "h3", "h4", "h5", "h6") for t in tags):
        return "heading"
    if "li" in tags:
        return "list"
    if "figure" in tags or "other" in cls:
        return "other"
    return "body"


def blocks_of(html: str) -> list[dict]:
    """Leaf blocks: text (math removed), math, label, bbox (0-1000) or None, page (data-page of a section)."""
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    if m:
        html = m.group(1)
    p = _Blocks()
    p.feed(html)
    p.close()
    out = []
    for nid in p.order:
        n = p.nodes[nid]
        raw = "".join(n["text"])

        maths = []

        def keep(mo):
            s = next(g for g in mo.groups() if g is not None)
            maths.append(s)
            # inline math that is a bare number / letter counts as page text; display math never does
            return s if mo.group(1) is not None and not re.search(r"[\\^_{]", s) else " "
        text = _MATH.sub(keep, raw)
        text = re.sub(r"\s+", " ", text).strip()
        lab = _label(p.nodes, nid)
        if lab == "body" and not text and maths:
            lab = "equation"
        page = next((a["attrs"].get("data-page") for a in _ancestors(p.nodes, nid)
                     if "page" in _classes(a) and a["attrs"].get("data-page")), None)
        out.append(dict(text=text, math=" ".join(x.strip() for x in maths if x.strip()), label=lab,
                        bbox=_bbox(p.nodes, nid), page=int(page) if page and page.isdigit() else None,
                        tag=n["tag"]))
    return out


def tables_of(html: str) -> list[dict]:
    """Each <table> with its data-bbox (for TEDS against the gold files' drafted tables)."""
    out = []
    for m in re.finditer(r"<table\b([^>]*)>.*?</table>", html, re.S | re.I):
        b = re.search(r'data-bbox="([^"]+)"', m.group(1))
        out.append(dict(html=m.group(0), bbox=[float(x) for x in re.split(r"[,\s]+", b.group(1).strip()) if x]
                        if b else None))
    return out


def equations_of(blocks) -> list[dict]:
    return [dict(latex=b["math"], bbox=b["bbox"]) for b in blocks if b["label"] == "equation" and b["math"]]


# ------------------------------------------------------------------------------------------------ references

def jload(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def azure_doc_lines(stem: str, page: int) -> tuple[list[dict], int, int]:
    """Azure's lines of one page of a whole document, in pixels at 300 dpi; (lines, width, height)."""
    a = jload(DOCS / f"{stem}.json")
    r = a.get("analyzeResult", a)
    pg = r["pages"][page - 1]
    s = 300.0 if pg.get("unit", "inch") == "inch" else 1.0
    lines = []
    for ln in pg.get("lines", []):
        xs, ys = ln["polygon"][0::2], ln["polygon"][1::2]
        lines.append(dict(text=ln["content"], box=[min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s], kind="text"))
    return lines, int(round(pg["width"] * s)), int(round(pg["height"] * s))


def ref_doc(pid, stem, lines, tables=(), equations=()) -> dict:
    ls = [dict(id=f"l{i:03d}", text=ln.get("text", ""), box=ln.get("box"), kind=ln.get("kind") or "text",
               status="ok") for i, ln in enumerate(lines) if (ln.get("text") or "").strip()]
    return dict(page_id=pid, stem=stem, kinds=[], primary="", decade="", split="", lines=ls,
                order=[x["id"] for x in ls], tables=list(tables), equations=list(equations), status="done")


def units(which: str) -> list[dict]:
    S = sample()
    out = []
    if which in ("sample", "all"):
        for p in S["pages"]:
            out.append(dict(p, unit="sample"))
    if which in ("docs", "all"):
        have = {u["page_id"] for u in out}
        for d in S["docs"]:
            for n in range(1, d["pages"] + 1):
                pid = f"{d['stem']}_p{n:03d}"
                if pid in have:
                    continue
                if which == "docs" and any(p["page_id"] == pid for p in S["pages"]):
                    out.append(dict(next(p for p in S["pages"] if p["page_id"] == pid), unit="sample", doc=d["stem"]))
                    continue
                _, W, H = azure_doc_lines(d["stem"], n)
                out.append(dict(page_id=pid, stem=d["stem"], page=n, kind="doc_page", truth=None, ncols=None,
                                width=W, height=H, referee_labels=None, unit="doc", tags=[]))
    return out


# ------------------------------------------------------------------------------------------------ reading

def read_unit(adir: Path, u: dict, _doc_cache={}) -> tuple[list[dict] | None, list[dict], str]:
    f = adir / f"{u['page_id']}.html"
    if f.exists():
        h = f.read_text(encoding="utf-8")
        return blocks_of(h), tables_of(h), "page"
    df = adir / "docs" / f"{u['stem']}.html"
    if df.exists():
        key = (str(df), df.stat().st_mtime)
        if key not in _doc_cache:
            h = df.read_text(encoding="utf-8")
            secs = {}
            for m in re.finditer(r'<section\b[^>]*class="[^"]*\bpage\b[^"]*"[^>]*>', h):
                pm = re.search(r'data-page="(\d+)"', m.group(0))
                if pm:
                    secs[int(pm.group(1))] = m.start()
            pos = sorted((v, k) for k, v in secs.items()) + [(len(h), None)]
            parts = {k: h[s:pos[i + 1][0]] for i, (s, k) in enumerate(pos[:-1])}
            _doc_cache[key] = parts
        part = _doc_cache[key].get(u["page"])
        if part is not None:
            return blocks_of(part), tables_of(part), "doc"
    return None, [], "missing"


def to_px(b, W, H):
    return [b[0] * W / 1000, b[1] * H / 1000, b[2] * W / 1000, b[3] * H / 1000] if b else None


def _tri(s):
    s = s.replace(" ", "")
    return Counter(s[i:i + 3] for i in range(len(s) - 2))


def _cover(line_box, b):
    ix = max(0.0, min(line_box[2], b[2]) - max(line_box[0], b[0]))
    iy = max(0.0, min(line_box[3], b[3]) - max(line_box[1], b[1]))
    a = max(1.0, (line_box[2] - line_box[0]) * (line_box[3] - line_box[1]))
    return ix * iy / a


# ------------------------------------------------------------------------------------------------ one page

def words_eval(plines, rlines, rkinds=None, kraken=None) -> dict:
    """36's hallucination accounting on lists of line texts."""
    PT, RT = e36.tokens(plines), e36.tokens(rlines)
    P, Rw = [t[0] for t in PT], [t[0] for t in RT]
    R = e36.Ref(RT)
    anc = e36.anchors(P, R)
    rep = e36.repeated_words(P, Rw)
    inv = {i for s, e in e36.unexplained(P, anc, R, skip=rep) for i in range(s, e)}
    inv_az = set(inv)
    if kraken is not None:
        K = e36.Ref(e36.tokens(kraken))
        invK = {i for s, e in e36.unexplained(P, e36.anchors(P, K), K, skip=rep) for i in range(s, e)}
        inv = inv & invK
    Pt = e36.Ref(PT)
    drp = {j for s, e in e36.unexplained(Rw, e36.anchors(Rw, Pt), Pt) for j in range(s, e)}
    c, n = e36.concordance([a for a in anc if a >= 0])
    ex_inv = [" ".join(PT[i][1] for i in range(s, e)) for s, e in e36.runs([i in inv for i in range(len(P))])][:3]
    ex_drp = [" ".join(RT[j][1] for j in range(s, e)) for s, e in e36.runs([j in drp for j in range(len(Rw))])][:3]
    out = dict(ref_words=len(Rw), pred_words=len(P), invented=len(inv), invented_az=len(inv_az), dropped=len(drp),
               repeated=len(rep), order_ok=c, order_pairs=n, ex_invented=[x[:160] for x in ex_inv],
               ex_dropped=[x[:160] for x in ex_drp])
    if rkinds:
        out["dropped_furniture"] = sum(1 for j in drp if rkinds[RT[j][2]] == "furniture")
    return out


def cer_row(ref: dict, plines: list[str], prefix: str, digits=False) -> dict:
    pred = {"lines": [{"text": t.translate(DIG) if digits else t} for t in plines]}
    sp = score_page(ref, pred)
    return {f"{prefix}.f_err": sp["faithful.char_err"], f"{prefix}.f_chars": sp["faithful.chars"],
            f"{prefix}.d_err": sp["folded.char_err"], f"{prefix}.d_chars": sp["folded.chars"]}


def page_eval(u: dict, adir: Path) -> dict:
    pid = u["page_id"]
    W, H = u["width"], u["height"]
    blocks, tables, how = read_unit(adir, u)
    row = dict(page_id=pid, stem=u["stem"], kind=u["kind"], unit=u["unit"], source=how,
               multicol=bool((u.get("ncols") or 1) > 1), truth=u.get("truth"))
    blocks = blocks or []
    for b in blocks:
        b["px"] = to_px(b["bbox"], W, H)
    plines = [b["text"] for b in blocks if b["text"]]
    p_notab = [b["text"] for b in blocks if b["text"] and b["label"] != "table"]
    tab_boxes = [b["px"] for b in blocks if b["label"] == "table" and b["px"]] + \
                [to_px(t["bbox"], W, H) for t in tables if t["bbox"]]
    row.update(blocks=len(blocks), labels=dict(Counter(b["label"] for b in blocks)),
               with_bbox=sum(1 for b in blocks if b["bbox"]), tables=len(tables),
               equations=sum(1 for b in blocks if b["label"] == "equation"),
               figures=sum(1 for b in blocks if b["label"] == "other"))
    # references
    if u["unit"] == "sample":
        az = jload(u["azure_file"])["lines"]
        kp = B36 / "kraken" / f"{pid}.json"
        kraken = [ln["text"] for ln in jload(kp)["lines"] if (ln.get("text") or "").strip()] if kp.exists() else None
    else:
        az, _, _ = azure_doc_lines(u["stem"], u["page"])
        kraken = None
    lab = {}
    if u.get("referee_labels"):
        lab_rows = jload(u["referee_labels"])["lines"]
    else:
        lab_rows = []
    ref_table_boxes = [x["box"] for x in lab_rows if x.get("ref") == "table"]
    # (a) CER vs Azure (all text) and vs truth
    tb, eq = e36.drafts_of(pid) if u["unit"] == "sample" else ([], [])
    row.update(cer_row(ref_doc(pid, u["stem"], az), plines, "az"))
    if u.get("truth") == "gold":
        g = gold_load(GOLD / f"{pid}.json")
        row.update(cer_row(g, plines, "gold"))
        tl = [ln["text"] for ln in e36.gold_lines(g) if ln.get("kind", "text") != "equation"]
        w = words_eval(plines, tl)
        row.update({f"truth.{k}": v for k, v in w.items()})
    elif u.get("truth") == "born_digital":
        t = jload(u["truth_file"])
        t, gone = e36.bd_clean(pid, t, {"lines": az})
        bl = blocks
        if gone:      # the reader's text in a dropped running head goes too (by box, else by text like Azure's)
            keep = e36.drop_like({"lines": [dict(text=b["text"], box=b["px"]) for b in bl if b["text"]]}, gone)
            plines_bd = [x["text"] for x in keep["lines"]]
        else:
            plines_bd = plines
        ref = ref_doc(pid, u["stem"], e36.digits_folded(t)["lines"])
        row.update(cer_row(ref, plines_bd, "bd", digits=True))
        w = words_eval([x.translate(DIG) for x in plines_bd], [ln["text"].translate(DIG) for ln in t["lines"]])
        row.update({f"truth.{k}": v for k, v in w.items()})
    # (b) invented / dropped vs Azure outside tables
    def in_tab(box):
        return box and any(_cover(box, tbx) >= 0.5 for tbx in tab_boxes + ref_table_boxes)
    az_nt = [ln for ln in az if ln.get("kind") != "cell" and not in_tab(ln.get("box"))]
    w = words_eval(p_notab, [ln["text"] for ln in az_nt], [ln.get("kind", "text") for ln in az_nt], kraken)
    row.update({f"az.{k}": v for k, v in w.items()})
    # (d) reading order: truth where there is one, else Azure (all text)
    if u.get("truth"):
        row["order_ok"], row["order_pairs"] = row["truth.order_ok"], row["truth.order_pairs"]
    else:
        wo = words_eval(plines, [ln["text"] for ln in az])
        row["order_ok"], row["order_pairs"] = wo["order_ok"], wo["order_pairs"]
    # (c) layout vs the referee
    if lab_rows:
        tris = [_tri(folded(b["text"] + " " + b["math"])) for b in blocks]
        conf = Counter()
        lt = lb = n = hit = boxed = 0
        for x in lab_rows:
            ref = x.get("ref")
            if ref in (None, "other"):
                continue
            n += 1
            t3 = _tri(folded(x.get("text") or ""))
            best, bi = 0.0, None
            if sum(t3.values()) >= 1:
                tot = sum(t3.values())
                for i, bt in enumerate(tris):
                    v = sum((t3 & bt).values()) / tot
                    if v > best:
                        best, bi = v, i
            else:     # a line too short for letter triples (a page number): a block holding it as a word,
                s = folded(x.get("text") or "").replace(" ", "")      # the nearest one by box when boxes exist
                cand = [i for i, b in enumerate(blocks) if s and s in folded(b["text"] + " " + b["math"]).split()]
                if cand:
                    cy = (x["box"][1] + x["box"][3]) / 2
                    bi = min(cand, key=lambda i: abs((blocks[i]["px"][1] + blocks[i]["px"][3]) / 2 - cy)
                             if blocks[i]["px"] else 0)
                    best = 1.0
            pt = blocks[bi]["label"] if bi is not None and best >= 0.5 else "none"
            lt += pt == ref
            conf[(ref, pt)] += 1
            if bi is not None and best >= 0.5 and blocks[bi]["px"]:
                boxed += 1
                cx, cy = (x["box"][0] + x["box"][2]) / 2, (x["box"][1] + x["box"][3]) / 2
                b = blocks[bi]["px"]
                hit += b[0] <= cx <= b[2] and b[1] <= cy <= b[3]
            cand = [(_cover(x["box"], b["px"]), b["label"]) for b in blocks if b["px"]]
            cand = [c for c in cand if c[0] >= 0.4]
            pb = max(cand)[1] if cand else "none"
            lb += pb == ref
        row.update(lay_n=n, lay_text_ok=lt, lay_box_ok=lb, lay_boxed=boxed, lay_hit=hit,
                   confusion={f"{a}->{b}": c for (a, b), c in conf.items()})
    # tables / equations against the gold files' drafts (gemini-3.1-pro): agreement, not truth
    if tb:
        pr = [(t["html"], to_px(t["bbox"], W, H)) for t in tables]
        v = [teds(r, p) for r, p in e36.boxpair([(x["html"], x["box"]) for x in tb], pr)]
        v = [x for x in v if x is not None]
        if v:
            row["teds_sum"], row["teds_n"] = sum(v), len(v)
    if eq:
        pr = [(e["latex"], to_px(e["bbox"], W, H)) for e in equations_of(blocks)]
        v = [eq_sim(r, p) for r, p in e36.boxpair([(x["latex"], x["box"]) for x in eq], pr)]
        if v:
            row["eq_sum"], row["eq_n"] = sum(s for s, _ in v), len(v)
    return row


# ------------------------------------------------------------------------------------------------ cost

def costs(adir: Path, prefix: str, us: list[dict]) -> dict:
    rows = [json.loads(l) for l in SPEND.read_text().splitlines() if l.strip()] if SPEND.exists() else []
    rows = [r for r in rows if r.get("tag", "").startswith(prefix)]
    pids = sorted({u["page_id"] for u in us}, key=len, reverse=True)
    docs = {d["stem"]: d["pages"] for d in sample()["docs"]}
    c = defaultdict(lambda: [0.0, 0.0])
    unassigned = 0.0
    for r in rows:
        t = r["tag"]
        p = next((p for p in pids if p in t), None)
        if p:
            c[p][0] += r["usd"]; c[p][1] += r.get("secs", 0) or 0
            continue
        s = next((s for s in docs if s in t), None)
        if s:
            for n in range(1, docs[s] + 1):
                c[f"{s}_p{n:03d}"][0] += r["usd"] / docs[s]; c[f"{s}_p{n:03d}"][1] += (r.get("secs", 0) or 0) / docs[s]
            continue
        unassigned += r["usd"]
    for u in us:
        mf = adir / f"{u['page_id']}.meta.json"
        if mf.exists():
            m = jload(mf)
            c[u["page_id"]] = [m.get("usd", 0.0), m.get("secs", 0.0)]
    return dict(per_page={k: v for k, v in c.items()}, unassigned=unassigned, total=sum(r["usd"] for r in rows))


# ------------------------------------------------------------------------------------------------ summary

def summarise(rows: list[dict]) -> dict:
    def ratio(rs, a, b, k=1.0):
        A, B = sum(r.get(a, 0) for r in rs), sum(r.get(b, 0) for r in rs)
        return round(k * A / B, 4) if B else None

    def block(rs):
        if not rs:
            return None
        return dict(
            pages=len(rs), missing=sum(r["source"] == "missing" for r in rs),
            cer_gold=ratio(rs, "gold.f_err", "gold.f_chars"), cer_gold_folded=ratio(rs, "gold.d_err", "gold.d_chars"),
            cer_bd=ratio(rs, "bd.f_err", "bd.f_chars"), cer_bd_folded=ratio(rs, "bd.d_err", "bd.d_chars"),
            cer_az=ratio(rs, "az.f_err", "az.f_chars"), cer_az_folded=ratio(rs, "az.d_err", "az.d_chars"),
            invented_per_1000w=ratio(rs, "az.invented", "az.ref_words", 1000),
            invented_az_per_1000w=ratio(rs, "az.invented_az", "az.ref_words", 1000),
            dropped_per_1000w=ratio(rs, "az.dropped", "az.ref_words", 1000),
            dropped_furniture_per_1000w=ratio(rs, "az.dropped_furniture", "az.ref_words", 1000),
            repeated_per_1000w=ratio(rs, "az.repeated", "az.ref_words", 1000),
            truth_invented_per_1000w=ratio(rs, "truth.invented", "truth.ref_words", 1000),
            truth_dropped_per_1000w=ratio(rs, "truth.dropped", "truth.ref_words", 1000),
            pages_inventing=round(sum(r.get("az.invented", 0) > 0 for r in rs) / len(rs), 3),
            layout_text_acc=ratio(rs, "lay_text_ok", "lay_n"), layout_box_acc=ratio(rs, "lay_box_ok", "lay_n"),
            box_hit=ratio(rs, "lay_hit", "lay_boxed"), layout_lines=sum(r.get("lay_n", 0) for r in rs),
            word_order=ratio(rs, "order_ok", "order_pairs"),
            teds_vs_pro_draft=ratio(rs, "teds_sum", "teds_n"), eq_sim_vs_pro_draft=ratio(rs, "eq_sum", "eq_n"),
            usd=round(sum(r.get("usd", 0) for r in rs), 4), usd_per_page=round(sum(r.get("usd", 0) for r in rs) / len(rs), 4),
            secs_per_page=round(sum(r.get("secs", 0) for r in rs) / len(rs), 1))

    out = dict(all=block(rows), truth_gold=block([r for r in rows if r.get("truth") == "gold"]),
               truth_bd=block([r for r in rows if r.get("truth") == "born_digital"]),
               multicolumn=block([r for r in rows if r.get("multicol")]),
               doc_pages=block([r for r in rows if r["unit"] == "doc"]))
    for k in sorted({r["kind"] for r in rows}):
        out["kind " + k] = block([r for r in rows if r["kind"] == k])
    conf = Counter()
    for r in rows:
        for k, v in r.get("confusion", {}).items():
            a, b = k.split("->")
            if a != b:
                conf[k] += v
    out["layout_confusions"] = dict(conf.most_common(15))
    return {k: v for k, v in out.items() if v is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--pages", default="sample", choices=["sample", "docs", "all"])
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    us = units(a.pages)
    for d in a.dirs:
        adir = Path(d)
        if not adir.is_absolute():
            adir = (HERE / d) if (HERE / d).exists() else Path.cwd() / d
        prefix = a.prefix if a.prefix is not None else adir.name + "_"
        cs = costs(adir, prefix, us)
        rows = []
        for u in us:
            r = page_eval(u, adir)
            r["usd"], r["secs"] = cs["per_page"].get(u["page_id"], [0.0, 0.0])
            rows.append(r)
        summ = summarise(rows)
        summ["spend_total_for_prefix"] = round(cs["total"], 4)
        summ["spend_unassigned"] = round(cs["unassigned"], 4)
        (adir / f"score_{a.pages}.json").write_text(json.dumps(dict(approach=adir.name, prefix=prefix, pages=a.pages,
                                                                     summary=summ, rows=rows), ensure_ascii=False,
                                                                indent=1), encoding="utf-8")
        print(f"== {adir.name} ({a.pages}: {len(rows)} pages) -> {adir / f'score_{a.pages}.json'}")
        for k in ("all", "truth_gold", "truth_bd", "multicolumn", "doc_pages"):
            if k in summ:
                s = summ[k]
                print(f"  {k:12} " + " ".join(f"{x}={s[x]}" for x in (
                    "pages", "missing", "cer_gold", "cer_bd", "cer_az", "invented_per_1000w", "dropped_per_1000w",
                    "layout_text_acc", "layout_box_acc", "word_order", "teds_vs_pro_draft", "eq_sim_vs_pro_draft",
                    "usd_per_page", "secs_per_page") if s.get(x) is not None))
        if not a.quiet:
            print("  confusions", summ["layout_confusions"])


if __name__ == "__main__":
    main()
