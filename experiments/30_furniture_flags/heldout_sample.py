"""A held-out check of the new furniture rule, drawn after it was tuned on truth/furniture_truth.json: what did it
change on the 205 documents (census_before.json vs census_after.json), and is each change right?

    .venv/bin/python experiments/30_furniture_flags/heldout_sample.py
      -> out/heldout_sample.json, out/look/heldout_NN.png; verdicts in truth/heldout_truth.json

Strata: released (set aside before, kept as content now) with letters 30, released numbers 10; still set aside
by place alone (not a repeat of the same text on 3+ pages) 20. Blocks already in the tuning sample are skipped.
"""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from furniture_sample import draw  # noqa: E402

norm = lambda s: re.sub(r"[^ء-يa-zA-Z]", "", s or "")
before = json.loads((HERE / "out" / "census_before.json").read_text(encoding="utf-8"))
after = json.loads((HERE / "out" / "census_after.json").read_text(encoding="utf-8"))
tuned = {(t["doc"], t["page"], tuple(t["box"])) for t in
         json.loads((HERE / "truth" / "furniture_truth.json").read_text(encoding="utf-8"))["blocks"]}
pools = {"released-letters": [], "released-number": [], "still-by-place": []}
counts = Counter()
for stem, r in before.items():
    now = {b["i"]: b for b in after[stem]["furniture"]}
    cnt = Counter(norm(b["text"]) for b in after[stem]["furniture"])
    for b in r["furniture"]:
        counts["before"] += 1
        if (stem, b["page"], tuple(b["box"])) in tuned:
            continue
        if b["i"] not in now:
            counts["released"] += 1
            s = "released-letters" if len(norm(b["text"])) >= 3 else "released-number"
            pools[s].append(dict(doc=stem, stratum=s, **b))
    for b in after[stem]["furniture"]:
        counts["after"] += 1
        if (stem, b["page"], tuple(b["box"])) in tuned or b["why"] == "azure":
            continue
        if len(norm(b["text"])) >= 3 and cnt[norm(b["text"])] <= 2:
            pools["still-by-place"].append(dict(doc=stem, stratum="still-by-place", **b))
print(dict(counts), {k: len(v) for k, v in pools.items()})
rng = random.Random(31)
sample = []
for s, n in (("released-letters", 30), ("released-number", 10), ("still-by-place", 20)):
    rng.shuffle(pools[s])
    sample += pools[s][:n]
for k, x in enumerate(sample):
    x["n"] = k
(HERE / "out" / "heldout_sample.json").write_text(json.dumps(dict(pools={k: len(v) for k, v in pools.items()},
                                                                  sample=sample), ensure_ascii=False, indent=1), encoding="utf-8")
draw(sample, "heldout")
for x in sample:
    print(x["n"], x["stratum"], x["doc"], x["page"], x["why"], "|", x["text"][:60])
