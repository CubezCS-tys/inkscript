"""Ground-truth files and image lists for fine-tuning and testing.

    out/env/bin/python make_train.py
From out/data.jsonl: writes <image>.gt.txt beside every train/dev image (the faithful text: see textnorm.py; digits
are written as Western digits whatever the print shows, because a born-digital PDF does not say which it drew) and
the lists out/lists/{train,dev,test_clean,test_deg}.txt. Train = clean + scan-like copy of every train line;
dev = the scan-like copies plus a third of the clean lines.
"""
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import faithful

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out")
data = [json.loads(l) for l in open(OUT / "data.jsonl")]
(OUT / "lists").mkdir(exist_ok=True)
lists = {k: [] for k in ("train", "dev", "test_clean", "test_deg")}
r = random.Random(33)
for d in data:
    base = OUT / "img" / d["split"] / d["id"]
    g = faithful(d["gold"])
    if not g:
        continue
    if d["split"] == "test":
        lists["test_clean"].append(f"{base}.png"); lists["test_deg"].append(f"{base}_d.jpg"); continue
    for img, use in ((f"{base}.png", d["split"] == "train" or r.random() < 1 / 3), (f"{base}_d.jpg", True)):
        if use:
            Path(img.rsplit(".", 1)[0] + ".gt.txt").write_text(g + "\n", encoding="utf-8")
            lists[d["split"]].append(img)
for k, v in lists.items():
    (OUT / "lists" / f"{k}.txt").write_text("\n".join(v) + "\n")
    print(k, len(v))
