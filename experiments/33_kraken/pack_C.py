"""Round C's training material, packed for upload (line images + .gt.txt; compiled on the GPU machine).

    out/env/bin/python pack_C.py     -> out/C.tar (C/train/..., C/dev/..., C/train.txt, C/dev.txt)
Aim: old prints, footnotes and vowelled lines, without forgetting the rest. Every journal held out by experiment 34
is already out of silver_data.py's set; rounds C start from round A's models, which never saw one.
train: all pre-1970 silver lines; all small-print silver lines; 4,000 other silver lines; 1,500 synthetic vowelled
       lines (clean and scan-like); replay of 3,000 born-digital lines as scan-like copies and 1,000 clean.
dev:   600 born-digital dev images; 600 silver dev lines; the last 300 synthetic lines (both copies).
Every image is scaled to 96 px high and stored as JPEG quality 70 (near the lines' own height at 300 dpi, and the
PP-OCRv6 input height): this machine's upload to the rented GPUs ran at 0.15 MB/s tonight, so the pack must stay
near 100 MB.
"""
import json, random, shutil, tarfile
from PIL import Image
from pathlib import Path

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); C = OUT / "C"
r = random.Random(33)
sil = [json.loads(l) for l in open(OUT / "silver" / "silver.jsonl")]
tr = [x for x in sil if x["split"] == "train"]; dv = [x for x in sil if x["split"] == "dev"]
keep = [x for x in tr if x["old70"] or x.get("small")]
rest = [x for x in tr if not (x["old70"] or x.get("small"))]; r.shuffle(rest)
train = [x["img"] for x in keep + rest[:4000]]
synth = [l.strip() for l in open(OUT / "lists" / "synth.txt") if l.strip()]
train += synth[:3000]; dev_synth = synth[-600:]
bd = [l.strip() for l in open(OUT / "lists" / "train.txt") if l.strip()]
deg = [p for p in bd if p.endswith("_d.jpg")]; cln = [p for p in bd if p.endswith(".png")]
r.shuffle(deg); r.shuffle(cln); train += deg[:3000] + cln[:1000]
r.shuffle(dv)
bdev = [l.strip() for l in open(OUT / "lists" / "dev.txt") if l.strip()]; r.shuffle(bdev)
dev = bdev[:600] + [x["img"] for x in dv[:600]] + dev_synth
if C.exists():
    shutil.rmtree(C)
lists = {}
for split, paths in (("train", train), ("dev", dev)):
    (C / split).mkdir(parents=True); out = []
    for k, p in enumerate(paths):
        p = Path(p); ext = p.suffix
        name = f"{k:06d}.jpg"
        im = Image.open(p).convert("L"); im = im.resize((max(1, round(im.width * 96 / im.height)), 96), Image.LANCZOS)
        im.save(C / split / name, quality=70); shutil.copy(p.with_suffix(".gt.txt") if ext == ".png" else Path(str(p)[:-4] + ".gt.txt"), C / split / f"{k:06d}.gt.txt")
        out.append(f"/work/C/{split}/{name}")
    (C / f"{split}.txt").write_text("\n".join(out) + "\n"); lists[split] = len(out)
with tarfile.open(OUT / "C.tar", "w") as tf:
    tf.add(C, arcname="C")
print(lists, (OUT / "C.tar").stat().st_size // 2**20, "MB")
