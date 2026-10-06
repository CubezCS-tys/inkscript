"""Contact sheet of judged boxes from experiment 21 (method cutter_new = today's src) for chosen letters.

    ../../.venv/bin/python look.py LETTERS bad|ok [limit]      -> out/look_<letters>_<which>.png
"""
import sys, json
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; E21 = HERE.parent / "21_better_boxes"
sys.path.insert(0, str(E21))
import judge21 as Q
J, R = Q.J, Q.R


def main(letters="مل", which="bad", limit="80"):
    S = Q.sample_with_new(); items, ref = Q.items_of(S); rows = json.load(open(E21 / "out/summary21.json"))["rows"]
    G = {k[:-3]: v for k, v in J.cached(R.MODEL).items() if k.endswith(":b2")}
    W = {R.wid(w): w for s, ws in S.items() for w in ws}
    tiles = []
    for r in rows:
        if r["m"] != "cutter_new" or r["ok"] is None or (which == "bad") == r["ok"] or r["letter"] not in letters: continue
        it = items[r["iid"]]; img = J.item_image(it); h = 120; img = cv2.resize(img, (int(img.shape[1] * h / img.shape[0]), h))
        img = cv2.copyMakeBorder(img, 0, 20, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(img, f"{len(tiles)} {r['w']} k{r['k']} {G[r['iid']]['verdict']}", (3, h + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
        tiles.append(img); print(len(tiles) - 1, r["w"], r["k"], W[r["w"]]["text"], r["letter"])
    tiles = tiles[:int(limit)]
    Wd = 1400; rows_, row, x = [], [], 0
    for img in tiles:
        img = img[:, :Wd]
        if x + img.shape[1] > Wd: rows_.append(row); row = []; x = 0
        row.append(img); x += img.shape[1] + 6
    if row: rows_.append(row)
    out = []
    for rr in rows_:
        line = np.full((142, Wd, 3), 255, np.uint8); x = 0
        for img in rr: line[:img.shape[0], x:x + img.shape[1]] = img; x += img.shape[1] + 6
        out.append(line)
    cv2.imwrite(str(HERE / f"out/look_{which}.png"), np.vstack(out))


if __name__ == "__main__":
    main(*sys.argv[1:])
