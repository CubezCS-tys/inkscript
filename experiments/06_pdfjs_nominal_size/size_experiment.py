"""Nominal font size vs the two engines: pdfium (Chrome) words/order; pdf.js (Firefox) words intact and lines in logical word order."""
import json, re, sys, subprocess, unicodedata
from pathlib import Path
import inkscript.pdf.type3 as t3
from inkscript.pdf.native import build_document
from inkscript.verify.engines import pdfium_words, pdfium_order
from inkscript.text import norm, ARABIC
S = Path(sys.argv[1]); O = Path("/home/cubez/Desktop/OCR_gem_json/output")
DOCS = sys.argv[2].split("+"); SIZES = [float(x) for x in sys.argv[3:]]
N = lambda s: unicodedata.normalize("NFKC", s)
def edge(t):
    while t and unicodedata.category(t[0])[0] in "PSZ": t = t[1:]
    while t and unicodedata.category(t[-1])[0] in "PSZ": t = t[:-1]
    return t
def toks(s): return [edge(x) for x in N(s).split() if edge(x)]
def sub(seq, big):
    n = len(seq)
    return any(big[i:i + n] == seq for i in range(len(big) - n + 1))
for size in SIZES:
    t3.SIZE_PT = abs(size); t3.SIZE_MODE = "gap" if size < 0 else "fixed"
    tot = dict(tw=0, ti=0, inv=0, jt=0, jw=0, ok=0, rev=0, other=0)
    for stem in DOCS:
        out = S / f"size_{size:g}" / stem; out.mkdir(parents=True, exist_ok=True)
        r = build_document(stem, O / "bakeoff_full/azure", O / "bakeoff_full/input" / f"{stem}.pdf", O / "frontpage_set" / f"{stem}.gemini.p1.md", out, False, 0.6)
        pdf = out / f"{stem}.pdf"
        v = pdfium_words(pdf, r, O / "bakeoff_full/azure"); tot["tw"] += sum(x["words"] for x in v); tot["ti"] += sum(x["intact"] for x in v)
        inv, _ = pdfium_order(pdf); tot["inv"] += inv
        raw = subprocess.run(["node", "words.mjs", str(pdf)], cwd=S / "pdfjs", capture_output=True, text=True).stdout
        js = {p["page"]: p["text"] for p in json.loads([l for l in raw.splitlines() if l.startswith("[")][-1])}
        for pi in r["pages"]:
            if not pi.get("glyphs"): continue
            placed = [edge(x) for x in map(N, pi["placed"]) if edge(x)]
            t = re.sub(r"[‎‏‪-‮]", "", N(js[pi["page"]]))
            got = {edge(x) for x in t.split()}
            tot["jt"] += len(placed); tot["jw"] += sum(1 for x in placed if x in got)
            import pypdfium2 as pdfium
            pd = pdfium.PdfDocument(str(pdf)); pt = N(pd[pi["page"] - 1].get_textpage().get_text_range()); pd.close()
            pl = {tuple(x for x in toks(l) if ARABIC.search(x)) for l in re.sub(r"[\u200e\u200f\u202a-\u202e]", "", pt).replace("\r\n", "\n").split("\n")}
            shown = 0
            for l in t.split("\n"):
                w = [x for x in toks(l) if ARABIC.search(x)]
                if len(w) < 3: continue
                if tuple(w) in pl: tot["ok"] += 1
                elif tuple(w[::-1]) in pl: tot["rev"] += 1
                else:
                    tot["other"] += 1
                    if size < 0 and shown < 3: shown += 1; print("   other:", " ".join(w)[:90])
    n = tot["ok"] + tot["rev"] + tot["other"]
    print(f"size {size:>4g}pt | pdfium {tot['ti']/tot['tw']:.1%} intact, {tot['inv']} inversions | pdf.js words {tot['jw']/tot['jt']:.1%}; lines: {tot['ok']/n:.0%} same as Chrome, {tot['rev']/n:.0%} reversed, {tot['other']/n:.0%} other (n={n})", flush=True)
