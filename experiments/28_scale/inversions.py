"""Order inversions per page (the build's pdfium_order rule, page by page), with the lines around each jump.
    .venv/bin/python experiments/28_scale/inversions.py PDF [--show N]"""
import re, statistics, sys
import pypdfium2 as pdfium
doc = pdfium.PdfDocument(sys.argv[1]); show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 0
good = re.compile(r"[؀-ۿﭐ-﷿ﹰ-﻿A-Za-z0-9]")
per = {}
for pn in range(len(doc)):
    pg = doc[pn]; tp = pg.get_textpage(); t = tp.get_text_range(); lines, cur, txt, texts = [], [], "", []
    def close():
        if cur and len(good.findall(txt)) >= 0.5 * len(txt.replace(" ", "")):
            lines.append(list(cur)); texts.append(txt)
    for k, c in enumerate(t):
        if c in "\r\n":
            close(); cur = []; txt = ""; continue
        if c.strip(): cur.append(tp.get_charbox(k)); txt += c
    close()
    base = [statistics.median(b[1] for b in L) for L in lines]; h = [statistics.median(b[3] - b[1] for b in L) for L in lines]
    xr = [(min(b[0] for b in L), max(b[2] for b in L)) for L in lines]
    same = lambda i, j: min(xr[i][1], xr[j][1]) - max(xr[i][0], xr[j][0]) > 0.3 * min(xr[i][1] - xr[i][0], xr[j][1] - xr[j][0])
    inv = [i for i in range(len(base) - 1) if base[i + 1] > base[i] + 0.5 * h[i] and same(i, i + 1)]
    if inv:
        per[pn + 1] = len(inv)
        if show and len(per) <= show:
            for i in inv[:3]:
                print(f"p{pn + 1}: '{texts[i][:50]}' (y {base[i]:.0f}) -> '{texts[i + 1][:50]}' (y {base[i + 1]:.0f})")
    tp.close(); pg.close()
doc.close()
print(sum(per.values()), "inversions on", len(per), "pages:", sorted(per.items(), key=lambda x: -x[1])[:15])
