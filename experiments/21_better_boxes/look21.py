"""Contact sheet of judged boxes from summary21 (any method), to see what is left.

    ../../.venv/bin/python look21.py METHOD(cutter|cutter_new|equal) bad|ok [alef|C|0618|...] [limit]
"""
import sys, json
import numpy as np, cv2
import judge21 as Q
J, R = Q.J, Q.R


def main(m="cutter_new", which="bad", flt="", limit="60"):
    S = Q.sample_with_new(); items, ref = Q.items_of(S); rows = json.load(open(Q.OUT / "summary21.json"))["rows"]
    G, B = {}, {}
    for k, v in J.cached(R.MODEL).items():
        (G if k.endswith(":b2") else B)[k[:-3]] = v
    tiles = []
    for r in rows:
        if r["m"] != m or r["ok"] is None or (which == "bad") == r["ok"]: continue
        if flt == "alef" and not r["alef"]: continue
        if flt in ("A", "B", "C") and r["s"] != flt: continue
        if flt[:1].isdigit() and not r["w"].startswith(flt): continue
        it = items[r["iid"]]; img = J.item_image(it); h = 120; img = cv2.resize(img, (int(img.shape[1] * h / img.shape[0]), h))
        img = cv2.copyMakeBorder(img, 0, 20, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(img, f"{r['w']} k{r['k']} {G[r['iid']]['verdict']} {B[r['iid']].get('marked','')[:0]}", (3, h + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
        tiles.append(img)
    tiles = tiles[:int(limit)]; print(len(tiles))
    W = 1400; rows_ = []; row = []; x = 0
    for img in tiles:
        img = img[:, :W]
        if x + img.shape[1] > W: rows_.append(row); row = []; x = 0
        row.append(img); x += img.shape[1] + 6
    if row: rows_.append(row)
    out = []
    for rr in rows_:
        line = np.full((142, W, 3), 255, np.uint8); x = 0
        for img in rr: line[:img.shape[0], x:x + img.shape[1]] = img; x += img.shape[1] + 6
        out.append(line)
    cv2.imwrite(str(Q.OUT / f"look21_{m}_{which}_{flt}.png"), np.vstack(out))


if __name__ == "__main__":
    main(*sys.argv[1:])
