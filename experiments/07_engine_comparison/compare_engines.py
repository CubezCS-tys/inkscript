"""Same page, three text layers, one reader (pdfium = Chrome): ours, Azure's searchable PDF, ocrmypdf/Tesseract.
Reference = the words and lines our layer placed (Azure/Gemini reading, lines by position)."""
import json, re, sys, unicodedata
from pathlib import Path
import pypdfium2 as pdfium
from inkscript.text import norm, ARABIC_LETTER, _class
O = Path("/home/cubez/Desktop/OCR_gem_json/output"); S = Path(sys.argv[1])
N = lambda s: unicodedata.normalize("NFKC", s)
def edge(t):
    while t and unicodedata.category(t[0])[0] in "PSZ": t = t[1:]
    while t and unicodedata.category(t[-1])[0] in "PSZ": t = t[:-1]
    return t
def key(line): return tuple(x for x in (edge(w) for w in N(line).split()) if x and ARABIC_LETTER.search(x))
def latin_majority(text):
    segs = [_class(c) for c in N(text)]; runs = [d for i, d in enumerate(segs) if i == 0 or segs[i - 1] != d]
    return runs.count("L") > runs.count("R")
def measure(pdf, report):
    doc = pdfium.PdfDocument(str(pdf)); tw = ti = tl = tok = 0
    for pi in report["pages"]:
        if not pi.get("glyphs"): continue
        t = re.sub(r"[‎‏‪-‮]", "", N(doc[pi["page"] - 1].get_textpage().get_text_range())).replace("\r\n", "\n")
        got = {edge(x) for x in t.split()}
        want = [x for x in (edge(x) for tt in pi["placed"] for x in N(tt).split() if norm(x)) if x]
        tw += len(want); ti += sum(1 for x in want if x in got)
        lines = [key(l) for l in t.split("\n")]
        for r in pi["runs"]:
            k = key(r)
            if len(k) < 3 or latin_majority(r): continue
            tl += 1; n = len(k)
            tok += any(l[i:i + n] == k for l in lines if len(l) >= n for i in range(len(l) - n + 1))
    doc.close(); return tw, ti, tl, tok
reps = {r["doc"]: r for r in json.load(open(O / "native_set/native_pdf_report.json"))}
print(f"{'document':24s} {'layer':10s} {'words intact':>18s} {'lines in order':>18s}")
for stem in sys.argv[2:]:
    r = reps[stem]
    for label, pdf in [("inkscript", O / f"native_set/{stem}.pdf"), ("azure", O / f"bakeoff_full/azure/{stem}/{stem}.pdf"), ("ocrmypdf", S / f"ocrmypdf/{stem}.pdf")]:
        if not pdf.exists(): print(f"{stem:24s} {label:10s} (missing)"); continue
        tw, ti, tl, tok = measure(pdf, r)
        print(f"{stem:24s} {label:10s} {ti:>7d}/{tw:<6d} {ti/max(1,tw):6.1%} {tok:>7d}/{tl:<6d} {tok/max(1,tl):6.1%}")
