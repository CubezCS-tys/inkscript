"""Which sampled documents are scans (Azure's reading is their only text) and which are born-digital?

A page is born-digital by the pipeline's own rule (src/inkscript/pdf/native.py `born_digital`: real embedded fonts carry
at least half as many readable words as Azure's invisible `Dummy` layer). A document is born-digital when most of its
pages are. Also records, per document: pages, Azure words, sideways pages (Azure page angle beyond 45 degrees),
and the metadata's journal/year.  -> out/docs.json
"""
import json, sys
from pathlib import Path
import pymupdf
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
from inkscript.pdf.native import born_digital, text_words

meta = json.load(open(OUT / "meta.json"))
rows = {}
for i in [l.strip() for l in open(OUT / "ids.txt") if l.strip()]:
    d = OUT / "docs" / i; pdf, js = d / f"{i}.pdf", d / f"{i}.json"
    r = dict(id=i, **meta.get(i, {}))
    try:
        doc = pymupdf.open(str(pdf)); nb = 0; fonts = set(); junk = 0
        for pg in doc:
            nb += born_digital(pg); fonts |= {f[3] for f in pg.get_fonts()}
            real, dummy = text_words(pg)
        r.update(pages=len(doc), bd_pages=nb, fonts=sorted(fonts)[:8], only_dummy=fonts <= {"Dummy"})
        j = json.load(open(js)); ar = j.get("analyzeResult", j)
        r.update(words=sum(len(p.get("words", [])) for p in ar["pages"]),
                 sideways=sum(abs(p.get("angle") or 0) > 45 for p in ar["pages"]),
                 angles=[round(p.get("angle") or 0, 1) for p in ar["pages"]][:60])
        r["kind"] = "born-digital" if nb > len(doc) / 2 else ("scan" if r["only_dummy"] else "scan+real-font")
    except Exception as e:
        r["kind"] = "error"; r["err"] = str(e)[:200]
    rows[i] = r
json.dump(rows, open(OUT / "docs.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(r["kind"] for r in rows.values()))
print("pages", sum(r.get("pages", 0) for r in rows.values()), "sideways pages", sum(r.get("sideways", 0) for r in rows.values()))
