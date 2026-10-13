"""Referee-labelled lines -> a YOLO dataset (one object per Azure line, class = its label), split by document:
out/train/yolo/{images,labels}/{train,val}/ + data.yaml. Pages are shrunk to 1280 px on the long side (a line stays
~25 px tall). The 44 pilot pages (test) come from out/score_<referee>/ into split 'test' when present.
ROUND2=1: round 1's pages plus out/round2/labels (its documents split 9:1 the same way) into out/train/yolo2/;
round 1's val documents stay val, so the two runs are checked on the same pages plus round 2's own."""
import json, random, sys
from pathlib import Path
import cv2
import os
HERE = Path(__file__).parent; T = HERE / "out/train"; R2 = os.environ.get("ROUND2") == "1"; Y = T / ("yolo2" if R2 else "yolo")
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "38_parser"))
from score_layout import LABELS
SIDE = 1280


def write(split, pid, gray, lines, key):
    h, w = gray.shape; s = SIDE / max(h, w)
    (Y / "images" / split).mkdir(parents=True, exist_ok=True); (Y / "labels" / split).mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(Y / "images" / split / f"{pid}.jpg"), cv2.resize(gray, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 90])
    rows = []
    for l in lines:
        if l.get(key) not in LABELS: continue
        x0, y0, x1, y1 = l["box"]; x0, x1 = max(0, x0), min(w, x1); y0, y1 = max(0, y0), min(h, y1)
        if x1 - x0 < 2 or y1 - y0 < 2: continue
        rows.append(f"{LABELS.index(l[key])} {(x0 + x1) / 2 / w:.5f} {(y0 + y1) / 2 / h:.5f} {(x1 - x0) / w:.5f} {(y1 - y0) / h:.5f}")
    (Y / "labels" / split / f"{pid}.txt").write_text("\n".join(rows))


if __name__ == "__main__":
    labs = sorted((T / "labels").glob("*.json"))
    docs = sorted({f.stem.rsplit("_p", 1)[0] for f in labs}); rnd = random.Random(39); rnd.shuffle(docs)
    val = set(docs[: max(1, len(docs) // 10)])
    n = {"train": 0, "val": 0, "test": 0}
    if R2:
        R = HERE / "out/round2"; l2 = sorted((R / "labels").glob("*.json"))
        d2 = sorted({f.stem.rsplit("_p", 1)[0] for f in l2} - set(docs)); rnd.shuffle(d2); val |= set(d2[: max(1, len(d2) // 10)])
        labs += l2
    for f in labs:
        r = json.loads(f.read_text())
        if not r["lines"]: continue
        gray = cv2.imread(str(f.parent.parent / "pages" / f"{r['pid']}.jpg"), cv2.IMREAD_GRAYSCALE)
        split = "val" if r["pid"].rsplit("_p", 1)[0] in val else "train"
        write(split, r["pid"], gray, r["lines"], "label"); n[split] += 1
    test = HERE / "out/score_test"
    if test.exists():
        from common import page_image
        for f in sorted(test.glob("*.json")):
            r = json.loads(f.read_text())
            if "lines" in r: write("test", r["pid"], page_image(r["pid"]), r["lines"], "ref"); n["test"] += 1
    (Y / "data.yaml").write_text(f"path: {Y}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(LABELS)))
    print(n, "val documents:", len(val))
