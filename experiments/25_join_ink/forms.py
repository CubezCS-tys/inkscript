"""Draw pieces in which a given letter-form occurs (replayed plans of a variant): forms.py VARIANT DOC LETTER FORM NAME [N]"""
import sys
from common import *

variant, doc, letter, form, name = sys.argv[1:6]; N = int(sys.argv[6]) if len(sys.argv) > 6 else 30
tiles = []
for p in load(variant, doc):
    if any(P._base(u) == letter and f == form for u, f in zip(p["units"], p["forms"])):
        tiles.append(label(draw_piece(p, 3), "".join(p["units"])[::-1] and f"{len(tiles)}"))
        if len(tiles) >= N: break
cv2.imwrite(str(HERE / f"out/forms_{name}.png"), grid(tiles, 1400))
