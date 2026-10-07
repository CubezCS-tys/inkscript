"""Score the furniture rule on the hand-read sample (truth/furniture_truth.json): each block the old rule set aside,
judged furniture or content on the page image. With the code on PYTHONPATH, is it still set aside?

    PYTHONPATH=src .venv/bin/python experiments/30_furniture_flags/evaluate_furniture.py [NAME [TRUTH]]
        -> out/furniture_eval_NAME.json; TRUTH furniture_truth (default, the tuning sample) or heldout_truth

  content rescued   content blocks no longer set aside (the old rule set aside all of them)
  furniture kept    furniture blocks still set aside (a lost one is a leak into the JATS text)
Rates per stratum are of the sample; the sample's strata are weighted by their size on the 205 documents
(census_before.json) for the whole-set estimate.
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from inkscript.enrich import structure
from inkscript.enrich.document import load

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/28_scale/out")
sys.path.insert(0, str(HERE))
from furniture_sample import stratum  # noqa: E402


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


name = sys.argv[1] if len(sys.argv) > 1 else "after"
TRUTH = sys.argv[2] if len(sys.argv) > 2 else "furniture_truth"     # or heldout_truth
truth = json.loads((HERE / "truth" / f"{TRUTH}.json").read_text(encoding="utf-8"))["blocks"]
by_doc = defaultdict(list)
for t in truth:
    by_doc[t["doc"]].append(t)


def one(item):
    stem, ts = item
    doc = load(DATA / "azure" / stem / f"{stem}.json")
    structure.FURNITURE_TRACE = {}
    a = structure.analyse(doc, structure.read_meta(stem, [DATA / "gemini"]), None)
    W = doc["words"]
    out = []
    for t in ts:
        hit = None
        for i, p in enumerate(doc["paras"]):
            ws = [W[k] for k in p["words"] if W[k]["page"] == t["page"]]
            if ws and W[p["words"][0]]["page"] == t["page"] and \
                    all(abs(round(x) - y) <= 2 for x, y in zip(structure._box(ws), t["box"])):
                hit = i
                break
        still = hit is not None and hit in a["furniture"]
        tr = structure.FURNITURE_TRACE.get(hit) if hit is not None else None
        out.append(dict(t, found=hit is not None, still=still, why_now=a["why"][hit] if hit is not None else None,
                        kind_now=a["kinds"][hit] if hit is not None else None, trace=tr))
    return out


from multiprocessing import Pool  # noqa: E402
with Pool(3) as pool:                       # 3 workers: the largest document takes ~2 GB with the whole analysis
    rows = [r for rs in pool.map(one, sorted(by_doc.items(), key=lambda x: -len(x[1])), chunksize=1) for r in rs]
census = json.loads((HERE / "out" / "census_before.json").read_text(encoding="utf-8"))
size = Counter()
import re  # noqa: E402
norm = lambda s: re.sub(r"[^ء-يa-zA-Z]", "", s or "")
for stem, r in census.items():
    cnt = Counter(norm(b["text"]) for b in r["furniture"])
    for b in r["furniture"]:
        s = stratum(b, cnt)
        if s:
            size[s] += 1
res = {}
tot = Counter()
for s in sorted({r["stratum"] for r in rows}):
    rs = [r for r in rows if r["stratum"] == s]
    c = Counter((r["verdict"], r["still"]) for r in rs)
    nc, nf = c[("content", True)] + c[("content", False)], c[("furniture", True)] + c[("furniture", False)]
    res[s] = dict(sample=len(rs), population=size[s], content=nc, rescued=c[("content", False)], furniture=nf,
                  kept=c[("furniture", True)], leaks=[r["text"][:60] for r in rs if r["verdict"] == "furniture" and not r["still"]],
                  missed=[r["text"][:60] for r in rs if r["verdict"] == "content" and r["still"]])
    w = (size[s] or len(rs)) / len(rs)
    tot.update(content=nc, rescued=c[("content", False)], furniture=nf, kept=c[("furniture", True)],
               w_content=nc * w, w_rescued=c[("content", False)] * w, w_furniture=nf * w, w_kept=c[("furniture", True)] * w)
    print(f"{s:14s} sample {len(rs):3d} (of {size[s]:5d})  content rescued {c[('content', False)]:2d}/{nc:<2d}  "
          f"furniture kept {c[('furniture', True)]:2d}/{nf:<2d}  leaks {res[s]['leaks']}  missed {res[s]['missed']}")
summary = dict(content=tot["content"], rescued=tot["rescued"], rescued_ci=wilson(tot["rescued"], tot["content"]),
               furniture=tot["furniture"], kept=tot["kept"], kept_ci=wilson(tot["kept"], tot["furniture"]),
               est_content_blocks=round(tot["w_content"]), est_rescued_blocks=round(tot["w_rescued"]),
               est_furniture_blocks=round(tot["w_furniture"]), est_leaked_blocks=round(tot["w_furniture"] - tot["w_kept"]))
print(summary)
(HERE / "out" / f"furniture_eval_{name}.json").write_text(json.dumps(dict(summary=summary, strata=res, rows=rows),
                                                                       ensure_ascii=False, indent=1), encoding="utf-8")
