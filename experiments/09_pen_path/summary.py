"""Totals for a built set: text checks from the build report, letter coverage from the PDFs, reasons pieces were doubted.
python summary.py <native_dir> [<native_dir> ...]"""
import sys, json, glob, os, re
from collections import Counter
import pypdfium2 as pdfium

def coverage(pdf, ours):
    """Only the pages this build wrote: a born-digital page keeps its own fonts, and its letter boxes are not our work."""
    a = pdfium.PdfDocument(pdf); cut = whole = 0
    for pi in range(len(a)):
        if pi + 1 not in ours: continue
        page = a[pi]; tp = page.get_textpage(); t = tp.get_text_range(); k = 0
        for w in re.split(r"(\s+)", t):
            if re.fullmatch(r"[ء-ي]{2,}", w):
                boxes = {tuple(round(v, 1) for v in tp.get_charbox(k + m)) for m in range(len(w))}; lig = len(re.findall("لا|لأ|لإ|لآ", w))
                if len(boxes) >= len(w) - lig: cut += 1
                else: whole += 1
            k += len(w)
        tp.close(); page.close()                                     # 227 documents left open took the machine's memory
    a.close()
    return cut, cut + whole

rows = []; why = Counter(); reps = []
for d in sys.argv[1:]:
    for f in glob.glob(f"{d}/**/native_pdf_report.json", recursive=True):
        r = json.load(open(f)); reps += r if isinstance(r, list) else r.get("documents", [])
for r in reps:
    stem = r.get("stem") or r.get("doc") or r.get("id"); pdf = next((p for d in sys.argv[1:] for p in glob.glob(f"{d}/**/{stem}_vector.pdf", recursive=True)), None)
    if not pdf: continue
    ours = {p["page"] for p in r.get("pages", []) if p.get("glyphs", 0) > 0 and p.get("text") != "native-digital"}
    c, n = coverage(pdf, ours); v = r.get("verify") or {}; why.update(r.get("letters_why") or {})
    rows.append(dict(stem=stem, pages=len(ours), born_digital=len(r.get("pages", [])) - len(ours), cut=c, words=n, verify=v, letters=(r.get("letters") or {}).get("accepted", 0)))
rows.sort(key=lambda x: x["cut"] / max(1, x["words"]))
C = sum(x["cut"] for x in rows); N = sum(x["words"] for x in rows)
rows = [x for x in rows if x["pages"]] if True else rows
print(f"{len(rows)} scanned documents, {sum(x['pages'] for x in rows)} pages we wrote (born-digital pages left alone: {sum(x['born_digital'] for x in rows)} in these documents)")
print(f"Arabic words in which every letter has its own box: {C} of {N} ({100 * C / max(1, N):.1f}%)")
cov = sorted(100 * x["cut"] / max(1, x["words"]) for x in rows if x["words"] >= 50)
if cov: print(f"per document (50+ words): median {cov[len(cov) // 2]:.1f}%, worst tenth under {cov[len(cov) // 10]:.1f}%, best tenth over {cov[-max(1, len(cov) // 10)]:.1f}%; documents under 50%: {sum(c < 50 for c in cov)}")
print("pieces by verdict:", dict(why.most_common()))
print("lowest coverage:"); [print(f"  {x['stem']}: {x['cut']}/{x['words']} ({100 * x['cut'] / max(1, x['words']):.0f}%), {x['pages']} pages") for x in rows[:15]]
json.dump(rows, open(os.path.join(sys.argv[1], "letter_coverage.json"), "w"), ensure_ascii=False, indent=1)
