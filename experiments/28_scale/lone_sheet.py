"""A contact sheet of a random sample of the 'lone' furniture blocks (furniture.py), each cropped from the scan with
a margin, to judge by eye whether it is furniture or content.  -> out/look/lone_sheet_N.png, out/lone_sample.json"""
import json, random, re
from pathlib import Path
import pymupdf
from lxml import etree
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; SET = OUT / "set"
A = "{http://www.loc.gov/standards/alto/ns-v4#}"
norm = lambda s: re.sub(r"[^ء-يa-zA-Z]", "", s or "")
from collections import Counter
items = []
for f in sorted(SET.glob("w*/*.alto.xml")):
    stem = f.name[:-9]; t = etree.parse(str(f)); bl = []
    for pg in t.iter(A + "Page"):
        W, H = float(pg.get("WIDTH")), float(pg.get("HEIGHT"))
        for b in pg.iter(A + "TextBlock"):
            r = b.get("TAGREFS") or ""
            if any(x in r for x in ("pageHeader", "pageFooter", "pageNumber")):
                txt = " ".join(s.get("CONTENT") for s in b.iter(A + "String"))
                bl.append((stem, int(pg.get("PHYSICAL_IMG_NR")), txt, [float(b.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")], W, H))
    c = Counter(norm(x[2]) for x in bl)
    items += [x for x in bl if len(norm(x[2])) >= 3 and c[norm(x[2])] <= 2]
random.Random(28).shuffle(items); sample = items[:24]
json.dump([dict(doc=s, page=p, text=t, box=b) for s, p, t, b, W, H in sample], open(OUT / "lone_sample.json", "w"), ensure_ascii=False, indent=1)
for k in range(0, len(sample), 12):
    out = pymupdf.open(); sp = out.new_page(width=2 * 600, height=6 * 150)
    for i, (s, p, t, b, W, H) in enumerate(sample[k:k + 12]):
        d = pymupdf.open(str(OUT / "azure" / s / f"{s}.pdf")); pg = d[p - 1]; R = pg.rect; sx, sy = R.width / W, R.height / H
        y0 = max(0, b[1] - 3 * b[3]); y1 = min(H, b[1] + 4 * b[3])
        clip = pymupdf.Rect(0, y0 * sy, R.width, y1 * sy)
        x, y = (i % 2) * 600, (i // 2) * 150
        sp.show_pdf_page(pymupdf.Rect(x + 4, y + 4, x + 596, y + 128), d, p - 1, clip=clip)
        rr = pymupdf.Rect(x + 4 + b[0] * sx / R.width * 592, y + 4 + (b[1] - y0) * sy / clip.height * 124, x + 4 + (b[0] + b[2]) * sx / R.width * 592, y + 4 + (b[1] + b[3] - y0) * sy / clip.height * 124)
        sp.draw_rect(rr, color=(1, 0, 0), width=1.2)
        sp.insert_text((x + 6, y + 142), f"{k + i}: {s} p{p}", fontsize=9)
    sp.get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(str(OUT / "look" / f"lone_sheet_{k // 12}.png"))
print(len(items), "lone blocks; sample of", len(sample))
for i, (s, p, t, b, W, H) in enumerate(sample): print(i, s, p, t[:60])
