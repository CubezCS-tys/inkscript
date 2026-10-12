"""Experiment 36: the owner's page, out/report.html (self-contained; scan crops embedded as JPEG).

    /home/yassine/inkscript/.venv/bin/python make_report.py
Reads out/results.json (evaluate.py), out/judge.jsonl, out/eval_pages.jsonl, out/pred/<reader>/, out/kraken/,
out/ref/bdtruth/, the gold files (read only) and the page images in out/pack. Rerun after evaluate.py.
Needs only numpy and opencv (both in the repo's venv). Equations are rendered by KaTeX from cdnjs (pinned).
"""
from __future__ import annotations

import base64
import difflib
import html
import json
import sys
import tarfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from inkscript.gold.text import faithful  # noqa: E402

OUT = Path("/home/yassine/inkscript/experiments/36_vlm_bakeoff/out")
GOLD = Path("/home/yassine/inkscript/experiments/34_yardstick/out/gold")
R = json.load(open(OUT / "results.json"))
RES = R["results"]
JUDGE = [json.loads(l) for l in (OUT / "judge.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
EVAL = {}
for _l in (OUT / "eval_pages.jsonl").read_text(encoding="utf-8").splitlines():
    _d = json.loads(_l)
    EVAL[(_d["reader"], _d["page_id"], _d["set"])] = _d
TAR = tarfile.open(OUT / "pack" / "pages.tar")

READERS = ["azure", "dots_mocr", "dots_ocr", "amad_vlm6", "paddle_vl15", "qwen3vl32b_awq", "qwen3vl8b", "kraken"]
VLMS = ["dots_mocr", "dots_ocr", "amad_vlm6", "paddle_vl15", "qwen3vl32b_awq", "qwen3vl8b"]
NAME = {"azure": "Azure (paid, today's reader)", "dots_mocr": "dots.mocr", "dots_ocr": "dots.ocr",
        "amad_vlm6": "amad-vlm6 (text only)", "paddle_vl15": "PaddleOCR-VL-1.5", "qwen3vl32b_awq": "Qwen3-VL-32B AWQ",
        "qwen3vl8b": "Qwen3-VL-8B", "kraken": "Kraken (the checker)"}
SHORT = {"azure": "Azure", "dots_mocr": "dots.mocr", "dots_ocr": "dots.ocr", "amad_vlm6": "amad", "paddle_vl15": "Paddle",
         "qwen3vl32b_awq": "Qwen-32B", "qwen3vl8b": "Qwen-8B", "kraken": "Kraken"}
COLOR = {"azure": "var(--c-azure)", "dots_mocr": "var(--c-mocr)", "dots_ocr": "var(--c-ocr)", "amad_vlm6": "var(--c-amad)",
         "paddle_vl15": "var(--c-paddle)", "qwen3vl32b_awq": "var(--c-q32)", "qwen3vl8b": "var(--c-q8)",
         "kraken": "var(--c-kraken)"}


# ---------------------------------------------------------------- small helpers

def g(d, *ks):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def stat(sset, rd, k, part="all"):
    st = g(RES, sset, rd, part) or {}
    return st.get(k), (st.get("ci95") or {}).get(k)


def pct(x, d=1):
    return "–" if x is None else f"{100 * x:.{d}f}%"


def num(x, d=1):
    return "–" if x is None else f"{x:,.{d}f}"


def jload(f: Path):
    return json.loads(f.read_text(encoding="utf-8"))


def page_image(pid: str):
    if pid.startswith("bd_"):
        im = cv2.imread(str(OUT / "pack" / "bd" / f"{pid}.jpg"), cv2.IMREAD_GRAYSCALE)
    else:
        b = TAR.extractfile(f"pages/{pid}.jpg").read()
        im = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_GRAYSCALE)
    return im


def crop(im, box, pad=12):
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    h, w = im.shape[:2]
    return im[max(0, y0 - pad):min(h, y1 + pad), max(0, x0 - pad):min(w, x1 + pad)]


def jpg64(im, width=None, q=62):
    if width and im.shape[1] > width:
        im = cv2.resize(im, (width, max(1, int(im.shape[0] * width / im.shape[1]))), interpolation=cv2.INTER_AREA)
    ok, b = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])
    return "data:image/jpeg;base64," + base64.b64encode(b.tobytes()).decode(), im.shape[1], im.shape[0]


def union(boxes):
    boxes = [b for b in boxes if b]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def overlap(a, b):
    """Share of box a's area inside box b."""
    if not a or not b:
        return 0.0
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    return w * h / max(1e-6, (a[2] - a[0]) * (a[3] - a[1]))


def marked(ref: str, hyp: str) -> str:
    """The reader's text with what differs from the reference marked (red = wrong or extra, ‸ = missing)."""
    ref, hyp = faithful(ref), faithful(hyp or "")
    if not hyp:
        return '<span class="miss">(nothing read here)</span>'
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_opcodes():
        seg = html.escape(hyp[j1:j2])
        if tag == "equal":
            out.append(seg)
        elif tag in ("replace", "insert"):
            out.append(f'<span class="bad">{seg if seg.strip() else "&#x2423;"}</span>')
            if tag == "replace" and i2 - i1 > j2 - j1 + 2:
                out.append(f'<span class="gap" title="missing: {html.escape(ref[i1:i2])}">&#x2038;</span>')
        else:
            out.append(f'<span class="gap" title="missing: {html.escape(ref[i1:i2])}">&#x2038;</span>')
    return "".join(out)


def cer(ref, hyp):
    r, h = faithful(ref), faithful(hyp or "")
    if not r:
        return None
    sm = difflib.SequenceMatcher(None, r, h, autojunk=False)
    e = sum(max(i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal")
    return e / len(r)


# ---------------------------------------------------------------- bars

def bars(title, sset, key, part="all", note="", scale=None, as_pct=True, readers=READERS, unit="", values=None,
         lower_better=True):
    rows = []
    vals = {}
    for rd in readers:
        if values is not None:
            v, c = values.get(rd, (None, None))
        else:
            v, c = stat(sset, rd, key, part)
        vals[rd] = (v, c)
    top = scale or max([(c[1] if c else v) for v, c in vals.values() if v is not None] + [1e-9])
    for rd in readers:
        v, c = vals[rd]
        lab = f'<span class="lab">{html.escape(NAME[rd])}</span>'
        if v is None:
            rows.append(f'<div class="row">{lab}<span class="track"><span class="na">not measured (no such output)</span></span></div>')
            continue
        w = min(v / top, 1.0) * 80
        txt = (pct(v) if as_pct else num(v, 1 if v < 100 else 0)) + unit
        ci_ = ""
        if c:
            lo, hi = min(c[0] / top, 1.0) * 80, min(c[1] / top, 1.0) * 80
            ci_ = f'<span class="ci" style="left:{lo:.2f}%;width:{max(hi - lo, 0.3):.2f}%"></span>'
            txt += f' <small>[{pct(c[0]) if as_pct else num(c[0])}–{pct(c[1]) if as_pct else num(c[1])}]</small>'
        over = '<span class="over">&#x25B6;</span>' if v > top else ""
        pos = max(w, (min(c[1] / top, 1.0) * 80) if c else 0)
        rows.append(f'<div class="row">{lab}<span class="track"><span class="bar" style="width:{w:.2f}%;background:{COLOR[rd]}"></span>'
                    f'{ci_}{over}<span class="val" style="left:calc({pos:.2f}% + 6px)">{txt}</span></span></div>')
    better = "Shorter is better." if lower_better else "Longer is better."
    return (f'<figure class="bars"><figcaption>{title}</figcaption>' + "\n".join(rows)
            + f'<p class="note">{note} {better}</p></figure>')


# ---------------------------------------------------------------- page text in reading order, aligned to gold lines

def reader_words(rd, pid):
    f = OUT / "pred" / rd / f"{pid}.json"
    if not f.exists():
        return []
    d = jload(f)
    return " ".join(faithful(l["text"]) for l in d["lines"]).split()


def gold_lines_in_order(gd):
    by = {l["id"]: l for l in gd["lines"]}
    order = [i for i in gd.get("order") or [] if i in by] or [l["id"] for l in gd["lines"]]
    return [by[i] for i in order]


def align_lines(lines_text, mw):
    """For each reference line, the reader's words that stand for it (word-level matching in reading order)."""
    gw, gl = [], []
    for i, t in enumerate(lines_text):
        for w in faithful(t).split():
            gw.append(w)
            gl.append(i)
    sm = difflib.SequenceMatcher(None, gw, mw, autojunk=False)
    m = {}
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            m[a + k] = b + k
    out = []
    starts = [gl.index(i) if i in gl else None for i in range(len(lines_text))]
    for i in range(len(lines_text)):
        if starts[i] is None:
            out.append("")
            continue
        g0 = starts[i]
        g1 = g0 + sum(1 for x in gl if x == i)
        inside = [k for k in range(g0, g1) if k in m]
        prev = max([m[k] for k in m if k < g0], default=-1)
        nxt = min([m[k] for k in m if k >= g1], default=len(mw))
        if inside:
            s = m[inside[0]] if inside[0] == g0 else prev + 1
            e = m[inside[-1]] if inside[-1] == g1 - 1 else nxt - 1
            s, e = max(s, prev + 1), min(e, nxt - 1)
        else:
            s, e = prev + 1, min(nxt - 1, prev + 1 + 2 * (g1 - g0))
        out.append(" ".join(mw[s:e + 1]) if e >= s else "")
    return out


def line_examples(pid, n=3):
    gd = load_gold(pid)
    lines = [l for l in gold_lines_in_order(gd) if l.get("kind") != "furniture" and l.get("text")]
    texts = [l["text"] for l in lines]
    al = {rd: align_lines(texts, reader_words(rd, pid)) for rd in READERS}
    score = []
    for i in range(len(lines)):
        long_ = len(texts[i].split()) >= 5          # whole body lines, not headings
        score.append(long_ * sum(min(cer(texts[i], al[rd][i]) or 0, 0.3) for rd in VLMS if not rd.startswith("qwen")))
    best = max(range(max(1, len(lines) - n + 1)), key=lambda i: sum(score[i:i + n]))
    im = page_image(pid)
    pe = {rd: EVAL.get((rd, pid, "gold")) for rd in READERS}
    head = []
    for rd in READERS:
        e = pe[rd]
        if e and e.get("faithful.chars"):
            head.append(f'<span class="chip" style="border-color:{COLOR[rd]}">{SHORT[rd]} {pct(e["faithful.char_err"] / e["faithful.chars"])}</span>')
    parts = [f'<div class="ex"><div class="meta">{pid} · {html.escape(gd.get("journal", ""))} {gd.get("year", "")} · '
             f'whole-page character errors: {" ".join(head)}</div>']
    for i in range(best, min(best + n, len(lines))):
        src, w, h = jpg64(crop(im, lines[i]["box"]), width=1000)
        parts.append(f'<img src="{src}" width="{w}" height="{h}" alt="scan line" loading="lazy">')
        parts.append(f'<div class="t gold"><span class="who">gold (owner)</span><span class="txt" dir="rtl">{html.escape(faithful(texts[i]))}</span></div>')
        for rd in READERS:
            c = cer(texts[i], al[rd][i])
            parts.append(f'<div class="t"><span class="who"><i class="dot" style="background:{COLOR[rd]}"></i>{SHORT[rd]} <small>{pct(c, 0)}</small></span>'
                         f'<span class="txt" dir="rtl">{marked(texts[i], al[rd][i])}</span></div>')
        parts.append('<hr>')
    parts[-1] = "</div>"
    return "\n".join(parts)


_GOLD = {}


def load_gold(pid):
    if pid not in _GOLD:
        _GOLD[pid] = jload(GOLD / f"{pid}.json")
    return _GOLD[pid]


# ---------------------------------------------------------------- tables and equations

class _Clean(HTMLParser):
    KEEP = {"table", "thead", "tbody", "tr", "th", "td", "br", "sub", "sup", "b", "i"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in self.KEEP:
            a = "".join(f' {k}="{html.escape(v or "")}"' for k, v in attrs if k in ("rowspan", "colspan") and (v or "").isdigit())
            self.out.append(f"<{tag}{a}>")

    def handle_endtag(self, tag):
        if tag in self.KEEP and tag != "br":
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(html.escape(data))


def clean_table(h):
    p = _Clean()
    p.feed(h or "")
    p.close()
    return "".join(p.out)


def verdicts(pid, oid):
    for j in JUDGE:
        if j["page_id"] == pid and j["id"] == oid:
            out = {}
            for k, v in (j.get("verdicts") or {}).items():
                k = j["labels"].get(k.replace("Candidate", "").strip(), k)
                out[k] = v
            return out
    return {}


def best_object(rd, pid, kind, box):
    f = OUT / "pred" / rd / f"{pid}.json"
    if not f.exists():
        return None
    objs = jload(f).get(kind) or []
    if not objs:
        return None
    withbox = [o for o in objs if o.get("box")]
    if withbox:
        o = max(withbox, key=lambda o: overlap(box, o["box"]) + overlap(o["box"], box))
        if overlap(box, o["box"]) + overlap(o["box"], box) > 0.2:
            return o
    return objs[0] if len(objs) == 1 else (objs[0] if not withbox else None)


def table_example(pid, tid):
    gd = load_gold(pid)
    t = next(x for x in gd["tables"] if x["id"] == tid)
    v = verdicts(pid, tid)
    src, w, h = jpg64(crop(page_image(pid), t["box"]), width=900, q=60)
    cards = []
    for rd in VLMS:
        if rd == "amad_vlm6":
            continue
        o = best_object(rd, pid, "tables", t["box"])
        vv = v.get(rd, {})
        grade = f'judge {vv.get("grade", "–")}/5' if vv else ""
        body = f'<div class="tbl" dir="rtl">{clean_table(o["html"])}</div>' if o and o.get("html") else '<p class="miss">gave no table</p>'
        cards.append(f'<div class="obj"><div class="who2"><i class="dot" style="background:{COLOR[rd]}"></i><b>{NAME[rd]}</b> · {grade}'
                     f'<br><small>{html.escape(vv.get("note", ""))}</small></div>{body}</div>')
    return (f'<div class="ex"><div class="meta">{pid} {tid} · {html.escape(gd.get("journal", ""))} {gd.get("year", "")}</div>'
            f'<div class="side"><figure class="scan"><img src="{src}" width="{w}" height="{h}" alt="scanned table" loading="lazy">'
            f'<figcaption>the scan</figcaption></figure><div class="objs">{"".join(cards)}</div></div></div>')


def eq_example(pid, eid):
    gd = load_gold(pid)
    e = next(x for x in gd["equations"] if x["id"] == eid)
    v = verdicts(pid, eid)
    src, w, h = jpg64(crop(page_image(pid), e["box"], pad=20), width=700, q=65)
    cards = []
    for rd in VLMS:
        if rd == "amad_vlm6":
            continue
        o = best_object(rd, pid, "equations", e["box"])
        vv = v.get(rd, {})
        grade = f'judge {vv.get("grade", "–")}/5' if vv else ""
        if o and o.get("latex"):
            body = (f'<div class="tex" data-tex="{html.escape(o["latex"])}"></div>'
                    f'<pre class="src">{html.escape(o["latex"])}</pre>')
        else:
            body = '<p class="miss">gave no equation (read it as text, or not at all)</p>'
        cards.append(f'<div class="obj"><div class="who2"><i class="dot" style="background:{COLOR[rd]}"></i><b>{NAME[rd]}</b> · {grade}'
                     f'<br><small>{html.escape(vv.get("note", ""))}</small></div>{body}</div>')
    return (f'<div class="ex"><div class="meta">{pid} {eid} · {html.escape(gd.get("journal", ""))} {gd.get("year", "")}</div>'
            f'<img class="eqscan" src="{src}" width="{w}" height="{h}" alt="scanned equation" loading="lazy">'
            f'<div class="objs eqs">{"".join(cards)}</div></div>')


# ---------------------------------------------------------------- inventions and the Kraken flag

def invention_example(rd, pid, sset, needle, why, in_table=False):
    pred = jload(OUT / "pred" / rd / f"{pid}.json")
    line = None if in_table else next((l for l in pred["lines"] if needle in l["text"]), None)
    table = None
    if line is None:                     # the invention sits in a table: show its first rows
        table = next(t for t in pred["tables"] if needle in t["html"])
        b = table["box"]
        box = [b[0], b[1], b[2], b[1] + min(b[3] - b[1], 330)]
        rows = clean_table(table["html"]).split("</tr>")
        line = {"text": "", "html": "</tr>".join(rows[:4]) + "</tr></table>"}
    else:
        box = line["box"]
    if pid.startswith("bd_"):
        ref = jload(OUT / "ref" / "bdtruth" / f"{pid}.json")
        reflab = "truth (the PDF's own text)"
    else:
        ref = jload(OUT / "ref" / "azure" / f"{pid}.json")
        reflab = "Azure"
    refl = [l for l in ref["lines"] if overlap(l.get("box"), box) > 0.4]
    krk = jload(OUT / "kraken" / f"{pid}.json")
    kl = [l for l in krk["lines"] if overlap(l.get("box"), box) > 0.4]
    reft = " ".join(l["text"] for l in refl)
    kt = " ".join(l["text"] for l in kl)
    if table is not None:                # the reference's and Kraken's words inside the table, the first rows' worth
        tb = table["box"]
        inside = lambda l: l.get("box") and tb[0] <= (l["box"][0] + l["box"][2]) / 2 <= tb[2] and tb[1] <= (l["box"][1] + l["box"][3]) / 2 <= tb[3]  # noqa: E731
        refl = [l for l in ref["lines"] if inside(l)]
        kl = [l for l in krk["lines"] if inside(l)]
        cut = lambda ws: " ".join(ws[:40]) + (" …" if len(ws) > 40 else "")  # noqa: E731
        reft = cut(" ".join(l["text"] for l in refl).split())
        kt = cut(" ".join(l["text"] for l in kl).split())
    e = EVAL.get((rd, pid, sset)) or {}
    src, w, h = jpg64(crop(page_image(pid), union([box] + ([l["box"] for l in refl] if table is None else []))), width=1000)
    flag = (f'<p class="flag">&#x2691; Kraken flagged {e.get("chk_flag", 0)} words on this page; '
            f'{e.get("chk_tp", 0)} of the {e.get("invented", 0)} invented words are among them.</p>')
    txt = html.escape(line["text"])
    for run in (e.get("examples") or {}).get("invented", []):
        for wd in sorted(set(run.split()), key=len, reverse=True):
            if len(wd) >= 3 and not any("؀" <= ch <= "ۿ" for ch in wd):
                txt = txt.replace(html.escape(wd), f'\x00{html.escape(wd)}\x01')
    txt = txt.replace("\x00", '<span class="inv">').replace("\x01", "</span>")
    if table is not None:
        txt = f'<div class="tbl inv-t" dir="rtl">{line["html"]}</div>'
    return (f'<div class="ex"><div class="meta">{pid} · {why}</div><img src="{src}" width="{w}" height="{h}" alt="scan" loading="lazy">'
            f'<div class="t gold"><span class="who">{reflab}</span><span class="txt" dir="rtl">{html.escape(faithful(reft))}</span></div>'
            f'<div class="t"><span class="who"><i class="dot" style="background:{COLOR[rd]}"></i>{SHORT[rd]}</span><span class="txt" dir="rtl">{txt}</span></div>'
            f'<div class="t"><span class="who"><i class="dot" style="background:{COLOR["kraken"]}"></i>Kraken here</span><span class="txt" dir="rtl">{html.escape(kt) or "(no line)"}</span></div>'
            f'{flag}</div>')


# ---------------------------------------------------------------- reading order drawn on the page

def order_example(pid):
    im = page_image(pid)
    H, W = im.shape[:2]
    src, w, h = jpg64(im, width=760, q=55)
    figs = []
    for rd in ["azure", "dots_mocr", "dots_ocr", "paddle_vl15"]:
        d = jload(OUT / "pred" / rd / f"{pid}.json")
        items = d["blocks"] if rd != "azure" else d["lines"]
        pts = [((b["box"][0] + b["box"][2]) / 2, (b["box"][1] + b["box"][3]) / 2) for b in items
               if b.get("box") and b.get("kind") != "furniture"]
        e = EVAL.get((rd, pid, "ys_azure")) or {}
        wo = e["word_order_ok"] / e["word_order_pairs"] if e.get("word_order_pairs") else None
        poly = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
        r = W / 60
        nums = []
        for k, (x, y) in enumerate(pts, 1):
            if len(pts) > 30 and k not in (1, len(pts)) and k % 5:
                nums.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r / 3:.0f}" class="pt"/>')
                continue
            nums.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" class="nb"/><text x="{x:.0f}" y="{y + r / 2.6:.0f}" '
                        f'font-size="{r * 1.1:.0f}" text-anchor="middle" class="nt">{k}</text>')
        unit = "lines" if rd == "azure" else "blocks"
        figs.append(f'<figure class="ord"><svg viewBox="0 0 {W} {H}" role="img" aria-label="{SHORT[rd]} reading order">'
                    f'<image href="{src}" width="{W}" height="{H}"/><polyline points="{poly}" class="path" '
                    f'style="stroke:{COLOR[rd]}" stroke-width="{r / 4:.0f}"/>{"".join(nums)}</svg>'
                    f'<figcaption><b>{NAME[rd]}</b> · {len(pts)} {unit} · words in Azure\'s order: {pct(wo, 0) if rd != "azure" else "(the reference)"}</figcaption></figure>')
    others = []
    for rd in ["amad_vlm6", "qwen3vl32b_awq", "qwen3vl8b", "kraken"]:
        e = EVAL.get((rd, pid, "ys_azure")) or {}
        wo = e["word_order_ok"] / e["word_order_pairs"] if e.get("word_order_pairs") else None
        others.append(f"{SHORT[rd]} {pct(wo, 0)}")
    return (f'<div class="ords">{"".join(figs)}</div><p class="note">The same measure for readers that give no usable boxes '
            f'(their order cannot be drawn): {", ".join(others)}.</p>')


# ---------------------------------------------------------------- the page

CSS = """
:root { --bg:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --line:#e4e2dc; --bad:#fde2e1; --badink:#b42318; --card:#fff; --inv:#ffe08a; --invink:#5c3d00;
  --c-azure:#1baf7a; --c-mocr:#2a78d6; --c-ocr:#86b6ef; --c-amad:#6250d6; --c-paddle:#eb6834; --c-q32:#b0477a; --c-q8:#d99ab9; --c-kraken:#a08a2a; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --line:#3a3936; --bad:#5a1e1b; --badink:#ffb4ab; --card:#232321; --inv:#6b5000; --invink:#ffe08a;
  --c-azure:#199e70; --c-mocr:#3987e5; --c-ocr:#7aa7dd; --c-amad:#9085e9; --c-paddle:#d95926; --c-q32:#cf6a9c; --c-q8:#a87891; --c-kraken:#c2a84a; } }
:root[data-theme="dark"] { --bg:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --line:#3a3936; --bad:#5a1e1b; --badink:#ffb4ab; --card:#232321; --inv:#6b5000; --invink:#ffe08a;
  --c-azure:#199e70; --c-mocr:#3987e5; --c-ocr:#7aa7dd; --c-amad:#9085e9; --c-paddle:#d95926; --c-q32:#cf6a9c; --c-q8:#a87891; --c-kraken:#c2a84a; }
* { box-sizing:border-box; }
body { background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,sans-serif; margin:0 auto; max-width:1100px; padding:16px; }
h1 { font-size:1.6rem; margin:.2em 0; } h2 { margin-top:2em; border-bottom:1px solid var(--line); padding-bottom:.2em; } h3 { margin:1.4em 0 .3em; }
p, li { max-width:80ch; } .note { color:var(--ink2); font-size:.85rem; margin:.3em 0 0; } .meta { color:var(--ink2); font-size:.8rem; margin-bottom:4px; }
.lede { font-size:1.02rem; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; }
figure.bars { margin:18px 0; } figcaption { font-weight:600; margin-bottom:6px; }
.row { display:flex; align-items:center; gap:10px; margin:4px 0; } .lab { width:190px; flex:none; color:var(--ink2); font-size:.88rem; }
.track { position:relative; flex:1; height:26px; min-width:0; }
.bar { position:absolute; left:0; top:3px; height:20px; border-radius:0 4px 4px 0; }
.ci { position:absolute; top:12px; height:2px; background:var(--ink2); opacity:.75; }
.over { position:absolute; left:calc(80% - 4px); top:3px; font-size:.9rem; color:var(--ink2); }
.val { position:absolute; top:3px; font-size:.85rem; white-space:nowrap; } .val small { color:var(--ink2); }
.na { color:var(--ink2); font-size:.85rem; position:absolute; left:0; top:4px; }
table.num { border-collapse:collapse; margin:10px 0; font-size:.86rem; } table.num td, table.num th { border-bottom:1px solid var(--line); padding:4px 8px; text-align:right; vertical-align:top; }
table.num th { color:var(--ink2); font-weight:600; } table.num td:first-child, table.num th:first-child { text-align:left; }
.scroll { overflow-x:auto; }
.ex { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px; margin:12px 0; overflow-x:auto; }
.ex img { display:block; max-width:min(100%,820px); height:auto; margin:4px 0 6px auto; background:#fff; }
.ex hr { border:0; border-top:1px dashed var(--line); margin:10px 0; }
.t { display:flex; gap:10px; align-items:baseline; padding:1px 0; } .who { width:120px; flex:none; font-size:.8rem; color:var(--ink2); }
.txt { font-size:1.15rem; flex:1; min-width:0; text-align:right; font-family:"Noto Naskh Arabic","Amiri","Traditional Arabic",serif; overflow-wrap:anywhere; }
.gold .txt { font-weight:600; } .bad { background:var(--bad); color:var(--badink); border-radius:2px; } .gap { color:var(--badink); font-weight:700; } .miss { color:var(--badink); }
.inv { background:var(--inv); color:var(--invink); outline:1px solid var(--invink); border-radius:2px; }
.flag { color:var(--ink); background:var(--bg); border-left:4px solid var(--c-kraken); padding:4px 8px; margin:6px 0 0; font-size:.9rem; }
.dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:baseline; }
.chip { display:inline-block; border:1px solid; border-radius:10px; padding:0 6px; margin:1px 2px; white-space:nowrap; }
.side { display:flex; gap:12px; flex-wrap:wrap; align-items:flex-start; } figure.scan { flex:1 1 300px; margin:0; max-width:420px; } figure.scan figcaption { font-weight:400; font-size:.8rem; color:var(--ink2); }
.objs { flex:2 1 420px; display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:10px; min-width:0; }
.obj { border:1px solid var(--line); border-radius:6px; padding:6px; min-width:0; } .who2 { font-size:.85rem; margin-bottom:4px; } .who2 small { color:var(--ink2); }
.tbl { max-height:420px; overflow:auto; } .tbl table { border-collapse:collapse; font-size:.72rem; font-family:"Noto Naskh Arabic",serif; }
.tbl td, .tbl th { border:1px solid var(--line); padding:1px 4px; text-align:center; }
.inv-t td { background:var(--inv); color:var(--invink); } .eqscan { margin:4px auto 8px !important; max-width:min(100%,460px) !important; } .tex { min-height:2em; overflow-x:auto; padding:4px 0; } pre.src { white-space:pre-wrap; overflow-wrap:anywhere; font-size:.78rem; color:var(--ink2); margin:4px 0 0; }
.ords { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(100%,400px),1fr)); gap:10px; }
figure.ord { margin:0; } figure.ord svg { width:100%; height:auto; border:1px solid var(--line); background:#fff; } figure.ord figcaption { font-weight:400; font-size:.82rem; color:var(--ink2); }
.path { fill:none; stroke-linejoin:round; opacity:.8; } .nb { fill:#111; opacity:.78; } .nt { fill:#fff; font-family:system-ui,sans-serif; font-weight:700; } .pt { fill:#111; opacity:.6; }
.key span { display:inline-block; margin-right:12px; white-space:nowrap; font-size:.85rem; }
@media (max-width:640px) { .lab { width:96px; font-size:.78rem; } .who { width:72px; } .val small { display:none; } }
"""

KATEX = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9"


def judge_means():
    from collections import defaultdict
    gg = defaultdict(list)
    for j in JUDGE:
        for k, v in (j.get("verdicts") or {}).items():
            k = j["labels"].get(k.replace("Candidate", "").strip(), k)
            gg[(j["kind"], k)].append(v.get("grade", 1))
    return {kr: sum(v) / len(v) for kr, v in gg.items()}, {kr: len(v) for kr, v in gg.items()}


def speed_rows():
    s = g(R, "speed", "models") or {}
    rows = []
    for rd in VLMS:
        v = s.get(rd) or {}
        rows.append(f'<tr><td>{NAME[rd]}</td><td>{num(v.get("pages_per_hour"), 0)}</td><td>${num(v.get("usd_per_1000_pages"), 2)}</td>'
                    f'<td>{v.get("hit_cap") if v.get("hit_cap") is not None else "–"}</td></tr>')
    return "\n".join(rows)


def spend():
    gem = sum(json.loads(l)["usd"] for l in (OUT / "gemini_spend.jsonl").read_text().splitlines() if l.strip())
    gpu = sum(json.loads(l).get("cost", 0) for l in (OUT / "gpu_spend.jsonl").read_text().splitlines() if l.strip())
    return gem, gpu


def main():
    sets = R["sets"]
    ng = sets["gold"]
    m = lambda s, rd, k, part="all": stat(s, rd, k, part)[0]  # noqa: E731
    gem, gpu = spend()
    jm, jn = judge_means()
    when = datetime.now().strftime("%Y-%m-%d %H:%M")

    lede = f"""<div class="lede">
<p><b>Question.</b> Which open vision-language model should read Mandumah's whole pages (text, tables, equations and
reading order) in our own stack, how often does each one invent or leave out text, and can Kraken (experiment 33) catch it?</p>
<p><b>Answer: dots.mocr.</b> On the owner's {ng} finished gold pages it gets {pct(m('gold', 'dots_mocr', 'faithful.cer'))} of characters
wrong (Azure {pct(m('gold', 'azure', 'faithful.cer'))}, flattered because the gold was corrected from Azure's draft); on 56 born-digital pages
{pct(m('bd', 'dots_mocr', 'faithful.cer'))} (Azure {pct(m('bd', 'azure', 'faithful.cer'))}). It almost never makes text up
({num(m('ys_azure', 'dots_mocr', 'invented_per_1000w', 'non_table'))} invented words per 1,000 outside tables on the 202 yardstick pages),
it never ran away or gave a page up, it keeps two columns in order, and it is the only reader whose tables the judge rates good
({jm.get(('table', 'dots_mocr'), 0):.2f} of 5). It reads about {num(g(R, 'speed', 'models', 'dots_mocr', 'pages_per_hour'), 0)} pages an hour
on one rented RTX 5090: ${num(g(R, 'speed', 'models', 'dots_mocr', 'usd_per_1000_pages'), 2)} per 1,000 pages.</p>
<p><b>Its weak spots</b>: it leaves out more than it invents ({num(m('ys_azure', 'dots_mocr', 'dropped_per_1000w'))} words per 1,000 compared with Azure),
it drops vowel marks (recall {pct(m('bd', 'dots_mocr', 'mark_recall'), 0)} on born-digital pages, Azure {pct(m('bd', 'azure', 'mark_recall'), 0)}),
and equations are weak for every model ({jm.get(('equation', 'dots_mocr'), 0):.2f} of 5 at best).</p>
<p><b>Kraken as the checker works where it matters</b>: it flags {pct(m('bd', 'dots_mocr', 'checker_recall'), 0)} of dots.mocr's inventions
against the born-digital truth, but most of its flags are false alarms on good readers (precision {pct(m('bd', 'dots_mocr', 'checker_precision'), 0)}),
mostly where Kraken itself misreads tables. So it says where to look, not what is wrong.</p>
<p><b>The others</b>: amad-vlm6 reads plain text best ({pct(m('gold', 'amad_vlm6', 'faithful.cer'))} gold, {pct(m('bd', 'amad_vlm6', 'faithful.cer'))} born-digital)
but gives no layout, tables or equations: a text cross-check. dots.ocr is a step behind dots.mocr everywhere. PaddleOCR-VL reads two-column
Arabic left column first and invents and drops much more. Qwen3-VL gives up on pages, loops, and adds vowel marks the page does not print.</p>
<p><b>Before it is used</b>: dots.mocr's licence is MIT plus an agreement that forbids "unauthorized digitization of publications" and limits
training on its outputs. The owner must clear that before its readings become training data or part of the product.</p>
</div>"""

    key = '<p class="key">' + "".join(f'<span><i class="dot" style="background:{COLOR[rd]}"></i>{NAME[rd]}</span>' for rd in READERS) + \
          '<br>Thin grey line: 95% interval, bootstrapped over documents (a document\'s pages go in or out together). &#x25B6; = bar cut off at the right edge.</p>'

    sec_bars = [
        "<h2>How many characters come out wrong</h2>", key,
        bars(f"1 · The owner's gold pages ({ng} done pages): characters wrong (every vowel mark and hamza counts)", "gold", "faithful.cer",
             note=f"Gold as of {when}: {ng} pages, none with a table or equation. Azure's number is flattered: the gold was corrected from Azure's draft. "
                  "Qwen-32B gave up or looped on 2 of these pages (on the other 4: " + pct(m('gold', 'qwen3vl32b_awq', 'faithful.cer', 'healthy')) + ").", scale=0.15),
        bars("2 · Born-digital pages (56 pages, 30 documents): characters wrong vs the PDF's own text", "bd", "faithful.cer",
             note="Truth: the PDF's text layer (digits folded). Some ligature-order defects in it remain, a small floor under every reader.", scale=0.30),
        bars("3 · All 202 yardstick pages: characters that differ from Azure (agreement, not accuracy)", "ys_azure", "faithful.cer",
             readers=[r for r in READERS if r != "azure"],
             note="Azure is a reader too; reading-order differences on tables and multi-column pages inflate this.", scale=0.60),
        "<h2>Invented, left out, looped</h2>",
        "<p>Counted in words, order-free: a run of 3+ reader words with no counterpart in the reference (and on the yardstick pages, none in "
        "Kraken's reading either) is <i>invented</i>; a reference run the reader lacks is <i>dropped</i>; words in a 4-word run repeated more often "
        "than in the reference are <i>looped</i>. Per 1,000 reference words.</p>",
        bars("4 · Invented words per 1,000, born-digital pages (truth), outside tables", "bd", "invented_per_1000w", part="non_table", as_pct=False,
             note="", scale=12),
        bars("5 · Invented words per 1,000, yardstick pages vs Azure, outside tables", "ys_azure", "invented_per_1000w", part="non_table",
             readers=[r for r in READERS if r != "azure"], as_pct=False, scale=30,
             note="Kraken's own 'inventions' are the rule's false-alarm floor: Kraken cannot invent, only misread."),
        bars("6 · Dropped words per 1,000, yardstick pages vs Azure", "ys_azure", "dropped_per_1000w", as_pct=False, scale=100,
             readers=[r for r in READERS if r != "azure"], note="Qwen's are mostly the pages it gave up (answered with one picture tag)."),
        bars("7 · Looped (repeated) words per 1,000, yardstick pages vs Azure", "ys_azure", "repeated_per_1000w", as_pct=False, scale=100,
             readers=[r for r in READERS if r != "azure"], note="Qwen3-VL-8B loops on many pages until the token cap."),
        "<h2>Vowel marks and reading order</h2>",
        bars("8 · Vowel marks printed on the page that the reader kept (recall), born-digital pages", "bd", "mark_recall", lower_better=False, scale=1.0,
             note="Precision (marks the reader wrote that the page has): " + ", ".join(
                 f"{SHORT[rd]} {pct(m('bd', rd, 'mark_precision'), 0)}" for rd in READERS) + ". Qwen adds marks that are not printed."),
        bars("9 · Words kept in reading order on multi-column pages (yardstick, vs Azure)", "ys_azure", "word_order", part="multicolumn",
             readers=[r for r in READERS if r != "azure"], lower_better=False, scale=1.0,
             note="Kendall concordance of matched words' positions. 50% is a random order; Paddle reads the left column first."),
    ]
    jv = {rd: (jm.get(("table", rd)), None) for rd in VLMS if rd != "amad_vlm6"}
    ev = {rd: (jm.get(("equation", rd)), None) for rd in VLMS if rd != "amad_vlm6"}
    sec_judge = ["<h2>Tables and equations</h2>",
                 f"<p>No gold page has a table or an equation yet, so these are graded by a judge: Gemini 3.1 Pro saw the scan crop and every "
                 f"reader's version, anonymised, and graded each 1–5 ({jn.get(('table', 'dots_mocr'), 0)} tables, {jn.get(('equation', 'dots_mocr'), 0)} equations, "
                 f"${gem:.2f}). A reader that gave nothing scores 1.</p>",
                 bars("10 · Tables: judge's grade (1–5)", "", "", values=jv, readers=list(jv), as_pct=False, scale=5, lower_better=False,
                      note="amad gives plain text only."),
                 bars("11 · Equations: judge's grade (1–5)", "", "", values=ev, readers=list(ev), as_pct=False, scale=5, lower_better=False,
                      note="dots.mocr gave no equation on 29% of them; Qwen on 81%."),
                 "<h3>One table, every reader</h3>", table_example("1681-006-011-010_p051", "t1"),
                 "<h3>One equation, every reader</h3>", eq_example("0478-007-002-005_p006", "e1")]
    sec_lines = ["<h2>Real lines, every reader</h2>",
                 "<p>The scanned line, the owner's reading, then each reader's text for that line; red is wrong or extra, &#x2038; marks "
                 "something missing (hover for what). The percentage is that line's character errors. The chips give each reader's "
                 "errors over the whole page. Most of the VLMs' red on these old prints is one habit: they write the modern "
                 "spelling (في, الذي with dots under the final ya) where the page prints فى, الذى; the faithful count keeps that as an error.</p>",
                 line_examples("0018-010-003-002_p003"), line_examples("0058-023-003-005_p003")]
    sec_inv = ["<h2>Invented text, and Kraken's flag</h2>",
               "<p>Yellow: the words counted as invented. Below each reader, what Kraken read in the same place.</p>",
               invention_example("dots_mocr", "bd_2571-006-011-016_p009", "bd", "playfully",
                                 "dots.mocr's worst invention: English inserted into an Arabic heading"),
               invention_example("paddle_vl15", "bd_2532-029-002-016_p012", "bd", "Λ70ΛV",
                                 "PaddleOCR-VL: a table of Arabic-Indic numbers read as Latin-letter garbage (its first rows)",
                                 in_table=True)]
    sec_ord = ["<h2>Reading order on a two-column page</h2>",
               "<p>Each reader's blocks numbered in the order it reads them, joined by a line (Azure: its lines). Arabic is read from the "
               "right column, top to bottom, then the left.</p>", order_example("1036-000-158-009_p007")]
    sec_speed = ["<h2>Speed and cost</h2>",
                 "<p>One rented RTX 5090 (vLLM, the authors' recipes), the 258 pages of this test. Cost at the rental price ($0.469 an hour).</p>",
                 '<div class="scroll"><table class="num"><tr><th>reader</th><th>pages per hour</th><th>$ per 1,000 pages</th><th>pages that hit the token cap</th></tr>',
                 speed_rows(), "</table></div>",
                 f"<p><b>Spent</b>: GPU ${gpu:.2f} logged (2.0 hours; the account went from $20.378 to $19.318, $1.06 with disk), "
                 f"Gemini judge ${gem:.2f}. Total about ${1.06 + gem:.2f}.</p>"]
    sec_cav = ["<h2>What these numbers cannot tell</h2><ul>",
               f"<li>Very few gold pages ({ng}), none with a table or an equation: the intervals on gold are wide, and tables and equations are "
               "judged by Gemini or compared with Gemini-pro drafts, not with truth.</li>",
               "<li>Azure's gold number is flattered: the owner corrected Azure's draft.</li>",
               "<li>The born-digital truth has ligature-order defects (about 0.5 dropped words per 1,000 under every reader).</li>",
               "<li>Every model ran with its authors' recipe, no prompt tuning; held-out pages were only read, never trained on.</li>",
               "<li>Qwen ran without fp8 KV cache and without async scheduling (setup problems on the rented card), and mostly without boxes; "
               "its speed and some failures may be better with a different setup.</li>",
               "<li>Kraken as the checker is scored against invented words found with the truth; on the yardstick pages the label itself uses "
               "Kraken, so its precision there is not independent.</li></ul>"]

    body = [f'<h1>Which open model should read Mandumah pages</h1>'
            f'<p class="meta">Experiment 36 · VLM bake-off · 2026-10-12 · gold as of {when} ({ng} done pages) · '
            f'{sets["bd"]} born-digital pages, {sets["ys_azure"]} yardstick pages · one RTX 5090</p>', lede]
    body += sec_bars + sec_lines + sec_judge + sec_inv + sec_ord + sec_speed + sec_cav
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VLM bake-off</title>
<link rel="stylesheet" href="{KATEX}/katex.min.css">
<style>{CSS}</style></head><body>
{chr(10).join(body)}
<script src="{KATEX}/katex.min.js"></script>
<script>
document.querySelectorAll('.tex').forEach(function (el) {{
  var s = el.getAttribute('data-tex').replace(/^\\s*\\\\[\\(\\[]|\\\\[\\)\\]]\\s*$/g, '').replace(/\\.{{4,}}/g, '\\\\quad ');
  try {{ if (window.katex) katex.render(s, el, {{throwOnError: false, displayMode: true}}); }} catch (e) {{ el.textContent = ''; }}
}});
</script>
</body></html>"""
    (OUT / "report.html").write_text(page, encoding="utf-8")
    print(OUT / "report.html", f"{len(page.encode()) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
