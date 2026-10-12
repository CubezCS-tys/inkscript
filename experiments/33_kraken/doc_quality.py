"""Keep only documents whose text layer can be trusted as truth -> out/doc_quality.json, out/data.jsonl.

    out/env/bin/python doc_quality.py
build_data.py's first screen (median line CER against Azure <= 5%) let through two kinds of broken text layer, found
by reading the disagreements (2026-10-11):
- fonts whose digit glyphs carry the wrong code (`6944، ص 613` printed as `1988، ص 147`; `(005)` for `(125)`),
- fonts that map a few letters to others (`المعممين بأىمية` for `المعلمين بأهمية`, every ل as م, ه as ى).
A document now stays when, over its Arabic lines of 10+ characters, the median line CER against Azure is <= 2% and at
least 60% of lines are within 2%, and, when it has 20+ numbers, at least 80% of its numbers are also in Azure's line.
Azure only votes on whole documents (a broken font is broken on every page), never on a line's text.
The previous data.jsonl is kept as data_all.jsonl.
"""
import json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import faithful, is_arabic_line
from rapidfuzz.distance import Levenshtein

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out")
if not (OUT / "data_all.jsonl").exists():
    shutil.copy(OUT / "data.jsonl", OUT / "data_all.jsonl")
data = [json.loads(l) for l in open(OUT / "data_all.jsonl")]
q = {}
for doc in sorted({r["doc"] for r in data}):
    d = json.load(open(OUT / "lines" / f"{doc}.json"))
    n = a = 0; c = []
    for p in d["pages"]:
        for l in p["lines"]:
            g = faithful(l["gold"]); az = faithful(l["azure"])
            gd = re.findall(r"\d+", g); ad = re.findall(r"\d+", az)
            if gd and ad:
                n += len(gd); a += len(set(gd) & set(ad))
            if az and is_arabic_line(g) and len(g) >= 10:
                c.append(Levenshtein.distance(g, az) / len(g))
    c.sort()
    med = c[len(c) // 2] if c else 1; close = sum(x <= 0.02 for x in c) / max(len(c), 1); dig = a / n if n else None
    keep = med <= 0.02 and close >= 0.6 and (n < 20 or dig >= 0.8)
    q[doc] = dict(median=med, close=close, numbers=n, numbers_agree=dig, keep=keep, split=d["info"]["split"])
json.dump(q, open(OUT / "doc_quality.json", "w"), indent=1)
kept = [r for r in data if q[r["doc"]]["keep"]]
# single lines whose text layer is broken although the document is fine (two overlapping lines drawn as one, a header
# in a broken font): in train/dev a line goes when its text is more than 30% away from Azure's; in test a line is only
# marked `suspect` (and left out of every reader's score) when it is more than 30% away from BOTH independent readers,
# Azure and the out-of-the-box Kraken model.
base = {}
if (OUT / "preds" / "test_clean_base.jsonl").exists():
    base = {Path(j["img"]).name: j["text"] for j in map(json.loads, open(OUT / "preds" / "test_clean_base.jsonl"))}
far = lambda g, t: bool(g) and Levenshtein.distance(g, faithful(t or "")) > 0.3 * len(g)
out = []
for r in kept:
    g = faithful(r["gold"])
    if r["split"] != "test":
        if r["azure"] and far(g, r["azure"]):
            continue
    else:
        r["suspect"] = far(g, r["azure"]) and far(g, base.get(r["id"] + ".png", ""))
    out.append(r)
print("lines dropped from train/dev:", sum(r["split"] != "test" for r in kept) - sum(r["split"] != "test" for r in out),
      "; test lines marked suspect:", sum(r.get("suspect", False) for r in out))
kept = out
with open(OUT / "data.jsonl", "w") as f:
    for r in kept:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
for sp in ("train", "dev", "test"):
    docs = [d for d, v in q.items() if v["split"] == sp]
    k = [d for d in docs if q[d]["keep"]]
    print(sp, f"documents {len(k)}/{len(docs)}", "journals", len({d[:4] for d in k}), "lines", sum(r["split"] == sp for r in kept))
