"""Text the output keeps from the source PDF's own fonts on pages we rebuilt from the scan: on such pages every word
should come from our Type 3 ink glyphs; words in any other font (a stamped running head, a typeset footnote, a
junk-encoded font) are read by Chrome too, beside ours, so copying gives them twice and often garbled.
    .venv/bin/python experiments/28_scale/leftover.py   -> out/leftover.json
"""
import json, re
from pathlib import Path
import pymupdf
HERE = Path(__file__).resolve().parent; SET = HERE / "out" / "set"
res = {}
for rp in sorted(SET.glob("w*/native_pdf_report.json")):
    for r in json.loads(rp.read_text()):
        stem = r["doc"]; pdf = rp.parent / f"{stem}.pdf"
        if not pdf.exists(): continue
        d = pymupdf.open(str(pdf)); pages = {}
        for i, p in enumerate(r["pages"]):
            if str(p.get("text", "")).startswith("native"): continue
            c = {}
            for b in d[i].get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    for s in l["spans"]:
                        if s["font"].startswith("Type3"): continue
                        n = len(re.findall(r"\w{2,}", s["text"]))
                        if n: c.setdefault(s["font"], [0, ""]); c[s["font"]][0] += n; c[s["font"]][1] = (c[s["font"]][1] + " " + s["text"])[:80]
            if c: pages[i + 1] = c
        d.close()
        res[stem] = dict(pages_with_leftover=len(pages), words=sum(v[0] for c in pages.values() for v in c.values()),
                         fonts=sorted({f for c in pages.values() for f in c}), example=next(iter(pages.items()), None), of=len(r["pages"]))
(HERE / "out" / "leftover.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
bad = {k: v for k, v in res.items() if v["words"]}
print(len(bad), "of", len(res), "documents keep source text on rebuilt pages;", sum(v["pages_with_leftover"] for v in bad.values()), "pages,",
      sum(v["words"] for v in bad.values()), "words")
for k, v in sorted(bad.items(), key=lambda x: -x[1]["words"])[:15]:
    print(k, v["pages_with_leftover"], "/", v["of"], "pages", v["words"], "words", v["fonts"][:4], (v["example"] or ["", {}])[1] and list(v["example"][1].values())[0][1][:50])
