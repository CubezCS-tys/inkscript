"""Experiment 59: the side-by-side page (scan | Reducto | ours), out/side/index.html.  No calls.

    /home/appuser/inkscript/experiments/58_indra_ocr/out/venv/bin/python side59.py      (that venv has OpenCV)

Each page: the scan with Reducto's r-1 blocks (colour = type, number = Reducto's reading order); the scan with our
structure (Azure's lines coloured by Gemini's role, number = our block order); then the text: Reducto's and Azure's,
words that differ from the truth (truth pages) or from each other (other pages) marked; on metadata / citation pages
also Reducto Extract's fields beside our masters'.
"""
import html
import json
import re
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "58_indra_ocr"))
from side58 import COL, GCOL, LEGEND, put, draw_ours, marked, truth_lines  # noqa: E402

OUT = HERE / "out"
SIDE = OUT / "side"
(SIDE / "img").mkdir(parents=True, exist_ok=True)
RCOL = {"Text": "Text", "Title": "Section-Header", "Section Header": "Section-Header", "Header": "Page-Header",
        "Footer": "Page-Footer", "Page Number": "Page-Footer", "List Item": "List-Group", "Table": "Table",
        "Figure": "Picture", "Key Value": "Form"}

PAGES = [  # (id, kind, why)
    ("0407-009-001-028_p003", "truth", "owner gold page, two Arabic columns: Reducto reads the left column first"),
    ("0656-016-001-011_p003", "truth", "owner gold page, 1960s print: the hardest old print"),
    ("7956-000-000-016_p001", "truth", "born-digital Arabic page: Reducto has fewer wrong words than Azure"),
    ("1148-041-116-018_p004", "truth", "born-digital Arabic page with tables and formulas"),
    ("0596-037-437-020_p001", "lay", "metadata page, two Arabic columns and a display title"),
    ("0829-013-025-033_p027", "lay", "two columns of Arabic footnotes: Reducto types them List Item"),
    ("0913-000-001-011_p021", "lay", "Arabic reference list (citations 54 and 56: editor, edition, Hijri dates)"),
    ("1717-006-001-005_p001", "lay", "French first page: title, two authors, affiliations, two abstracts"),
]


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def image_of(pid, kind):
    return (E / "41_azure_structure/out/pages" if kind == "truth" else E / "43_rehearsal/out/pages") / f"{pid}.jpg"


def save(img, name, w=900):
    s = w / img.shape[1]
    img = cv2.resize(img, (w, int(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(SIDE / "img" / name), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return f"img/{name}"


def blocks(pid):
    j = jl(OUT / "reducto/r1" / f"{pid}.json")
    return [b for ch in j["chunks_full"] for b in ch["blocks"]]


def strip_html(s):
    s = re.sub(r"</t[dh]>|<br\s*/?>|</tr>", " ", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def draw_reducto(img, bl):
    H, W = img.shape[:2]
    out, over = img.copy(), img.copy()
    boxes = []
    for b in bl:
        bb = b["bbox"]
        x0, y0 = int(bb["left"] * W), int(bb["top"] * H)
        x1, y1 = int((bb["left"] + bb["width"]) * W), int((bb["top"] + bb["height"]) * H)
        c = COL.get(RCOL.get(b["type"], "Form"), (0, 0, 0))
        boxes.append((x0, y0, x1, y1, c))
        cv2.rectangle(over, (x0, y0), (x1, y1), c, -1)
    out = cv2.addWeighted(over, 0.22, out, 0.78, 0)
    for k, (x0, y0, x1, y1, c) in enumerate(boxes, 1):
        cv2.rectangle(out, (x0, y0), (x1, y1), c, 4)
        put(out, k, x1 + 4 if x1 < W - 60 else x1 - 60, y0 + 34, c)
    return out


def ex_rows(pid):
    """Reducto Extract (deep) next to nothing: a compact field list"""
    rows = []
    for kind in ("meta_deep", "refs_deep"):
        f = OUT / "extract" / kind / f"{pid}.json"
        if not f.exists():
            continue
        r = jl(f)["result"]
        r = r[0] if isinstance(r, list) else r

        def val(x):
            if isinstance(x, dict) and "value" in x and "citations" in x:
                return val(x["value"])
            if isinstance(x, dict):
                return {k: val(v) for k, v in x.items() if val(v) not in (None, "", [], {})}
            if isinstance(x, list):
                return [val(v) for v in x]
            return x
        v = val(r)
        if kind.startswith("refs"):
            for e in (v.get("references") or [])[:12]:
                e = {k: x for k, x in e.items() if k not in ("raw_text", "where", "is_back_reference")}
                rows.append(html.escape(json.dumps(e, ensure_ascii=False)))
        else:
            for k, x in v.items():
                s = json.dumps(x, ensure_ascii=False)
                rows.append(f"<b>{html.escape(k)}</b>: {html.escape(s[:400])}")
    return rows


def main():
    lay = {}
    want = {p for p, k, _ in PAGES if k == "lay"}
    for line in open(E / "58_indra_ocr/out/layout_lines.jsonl", encoding="utf-8"):
        if any(w in line[:60] for w in want):
            d = json.loads(line)
            if d["id"] in want:
                lay[d["id"]] = d
    az_truth = jl(E / "58_indra_ocr/out/azure_truth34.json")
    ts = jl(OUT / "text_scores.json")
    trow = {r["id"]: r for r in ts["rows"]}
    secs = []
    for pid, kind, why in PAGES:
        img = cv2.imread(str(image_of(pid, kind)))
        bl = blocks(pid)
        a = save(draw_reducto(img, bl), f"{pid}_reducto.jpg")
        rl = [ln.strip() for b in bl if b["type"] != "Figure" for ln in strip_html(b["content"]).split("\n") if ln.strip()]
        extra = ""
        if kind == "truth":
            az = [l["text"] for l in az_truth[pid]]
            ref_words = [w for t in truth_lines(pid) for w in t.split()]
            rh, rb, rw = marked(rl, ref_words)
            ah, ab, aw = marked(az, ref_words)
            right_img = ("Scan", save(img, f"{pid}_scan.jpg"))
            r = trow.get(pid, {})
            pct = lambda k: f"{100 * r[k]['bag_err'] / max(r[k]['bag_n'], 1):.1f}%" if k in r else "-"
            note = (f"Words marked: differ from the hand-checked truth (aligned in reading order, vowel marks and letter forms "
                    f"folded, so a reading-order difference also marks words). Words wrong (exp 41's measure): Reducto r-1 "
                    f"{pct('reducto/r1')}, with the 'as printed' prompt {pct('reducto/r1_verbatim')}, Azure {pct('azure')}.")
        else:
            d = lay[pid]
            az = [l["t"] for l in sorted(d["lines"], key=lambda l: (l["go"] is None, l["go"] or 0))]
            rh, rb, rw = marked(rl, [w for t in az for w in t.split()])
            ah, ab, aw = marked(az, [w for t in rl for w in t.split()])
            right_img = ("Ours: Azure's lines, Gemini's roles and order", save(draw_ours(img, d["lines"]), f"{pid}_ours.jpg"))
            note = (f"No truth for this page: words marked where Reducto and Azure disagree (Azure in our reading order). "
                    f"Reducto {rb} of {rw} marked, Azure {ab} of {aw}.")
            rows = ex_rows(pid)
            if rows:
                extra = ('<details open><summary>Reducto Extract (deep), fields as returned</summary><ul class="ex" dir="auto">'
                         + "".join(f"<li>{x}</li>" for x in rows) + "</ul></details>")
        secs.append(f"""
<section class="pg"><h2>{html.escape(pid)} <small>{html.escape(why)}</small></h2>
<div class="row">
 <figure><figcaption>Reducto r-1: blocks by type, numbers = its reading order</figcaption><img src="{a}" alt="Reducto blocks on {pid}" loading="lazy"></figure>
 <figure><figcaption>{right_img[0]}</figcaption><img src="{right_img[1]}" alt="{pid}" loading="lazy"></figure>
</div>
<p class="note">{note}</p>
<div class="row txt">
 <div><h3>Reducto r-1 (hosted API)</h3><div class="t" dir="auto">{rh}</div></div>
 <div><h3>Azure (our text){' in our reading order' if kind == 'lay' else ''}</h3><div class="t" dir="auto">{ah}</div></div>
</div>{extra}</section>""")
    leg = "".join(f'<span><i style="background:rgb{COL[k][::-1]}"></i>{html.escape(n)}</span>' for n, k in LEGEND)
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reducto side by side</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a64;--line:#dedbd2;--mark:#ffd5cf}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#1b1b19;--fg:#ecebe6;--mute:#a3a29b;--line:#3a3935;--mark:#7a2e26}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1900px;padding:16px}}
h1{{font-size:22px;margin:4px 0}} h2{{font-size:17px;margin:28px 0 8px;border-top:1px solid var(--line);padding-top:14px}}
h2 small{{color:var(--mute);font-weight:400;margin-left:8px}} h3{{font-size:14px;margin:6px 0;color:var(--mute)}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} figure{{margin:0}} figcaption{{color:var(--mute);font-size:13px}}
img{{width:100%;height:auto;border:1px solid var(--line)}}
.t{{font-family:"Noto Naskh Arabic","Scheherazade New",serif;font-size:17px;line-height:1.8;border:1px solid var(--line);padding:8px 12px;max-height:620px;overflow:auto}}
mark{{background:var(--mark);color:inherit;border-radius:2px}} .note{{color:var(--mute);font-size:13px}}
.sum{{border:1px solid var(--line);padding:10px 14px;margin:10px 0;font-size:14px}}
.ex{{font-size:13px;line-height:1.6}} details{{margin-top:8px}}
.legend span{{margin-right:14px;font-size:13px;white-space:nowrap}} .legend i{{display:inline-block;width:12px;height:12px;margin-right:4px;vertical-align:-1px}}
@media (max-width:800px){{.row{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Reducto beside our pipeline (experiment 59)</h1>
<p class="note">Reducto's hosted API, 49 approved pages (Standard tier: no zero retention, no deletion; see README). Colours are the same on both scans: <span class="legend">{leg}</span></p>
<div class="sum"><b>In short (README for the numbers and method).</b> Text on 22 hand-checked pages: words wrong Reducto r-1 5.2%,
with an "as printed" prompt 3.5%, Azure 2.3% (born-digital pages: 2.2% with the prompt against Azure's 2.7%); it retypes some
letters (ى→ي, hamza added or dropped). Two-column Arabic prose pages: the left column read first on all 6 sent. Footnotes come out
as list items. Citations (20 of the proof pack's 80): fully right Reducto deep 15, standard 13, ours 12. Page-1 metadata (12): ours 11, Reducto 7 / 6.</div>
{''.join(secs)}
</body></html>"""
    (SIDE / "index.html").write_text(doc, encoding="utf-8")
    print(SIDE / "index.html")


if __name__ == "__main__":
    main()
