"""Big drawings of chosen sample words: ink by letter, pen path, candidate cuts (grey ticks with their path index),
chosen cuts (red).   zoom.py VARIANT NAME WORDID..."""
import sys
from common import *

variant, name, wids = sys.argv[1], sys.argv[2], sys.argv[3:]
W = words(); tiles = []
for wid in wids:
    s, w = W[wid]
    for k, (idx, p) in match(w, variant).items():
        sc = int(sys.argv[0] and 5); img = draw_piece(p, sc)
        for c in p.get("cand", []):
            y, x = p["trunk"][c]; cv2.circle(img, (x * sc + 3, y * sc + 3), 4, (150, 150, 150), 1)
            cv2.putText(img, str(c), (x * sc + 5, y * sc - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (90, 90, 90), 1)
        for c in p["cuts"]:
            y, x = p["trunk"][c]; cv2.circle(img, (x * sc + 3, y * sc + 3), 5, (0, 0, 255), 2)
        y, x = p["trunk"][0]; cv2.putText(img, "L", (x * sc, y * sc), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        tiles.append(label(img, f"{wid} {''.join(p['units'])} cuts {p['cuts']} S={p['G']['W']} sc={[round(x,2) if x is not None else None for x in (p.get('scores') or [])]}"))
cv2.imwrite(str(HERE / f"out/zoom_{name}.png"), grid(tiles, 1600))
