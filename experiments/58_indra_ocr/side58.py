"""Experiment 58: the side-by-side page (scan | Indra | Azure + Gemini, ours), out/side/index.html.  No calls.

    out/venv/bin/python side58.py

Each page: the scan with Indra's blocks (colour = label, number = Indra's reading order); the scan with our
structure (Azure's lines coloured by Gemini's role, number = our block order); then the text: Indra's lines and
Azure's lines, words that differ from the truth (truth pages) or from each other (other pages) highlighted.
"""
import difflib
import html
import json
import re
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
SIDE = OUT / "side"
(SIDE / "img").mkdir(parents=True, exist_ok=True)

COL = {"Text": (180, 180, 180), "Section-Header": (40, 40, 220), "Page-Header": (200, 120, 0), "Page-Footer": (200, 120, 0),
       "List-Group": (0, 160, 0), "Table": (160, 0, 160), "Caption": (0, 140, 200), "Footnote": (0, 110, 255),
       "Table-Of-Contents": (100, 100, 0), "Form": (100, 100, 0), "Picture": (60, 60, 60)}
GCOL = {"paragraph": "Text", "quote": "Text", "abstract": "Text", "keywords": "Text", "boxed": "Text",
        "title": "Section-Header", "trans_title": "Section-Header", "heading": "Section-Header", "byline": "Section-Header",
        "list_item": "List-Group", "reference": "List-Group", "footnote": "Footnote", "verse": "Text", "table": "Table",
        "equation": "Form", "caption": "Caption", "figure": "Picture", "header": "Page-Header", "footer": "Page-Footer",
        "other_article": "Form", "other": "Form", "noise": "Picture"}
LEGEND = [("Text / paragraph", "Text"), ("heading / title", "Section-Header"), ("running head / page number", "Page-Header"),
          ("list / reference", "List-Group"), ("table", "Table"), ("caption", "Caption"), ("footnote", "Footnote")]

PAGES = [  # (id, kind, why)
    ("0422-004-006-018_p002", "truth", "owner gold page, 2000s print: Indra at its best"),
    ("0656-016-001-011_p003", "truth", "owner gold page, 1960s print: Indra at its worst"),
    ("7956-000-000-016_p001", "truth", "born-digital Arabic page: one of the few where Indra has fewer wrong words than Azure"),
    ("1148-041-116-018_p004", "truth", "born-digital Arabic page with a table"),
    ("0692-003-000-005_p004", "lay", "two columns: the reading orders differ most"),
    ("1136-040-000-023_p012", "lay", "footnote-heavy page"),
    ("0756-001-000-012_p009", "lay", "footnotes Indra calls body text"),
    ("0040-007-004-002_p010", "lay", "a table: Indra's grid against ours"),
]


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def image_of(pid, kind):
    if kind == "truth":
        return E / "41_azure_structure/out/pages" / f"{pid}.jpg"
    return E / "43_rehearsal/out/pages" / f"{pid}.jpg"


def put(img, k, x, y, col, scale=1.0):
    cv2.putText(img, str(k), (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, 1.1 * scale, (255, 255, 255), 6, cv2.LINE_AA)
    cv2.putText(img, str(k), (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, 1.1 * scale, col, 3, cv2.LINE_AA)


def draw_indra(img, ind):
    out = img.copy()
    over = img.copy()
    for k, b in enumerate(ind["blocks"], 1):
        x0, y0, x1, y1 = map(int, b["bbox"])
        c = COL.get(b["label"], (0, 0, 0))
        cv2.rectangle(over, (x0, y0), (x1, y1), c, -1)
    out = cv2.addWeighted(over, 0.22, out, 0.78, 0)
    for k, b in enumerate(ind["blocks"], 1):
        x0, y0, x1, y1 = map(int, b["bbox"])
        c = COL.get(b["label"], (0, 0, 0))
        cv2.rectangle(out, (x0, y0), (x1, y1), c, 4)
        put(out, k, x1 + 4 if x1 < out.shape[1] - 60 else x1 - 60, y0 + 34, c)
    return out


def draw_ours(img, lines):
    """lines: [{px, g, gk}] -> Azure lines coloured by Gemini's role, numbered by block order."""
    out = img.copy()
    over = img.copy()
    first = {}
    for l in lines:
        if l.get("gk") is not None:
            first.setdefault(l["gk"], l)
    rank = {gk: n for n, gk in enumerate(sorted(first, key=lambda g: min(l["go"] for l in lines if l.get("gk") == g)), 1)}
    for l in lines:
        x0, y0, x1, y1 = map(int, l["px"])
        c = COL.get(GCOL.get(l["g"], "Form"), (0, 0, 0))
        cv2.rectangle(over, (x0, y0), (x1, y1), c, -1)
    out = cv2.addWeighted(over, 0.25, out, 0.75, 0)
    for gk, l in first.items():
        x0, y0, x1, y1 = map(int, l["px"])
        c = COL.get(GCOL.get(l["g"], "Form"), (0, 0, 0))
        put(out, rank[gk], x1 + 4 if x1 < out.shape[1] - 60 else x1 - 60, y0 + 34, c)
    return out


def save(img, name, w=900):
    s = w / img.shape[1]
    img = cv2.resize(img, (w, int(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(SIDE / "img" / name), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return f"img/{name}"


def norm(w):
    w = re.sub(r"[^\w؀-ۿ]", "", w)
    w = re.sub("[ً-ْٰـ]", "", w)
    return w.translate(str.maketrans("أإآٱىةی ک", "اااايهي ك")).translate(
        str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).lower()


def marked(lines, ref_words):
    """HTML of lines with every word that has no match in ref_words (aligned, folded) marked."""
    words = [(i, w) for i, ln in enumerate(lines) for w in ln.split()]
    a = [norm(w) for _, w in words]
    sm = difflib.SequenceMatcher(None, a, [norm(w) for w in ref_words], autojunk=False)
    bad = set()
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal":
            bad.update(range(i1, i2))
    out, cur, n_bad = [], [], 0
    li = 0
    for k, (i, w) in enumerate(words):
        if i != li:
            out.append(" ".join(cur))
            cur, li = [], i
        if k in bad and norm(w):
            cur.append(f'<mark>{html.escape(w)}</mark>')
            n_bad += 1
        else:
            cur.append(html.escape(w))
    out.append(" ".join(cur))
    return "<br>".join(out), n_bad, len(words)


def truth_lines(pid):
    g = E / "34_yardstick/out/gold" / f"{pid}.json"
    if g.exists():
        d = jl(g)
        order = {x: n for n, x in enumerate(d.get("order", []))}
        ls = sorted(d["lines"], key=lambda l: order.get(l["id"], 9999))
        return [l["text"] for l in ls if l.get("kind") != "equation"]
    return [l["text"] for l in jl(E / "36_vlm_bakeoff/out/ref/bdtruth" / f"bd_{pid}.json")["lines"]]


def main():
    import sys
    global PAGES
    name = "index.html"
    if len(sys.argv) > 1:                       # extra pages: side58.py <name.html> <id> ...  (lay300 pages)
        name = sys.argv[1]
        PAGES = [(x, "lay", "extra page") for x in sys.argv[2:]]
    lay = {}
    want = {p for p, k, _ in PAGES if k == "lay"}
    for line in open(OUT / "layout_lines.jsonl", encoding="utf-8"):
        if any(w in line[:60] for w in want):
            d = json.loads(line)
            if d["id"] in want:
                lay[d["id"]] = d
    az_truth = jl(OUT / "azure_truth34.json")
    secs = []
    for pid, kind, why in PAGES:
        img = cv2.imread(str(image_of(pid, kind)))
        ind = jl(OUT / "indra/img300" / f"{pid}.json") if kind == "truth" else jl(OUT / "indra/lay300" / f"{pid}.json")
        a = save(draw_indra(img, ind), f"{pid}_indra.jpg")
        il = [l["text"] for l in ind["lines"] if l["text"].strip()]
        if kind == "truth":
            az = [l["text"] for l in az_truth[pid]]
            tl = truth_lines(pid)
            ref_words = [w for t in tl for w in t.split()]
            ih, ib, iw = marked(il, ref_words)
            ah, ab, aw = marked(az, ref_words)
            mid = save(img, f"{pid}_scan.jpg")
            note = (f"Words marked: differ from the hand-checked truth (aligned in reading order, vowel marks and "
                    f"letter forms folded). Indra {ib} of {iw}, Azure {ab} of {aw}.")
            right_img = ("Scan", mid)
        else:
            d = lay[pid]
            az = [l["t"] for l in sorted(d["lines"], key=lambda l: (l["go"] is None, l["go"] or 0))]
            ih, ib, iw = marked(il, [w for t in az for w in t.split()])
            ah, ab, aw = marked(az, [w for t in il for w in t.split()])
            right_img = ("Ours: Azure's lines, Gemini's roles and order", save(draw_ours(img, d["lines"]), f"{pid}_ours.jpg"))
            note = (f"No truth for this page: words marked where Indra and Azure disagree (Azure in our reading "
                    f"order). Indra {ib} of {iw} marked, Azure {ab} of {aw}.")
        secs.append(f"""
<section class="pg"><h2>{html.escape(pid)} <small>{html.escape(why)}</small></h2>
<div class="row">
 <figure><figcaption>Indra: blocks by label, numbers = its reading order</figcaption><img src="{a}" loading="lazy"></figure>
 <figure><figcaption>{right_img[0]}</figcaption><img src="{right_img[1]}" loading="lazy"></figure>
</div>
<p class="note">{note}</p>
<div class="row txt">
 <div><h3>Indra (local CPU)</h3><div class="t" dir="auto">{ih}</div></div>
 <div><h3>Azure (our text)</h3><div class="t" dir="auto">{ah}</div></div>
</div></section>""")
    leg = "".join(f'<span><i style="background:rgb{COL[k][::-1]}"></i>{html.escape(n)}</span>' for n, k in LEGEND)
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Indra side by side</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a64;--line:#dedbd2;--mark:#ffd5cf}}
@media (prefers-color-scheme: dark){{:root{{--bg:#1b1b19;--fg:#ecebe6;--mute:#a3a29b;--line:#3a3935;--mark:#7a2e26}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1900px;padding:16px}}
h1{{font-size:22px;margin:4px 0}} h2{{font-size:17px;margin:28px 0 8px;border-top:1px solid var(--line);padding-top:14px}}
h2 small{{color:var(--mute);font-weight:400;margin-left:8px}} h3{{font-size:14px;margin:6px 0;color:var(--mute)}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} figure{{margin:0}} figcaption{{color:var(--mute);font-size:13px}}
img{{width:100%;height:auto;border:1px solid var(--line)}}
.t{{font-family:"Noto Naskh Arabic","Scheherazade New",serif;font-size:17px;line-height:1.8;border:1px solid var(--line);padding:8px 12px;max-height:620px;overflow:auto}}
mark{{background:var(--mark);color:inherit;border-radius:2px}} .note{{color:var(--mute);font-size:13px}}
.sum{{border:1px solid var(--line);padding:10px 14px;margin:10px 0;font-size:14px}}
.legend span{{margin-right:14px;font-size:13px;white-space:nowrap}} .legend i{{display:inline-block;width:12px;height:12px;margin-right:4px;vertical-align:-1px}}
@media (max-width:800px){{.row{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Indra OCR 1.1 beside our pipeline (experiment 58)</h1>
<p class="note">Local run on this machine, CPU only; no page left it. Colours are the same on both scans: <span class="legend">{leg}</span></p>
<div class="sum"><b>In short (README for the method).</b> Words wrong on our 34 hand-checked pages: Indra 10.4%, Azure 1.8%
(born-digital 3.8% vs 2.4%; old print far worse). Against Gemini's roles on 3,404 pages: 85% of lines agree; footnotes it names
are 98% right but it finds only 41% of them; headings 51%, captions 21%; two-column pages in the same order 42%.
6.7 pages a second on 8 cores. Pages 1-4 are scored against the truth; pages 5-8 compare Indra with our pipeline (no truth).</div>
{''.join(secs)}
</body></html>"""
    (SIDE / name).write_text(doc, encoding="utf-8")
    print(SIDE / name)


if __name__ == "__main__":
    main()
