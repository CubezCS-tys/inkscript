"""Experiment 84: letter error (CER, punctuation counted) of readers on the 4,000 synthetic dev lines, by mode
(dark band / partial band / grey band / plain display / quote).   python3 vsyn84.py v3 v5 [v5a]  -> out/vsyn84.json"""
import glob, json, sys
from collections import defaultdict
from pathlib import Path
from rapidfuzz.distance import Levenshtein
H = Path(__file__).resolve().parent
M = {}
for f in glob.glob(str(H / "out/host/manifest-vsyn84-*.jsonl")):
    for l in open(f, encoding="utf-8"):
        d = json.loads(l); M[d["key"]] = d
res = {}
for name in sys.argv[1:]:
    P = {d["key"]: d["pred"] for d in map(json.loads, open(H / f"out/pred/vsyn_{name}.jsonl", encoding="utf-8"))}
    acc = defaultdict(lambda: [0, 0, 0, 0])
    for k, d in M.items():
        if k not in P:
            continue
        for g in (d["mode"], "all"):
            a = acc[g]; e = Levenshtein.distance(P[k], d["label"]); a[0] += e; a[1] += len(d["label"]); a[2] += e > 0; a[3] += 1
    res[name] = {g: dict(cer=round(100 * a[0] / a[1], 2), lines_wrong=round(100 * a[2] / a[3], 1), n=a[3]) for g, a in acc.items()}
    print(name, json.dumps(res[name]))
(H / "out/vsyn84.json").write_text(json.dumps(res, indent=1))
