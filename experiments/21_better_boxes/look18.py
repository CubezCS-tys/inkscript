"""Contact sheets of experiment 18's cutter boxes that the judge called wrong (or right), to see what is systematic.

    ../../.venv/bin/python look18.py [filter: C|0618|1036|alef] [ok|bad]   -> out/look_<filter>_<bad>.png
"""
import sys, json
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; E18 = HERE.parents[0] / "18_boxes"
sys.path.insert(0, str(E18))
import judge18 as J, run18 as R

def main(flt="C", which="bad", limit="48"):
    limit = int(limit)
    S = json.load(open(E18 / "out/sample.json")); items, ref = R.items_of(S)
    summ = json.load(open(E18 / "out/summary.json"))["words"]
    tiles = []
    for s, ws in S.items():
        for w in ws:
            for k in range(1, len(w["text"]) + 1):
                v = summ.get(f"{s}|{R.wid(w)}|cutter|{k}")
                if v is None: continue
                if (which == "bad") == v["ok"]: continue
                if flt in ("A", "B", "C") and s != flt: continue
                if flt in ("0618", "1036", "0772", "0582") and w["doc"] != flt: continue
                if flt == "alef" and not (w["text"][k - 1] == "ا" and w["joined"][k - 1] and k > 1 and w["piece_of"][k - 2] == w["piece_of"][k - 1]): continue
                it = items[ref[(s, R.wid(w), "cutter", k)]]
                img = J.item_image(it)
                h = 130; img = cv2.resize(img, (int(img.shape[1] * h / img.shape[0]), h))
                lab = f"{R.wid(w)} k{k} {v['g']} b{v['b']}"
                img = cv2.copyMakeBorder(img, 0, 22, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
                cv2.putText(img, lab, (3, h + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
                tiles.append((img, w["text"], k))
    tiles = tiles[:limit]
    print(len(tiles), "tiles")
    for t in tiles: print(t[1], t[2])
    W = 1400; rows = []; row = []; x = 0
    for img, _, _ in tiles:
        img = img[:, :W]
        if x + img.shape[1] > W: rows.append(row); row = []; x = 0
        row.append(img); x += img.shape[1] + 6
    if row: rows.append(row)
    out = []
    for r in rows:
        line = np.full((152, W, 3), 255, np.uint8); x = 0
        for img in r: line[:img.shape[0], x:x + img.shape[1]] = img; x += img.shape[1] + 6
        out.append(line)
    cv2.imwrite(str(HERE / f"out/look_{flt}_{which}.png"), np.vstack(out))

if __name__ == "__main__":
    main(*sys.argv[1:])
