"""Experiment 78: a specimen of a traced typeface (every letter isolated / initial / medial / final, beside Amiri),
to find wrong glyphs before the font is used (a wrong glyph would teach the reader a wrong label).

    python specimen78.py FONT.ttf OUT.png
"""
import sys
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

L = "ابتثجحخدذرزسشصضطظعغفقكلمنهويىةءأإآؤئ"
NONJ = set("اأإآدذرزوؤةءى")
p, out = sys.argv[1], sys.argv[2]
cm = TTFont(p).getBestCmap()
ref = ImageFont.truetype(sys.argv[3] if len(sys.argv) > 3 else
                         "/home/appuser/inkscript/experiments/78_synthetic_lines/out/fonts/amiri_Amiri-Regular.ttf", 34,
                         layout_engine=ImageFont.Layout.RAQM)
f = ImageFont.truetype(p, 40, layout_engine=ImageFont.Layout.RAQM)
small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
cols = 2
rows = (len(L) + cols - 1) // cols
im = Image.new("L", (1500, 64 * rows + 20), 255)
d = ImageDraw.Draw(im)
for k, c in enumerate(L):
    x0 = 1500 - (k % cols) * 750
    y = 50 + 64 * (k // cols)
    forms = [c, c + "م", "م" + c + "م", "م" + c] if c not in NONJ else [c, "م" + c, "م" + c + "م", c + c]
    s = "   ".join(forms)
    d.text((x0 - 10, y), s, font=f if ord(c) in cm else ref, fill=0 if ord(c) in cm else 160, anchor="rs",
           direction="rtl", language="ar")
    d.text((x0 - 400, y), s, font=ref, fill=90, anchor="rs", direction="rtl", language="ar")
    d.text((x0 - 740, y - 20), f"{k}", font=small, fill=0)
im.save(out)
