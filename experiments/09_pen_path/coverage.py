"""Share of Arabic words (2+ letters, no vowel marks) in which every letter has its own selection box in Chrome's
engine (a lam-alef ligature counts as one). python coverage.py <pdf> [--list]"""
import sys, re, pypdfium2 as pdfium
a = pdfium.PdfDocument(sys.argv[1]); cut = whole = 0; missed = []
for pi in range(len(a)):
    tp = a[pi].get_textpage(); t = tp.get_text_range(); k = 0
    for w in re.split(r"(\s+)", t):
        if re.fullmatch(r"[ء-ي]{2,}", w):
            boxes = {tuple(round(v, 1) for v in tp.get_charbox(k + m)) for m in range(len(w))}; lig = len(re.findall("لا|لأ|لإ|لآ", w))
            if len(boxes) >= len(w) - lig: cut += 1
            else: whole += 1; missed.append((pi + 1, w, len(boxes)))
        k += len(w)
print(f"words where every letter has its own box: {cut} of {cut + whole} ({100 * cut / max(1, cut + whole):.1f}%)")
if "--list" in sys.argv:
    for pg, w, n in missed[:80]: print(f"  p{pg} {w}: {n} boxes for {len(w)} letters")
