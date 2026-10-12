"""Experiment 36: every reader's output -> `inkscript score`'s prediction format, one file per page.

    /home/yassine/inkscript/.venv/bin/python convert.py [TAG ...]      # default: every reader found (azure, kraken,
                                                                        # and each out/raw/<tag>/ that has pages)
Writes out/pred/<tag>/<page_id>.json and out/pred/<tag>.kl/<page_id>.json:
    {"lines": [{"text", "box", "kind", "block"}...],          # reading order; box in the pack JPEG's pixels
     "tables": [{"html", "box"}], "equations": [{"latex", "box"}],
     "blocks": [{"kind", "box", "label"}],                    # the model's own blocks (Kraken's box check uses them)
     "meta": {"status", "finish_reason", "hit_cap", "completion_tokens", "seconds", "parse", "has_boxes",
              "has_tables", "has_equations"}}
Lines: a block model's block text is split on newlines, each piece carrying its block's box (the brief's rule). Those
pieces are paragraphs, not printed lines, so line-level measures (line CER, inserted/dropped lines, line order) are
unfair to them; the `.kl` variant re-cuts each text block on the Kraken lines lying inside its box (words shared
out in proportion to each Kraken line's length; Kraken gives only the cut and the box, never text). Character and
word measures do not depend on the cut (lines are joined by a space).
Tables: HTML to `tables` AND each cell's printed lines (split at <br>) to `lines` as kind "cell" (gold keeps table
text as cell lines). Equations (display): LaTeX to `equations` only. Page header/footer: kept, kind "furniture".

To add a model: write a parser `parse_<kind>(rec) -> (blocks, parse_status)` returning blocks
{"kind", "box" (pack pixels or None), "text" | "html" | "latex", "label"} in reading order, and map its tags in KIND.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

OUT = Path("/home/yassine/inkscript/experiments/36_vlm_bakeoff/out")
RAW, PRED = OUT / "raw", OUT / "pred"
MAN = {p["page_id"]: p for p in json.load(open(OUT / "pack" / "manifest.json"))["pages"]}

# raw tag -> parser kind (tags not listed: prefix match below)
KIND = {"dots_mocr": "dots", "dots_ocr": "dots", "qwen3vl32b_awq": "qwen", "qwen3vl32b_awq_card": "qwen",
        "qwen3vl8b": "qwen", "amad_vlm6": "amad", "paddle_vl15": "paddle", "paddle_vl16": "paddle"}


def kind_of(tag: str) -> str:
    if tag in KIND:
        return KIND[tag]
    for k in ("dots", "qwen", "amad", "paddle"):
        if tag.startswith(k):
            return k
    raise SystemExit(f"no parser for {tag}: add it to KIND")


# ---------------------------------------------------------------- categories -> line kinds

CAT = {  # lower-cased model labels -> our kinds
    "text": "text", "list-item": "text", "paragraph": "text", "p": "text", "content": "text", "abstract": "text",
    "reference": "text", "reference_content": "text", "aside_text": "text", "algorithm": "text", "number": "furniture",
    "section-header": "heading", "paragraph_title": "heading", "h1": "heading", "h2": "heading", "h3": "heading",
    "h4": "heading", "h5": "heading", "h6": "heading", "heading": "heading", "title": "title", "doc_title": "title",
    "footnote": "footnote", "vision_footnote": "footnote", "caption": "caption", "figure_title": "caption",
    "table_title": "caption", "chart_title": "caption", "figure_caption": "caption", "table_caption": "caption",
    "page-header": "furniture", "page-footer": "furniture", "header": "furniture", "footer": "furniture",
    "header_image": "picture", "footer_image": "picture",
    "table": "table", "formula": "equation", "display_formula": "equation", "equation": "equation",
    "picture": "picture", "image": "picture", "figure": "picture", "chart": "picture", "seal": "picture",
    "img": "picture", "formula_number": "text", "inline_formula": "text",
}


def cat(label: str) -> str:
    return CAT.get((label or "text").strip().lower(), "text")


_MD = [(re.compile(r"^\s{0,3}#{1,6}\s+"), ""), (re.compile(r"\*\*(.+?)\*\*"), r"\1"), (re.compile(r"__(.+?)__"), r"\1")]


def demarkdown(t: str) -> str:
    for rx, rep in _MD:
        t = rx.sub(rep, t)
    return t


def unlatex_block(t: str) -> str:
    t = t.strip()
    for a, b in (("$$", "$$"), ("\\[", "\\]"), ("$", "$")):
        if t.startswith(a) and t.endswith(b) and len(t) > len(a) + len(b):
            return t[len(a):-len(b)].strip()
    return t


# ---------------------------------------------------------------- small HTML helpers (stdlib only)

class _Cells(HTMLParser):
    """Every table cell's printed lines (split at <br> and newlines), in document order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells, self.cur = [], None

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self.cur = [""]
        elif tag == "br" and self.cur is not None:
            self.cur.append("")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cur is not None:
            self.cells.append([s for s in (x.strip() for x in "".join(c + "\n" for c in self.cur).split("\n")) if s])
            self.cur = None

    def handle_data(self, d):
        if self.cur is not None:
            self.cur[-1] += d


def cell_lines(html: str) -> list[str]:
    p = _Cells()
    try:
        p.feed(html)
        p.close()
    except Exception:
        return []
    return [s for c in p.cells for s in c]


class _QwenHTML(HTMLParser):
    """qwenvl html: each element carrying data-bbox is a block (outermost wins); its inner HTML is kept for tables,
    its text (with <br> as newline) for the rest."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.blocks, self.depth, self.cur = [], 0, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.cur is None:
            if "data-bbox" in a:
                self.cur = dict(tag=tag, cls=a.get("class", ""), bbox=a["data-bbox"], raw="", text="")
                self.depth = 1
            return
        self.depth += tag not in ("br", "img", "hr", "meta")
        self.cur["raw"] += self.get_starttag_text()
        if tag == "br":
            self.cur["text"] += "\n"
        elif tag in ("tr", "p", "div", "li"):
            self.cur["text"] += "\n"

    def handle_startendtag(self, tag, attrs):
        a = dict(attrs)
        if self.cur is None:
            if "data-bbox" in a:
                self.blocks.append(dict(tag=tag, cls=a.get("class", ""), bbox=a["data-bbox"], raw="", text=""))
            return
        self.cur["raw"] += self.get_starttag_text()
        if tag == "br":
            self.cur["text"] += "\n"

    def handle_endtag(self, tag):
        if self.cur is None:
            return
        if tag in ("br", "img", "hr", "meta"):
            return
        self.depth -= 1
        if self.depth == 0:
            self.blocks.append(self.cur)
            self.cur = None
        else:
            self.cur["raw"] += f"</{tag}>"
            if tag in ("td", "th"):
                self.cur["text"] += " "

    def handle_data(self, d):
        if self.cur is not None:
            self.cur["raw"] += d
            self.cur["text"] += d

    def handle_entityref(self, name):
        self.handle_data(htmlmod.unescape(f"&{name};"))

    def handle_charref(self, name):
        self.handle_data(htmlmod.unescape(f"&#{name};"))


# ---------------------------------------------------------------- parsers: raw record -> blocks in pack pixels

def _scale(rec):
    W, H = rec.get("orig_size") or [MAN[rec["page_id"]]["width"], MAN[rec["page_id"]]["height"]]
    w, h = rec.get("seen_size") or [W, H]
    return W / w, H / h


def _salvage_json_list(s: str):
    """A truncated JSON list (hit the token cap): keep every complete object."""
    i = s.find("[")
    if i < 0:
        return None
    s = s[i:]
    for end in [m.start() for m in re.finditer(r"\}\s*,", s)][::-1][:200] + [s.rfind("}")]:
        if end <= 0:
            continue
        try:
            return json.loads(s[:end + 1] + "]")
        except Exception:
            continue
    return None


def parse_dots(rec):
    s = (rec.get("output") or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    status = "ok"
    try:
        d = json.loads(s)
    except Exception:
        d = _salvage_json_list(s)
        status = "salvaged" if d else "unparsed"
    if isinstance(d, dict):
        d = next((v for v in d.values() if isinstance(v, list)), [d])
    if not d:   # the parser's own fallback: the raw text as one block
        return ([dict(kind="text", box=None, text=s, label="raw")] if s else []), "unparsed"
    sx, sy = _scale(rec)
    out = []
    for b in d:
        if not isinstance(b, dict):
            continue
        bb = b.get("bbox")
        box = [bb[0] * sx, bb[1] * sy, bb[2] * sx, bb[3] * sy] if isinstance(bb, list) and len(bb) == 4 else None
        k = cat(b.get("category"))
        t = b.get("text") or ""
        out.append(dict(kind=k, box=box, label=b.get("category"),
                        **({"html": t} if k == "table" else {"latex": unlatex_block(t)} if k == "equation" else
                           {"text": demarkdown(t)})))
    return out, status


def parse_qwen(rec):
    s = (rec.get("output") or "").strip()
    s = re.sub(r"^```(?:html)?\s*|\s*```$", "", s)
    p = _QwenHTML()
    try:
        p.feed(s)
        p.close()
    except Exception:
        pass
    if p.cur is not None:          # truncated mid-block
        p.blocks.append(p.cur)
    W, H = rec.get("orig_size") or [MAN[rec["page_id"]]["width"], MAN[rec["page_id"]]["height"]]
    out = []
    for b in p.blocks:
        try:
            x0, y0, x1, y1 = [float(v) for v in b["bbox"].replace(",", " ").split()]
            box = [x0 / 1000 * W, y0 / 1000 * H, x1 / 1000 * W, y1 / 1000 * H]
        except Exception:
            box = None
        label = b["cls"] or b["tag"]
        k = "table" if b["tag"] == "table" or "table" in label else cat(label.split()[0] if label else b["tag"])
        if b["tag"] in ("h1", "h2", "h3", "h4", "h5", "h6") and k == "text":
            k = "heading"
        text = htmlmod.unescape(b["text"])
        if k == "table":
            out.append(dict(kind=k, box=box, label=label, html=b["raw"] if b["tag"] != "table" else f"<table>{b['raw']}</table>"))
        elif k == "equation":
            out.append(dict(kind=k, box=box, label=label, latex=unlatex_block(text)))
        else:
            out.append(dict(kind=k, box=box, label=label, text=text))
    status = "ok" if p.blocks else ("unparsed" if s else "empty")
    if not p.blocks and s:      # no html: take it as text
        out = [dict(kind="text", box=None, text=re.sub(r"<[^>]+>", "\n", s), label="raw")]
    return out, status


def parse_amad(rec):
    s = rec.get("output") or ""
    if "</think>" in s:
        s = s.rsplit("</think>", 1)[1]
    return ([dict(kind="text", box=None, text=s.strip(), label="plain")] if s.strip() else []), "ok"


def parse_paddle(rec):
    o = rec.get("output")
    if isinstance(o, list):
        o = o[0] if o else {}
    res = (o or {}).get("parsing_res_list") or []
    # parsing_res_list is already in reading order (header/footer carry block_order None): keep it as given
    out = []
    for b in res:
        bb = b.get("block_bbox")
        box = [float(v) for v in bb] if isinstance(bb, list) and len(bb) == 4 else None
        k = cat(b.get("block_label"))
        t = b.get("block_content") or ""
        out.append(dict(kind=k, box=box, label=b.get("block_label"),
                        **({"html": t} if k == "table" else {"latex": unlatex_block(t)} if k == "equation" else
                           {"text": demarkdown(t)})))
    return out, ("ok" if res else "empty")


PARSERS = {"dots": parse_dots, "qwen": parse_qwen, "amad": parse_amad, "paddle": parse_paddle}


# ---------------------------------------------------------------- blocks -> pred

def to_pred(blocks, meta) -> dict:
    lines, tables, eqs, bl = [], [], [], []
    for bi, b in enumerate(blocks):
        bl.append(dict(kind=b["kind"], box=b["box"], label=b.get("label")))
        if b["kind"] == "picture":
            continue
        if b["kind"] == "table":
            tables.append(dict(html=b.get("html", ""), box=b["box"]))
            for t in cell_lines(b.get("html", "")):
                lines.append(dict(text=t, box=b["box"], kind="cell", block=bi))
            continue
        if b["kind"] == "equation":
            eqs.append(dict(latex=b.get("latex", ""), box=b["box"]))
            continue
        for t in (b.get("text") or "").split("\n"):
            t = t.strip()
            if t:
                lines.append(dict(text=t, box=b["box"], kind=b["kind"], block=bi))
    meta = dict(meta, has_boxes=any(b["box"] for b in blocks), has_tables=True, has_equations=True)
    return dict(lines=lines, tables=tables, equations=eqs, blocks=bl, meta=meta)


def recut(pred: dict, kraken: dict) -> dict:
    """The .kl variant: each text block's text shared out over the Kraken lines whose centre lies in its box."""
    kl = [ln for ln in kraken["lines"] if ln.get("box")]
    used = set()
    out, by_block = [], {}
    for ln in pred["lines"]:
        by_block.setdefault(ln.get("block"), []).append(ln)
    for bi, lns in by_block.items():
        box = lns[0].get("box")
        if box is None or lns[0]["kind"] == "cell":
            out += lns
            continue
        inside = [i for i, k in enumerate(kl) if i not in used and box[0] <= (k["box"][0] + k["box"][2]) / 2 <= box[2]
                  and box[1] <= (k["box"][1] + k["box"][3]) / 2 <= box[3]]
        if len(inside) < 2:
            out += lns
            continue
        inside.sort(key=lambda i: (kl[i]["box"][1] + kl[i]["box"][3]) / 2)
        used.update(inside)
        words = " ".join(ln["text"] for ln in lns).split()
        lens = [max(len(kl[i].get("text") or ""), (kl[i]["box"][2] - kl[i]["box"][0]) / 30) for i in inside]
        tot, total_chars = sum(lens), sum(len(w) + 1 for w in words)
        cuts, acc, wi, pos = [], 0.0, 0, 0
        pieces = [[] for _ in inside]
        cum = [sum(lens[:k + 1]) / tot * total_chars for k in range(len(lens))]
        k = 0
        for w in words:
            mid = pos + (len(w) + 1) / 2
            while k < len(cum) - 1 and mid > cum[k]:
                k += 1
            pieces[k].append(w)
            pos += len(w) + 1
        for k, i in enumerate(inside):
            if pieces[k]:
                out.append(dict(text=" ".join(pieces[k]), box=list(kl[i]["box"]), kind=lns[0]["kind"], block=bi))
    return dict(pred, lines=out)


def raw_meta(rec, parse):
    return dict(status=rec.get("status"), finish_reason=rec.get("finish_reason"), hit_cap=bool(rec.get("hit_cap")),
                completion_tokens=rec.get("completion_tokens"), seconds=rec.get("seconds"), parse=parse,
                seen_size=rec.get("seen_size"))


def ref_pred(d: dict, reader: str) -> dict:
    lines = [dict(text=ln["text"], box=ln.get("box"), kind=ln.get("kind", "text"), block=i)
             for i, ln in enumerate(d["lines"]) if (ln.get("text") or "").strip()]
    return dict(lines=lines, tables=[], equations=[], blocks=[dict(kind=x["kind"], box=x["box"]) for x in lines],
                meta=dict(status="ok", reader=reader, has_boxes=True, has_tables=False, has_equations=False))


def synth(seed: int = 36) -> int:
    """A calibration reader, `synth_azure`: Azure's reading with known damage on every page, so the invented-text
    rule and the Kraken checker can be measured before any VLM lands: one line from another page of the same set
    inserted (box: its neighbour's, the hardest case for a box check), one line dropped, and on a fifth of the pages
    a 4-word loop (x5) appended to a line. Inserted lines carry "synth": true."""
    import random
    rng = random.Random(seed)
    pids = sorted(MAN)
    az = {pid: json.load(open(OUT / "ref" / "azure" / f"{pid}.json")) for pid in pids}
    for pid in pids:
        pred = ref_pred(az[pid], "synth_azure")
        L = pred["lines"]
        same = [q for q in pids if q != pid and MAN[q]["kind"] == MAN[pid]["kind"]]
        donor = [ln for ln in az[rng.choice(same)]["lines"] if len(ln["text"].split()) >= 5]
        if len(L) >= 3:
            del L[rng.randrange(1, len(L) - 1)]
        if donor and L:
            k = rng.randrange(0, len(L) + 1)
            nb = L[min(k, len(L) - 1)]
            L.insert(k, dict(text=rng.choice(donor)["text"], box=nb["box"], kind="text", block=-1, synth=True))
        if L and rng.random() < 0.2:
            j = rng.randrange(len(L))
            w = L[j]["text"].split()
            if len(w) >= 4:
                L[j] = dict(L[j], text=L[j]["text"] + " " + " ".join(w[:4] * 5), loop=True)
        pred["meta"]["has_boxes"] = True
        write("synth_azure", pid, pred)
    return len(pids)


def write(tag: str, pid: str, pred: dict):
    for t, p in ((tag, pred), (tag + ".kl", None)):
        d = PRED / t
        if p is None:
            kf = OUT / "kraken" / f"{pid}.json"
            if not kf.exists() or not pred["meta"].get("has_boxes") or tag in ("azure", "kraken", "synth_azure"):
                continue
            p = recut(pred, json.load(open(kf)))
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{pid}.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")


def convert(tag: str) -> dict:
    n, st = 0, {}
    if tag == "synth_azure":
        return dict(tag=tag, pages=synth())
    if tag in ("azure", "kraken"):
        src = OUT / ("ref/azure" if tag == "azure" else "kraken")
        for pid in MAN:
            f = src / f"{pid}.json"
            if f.exists():
                write(tag, pid, ref_pred(json.load(open(f)), tag))
                n += 1
        return dict(tag=tag, pages=n)
    parse = PARSERS[kind_of(tag)]
    for f in sorted((RAW / tag).glob("*.json")):
        if f.name == "run.json" or f.name.count(".") != 1:
            continue
        rec = json.load(open(f))
        if rec.get("page_id") not in MAN:
            continue
        blocks, ps = parse(rec) if rec.get("status", "ok") == "ok" else ([], "failed")
        write(tag, rec["page_id"], to_pred(blocks, raw_meta(rec, ps)))
        st[ps] = st.get(ps, 0) + 1
        n += 1
    return dict(tag=tag, pages=n, parse=st)


def readers() -> list[str]:
    tags = ["azure", "kraken", "synth_azure"]
    if RAW.exists():
        tags += sorted(d.name for d in RAW.iterdir() if d.is_dir() and any(d.glob("*_p*.json")))
    return tags


if __name__ == "__main__":
    for t in (sys.argv[1:] or readers()):
        print(json.dumps(convert(t), ensure_ascii=False), flush=True)
