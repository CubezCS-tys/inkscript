"""Synthetic vowelled lines for round C: Quran verses (Tanzil simple text, fully vowelled, shipped in
src/inkscript/data/quran) cut into 4-9 word lines, set by MuPDF's HarfBuzz shaper in Amiri, Amiri Bold, Noto Naskh
Arabic and its bold, at 12-18 pt, rendered at 300 dpi, then a scan-like copy (degrade.py). Real silver lines give
almost no vowelled text (Azure's confidence on vowelled words is under the 0.9 the silver set asks for).
The rebuilt typefaces of experiment 11 are no longer on this machine, so they could not be used.

    out/env/bin/python synth.py [N=3000]   -> out/synth/<k>.png, <k>_d.jpg, .gt.txt beside each; out/lists/synth.txt
"""
import gzip, random, sys, zlib
from pathlib import Path
import numpy as np
import pymupdf
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from degrade import degrade
from textnorm import faithful

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); Q = Path(__file__).resolve().parents[2] / "src/inkscript/data/quran"
FONTS = {"amiri": "/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Regular.ttf",
         "amirib": "/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Bold.ttf",
         "naskh": "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
         "naskhb": "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"}


def render(text, font, size):
    doc = pymupdf.open(); page = doc.new_page(width=1400, height=90)
    css = f"@font-face {{font-family: f; src: url({Path(font).name});}} body {{font-family: f; font-size: {size}pt; direction: rtl; text-align: right;}}"
    page.insert_htmlbox(pymupdf.Rect(10, 5, 1390, 85), text, css=css, archive=pymupdf.Archive(str(Path(font).parent)))
    pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    im = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    ys, xs = np.where(im < 200)
    if len(xs) == 0:
        return None
    pad = int(0.25 * (ys.max() - ys.min()))
    return Image.fromarray(im[max(0, ys.min() - pad // 2): ys.max() + pad // 2, max(0, xs.min() - pad): xs.max() + pad])


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    verses = [l.rstrip("\n").split("|")[-1] for l in gzip.open(Q / "quran-simple.txt.gz", "rt", encoding="utf-8") if l.count("|") == 2]
    r = random.Random(33); (OUT / "synth").mkdir(exist_ok=True); paths = []
    k = 0
    while k < n:
        w = r.choice(verses).split()
        if len(w) < 4:
            continue
        a = r.randrange(0, max(1, len(w) - 4)); text = " ".join(w[a: a + r.randint(4, 9)])
        fname = r.choice(list(FONTS)); im = render(text, FONTS[fname], r.choice([12, 13, 14, 16, 18]))
        if im is None or im.width < 50:
            continue
        p = OUT / "synth" / f"s{k:05d}_{fname}"
        im.save(f"{p}.png", optimize=True); degrade(im, zlib.crc32(p.name.encode())).save(f"{p}_d.jpg", quality=70)
        for suf in ("", "_d"):
            Path(f"{p}{suf}.gt.txt").write_text(faithful(text) + "\n", encoding="utf-8")
        paths += [f"{p}.png", f"{p}_d.jpg"]; k += 1
    (OUT / "lists" / "synth.txt").write_text("\n".join(paths) + "\n")
    print(k, "lines,", len(paths), "images")
