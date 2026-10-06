"""Paid confirmation, tried on a small sample: the calibrated judge (experiment 19's two stages: Flash on every word,
Pro on those Flash does not call RIGHT) looks at flagged words of the four scanned TEI documents. A RIGHT clears the
flag; anything else keeps it.

    .venv/bin/python confirm.py [N_PER_DOC] [--go]     -> out/confirm.json; spend in out/spend.jsonl (cap $5)

Without --go it only prints the estimate.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO / "experiments/17_judge"))
import judge1 as J  # noqa: E402
from docs import list_docs  # noqa: E402

FLASH, PRO = "gemini-3.8-flash", "gemini-3.1-pro-preview"
STEMS = ["0582-004-009-012", "0618-021-002-004", "1036-010-038-007", "1005-000-001-002"]


def sample(n_per_doc):
    out = []
    for s in STEMS:
        t = [w for w in json.loads((HERE / "out/trust" / f"{s}.json").read_text()) if w["mark"] == "flagged" and w["box"]]
        rng = random.Random(f"22:{s}")
        out += [dict(w, doc=s) for w in rng.sample(t, min(n_per_doc, len(t)))]
    return out


def crops(ws):
    import judge as J17
    docs = list_docs(); items = []
    for w in ws:
        g = J17.page_image(docs[w["doc"]]["pdf"], w["page"])
        items.append(dict(id=f"{w['doc']}:{w['page']}:{w['pi']}", reading=w["text"], img=J17.crop(g, w["box"])))
    return items


if __name__ == "__main__":
    a = sys.argv[1:]; n = int(a[0]) if a and a[0].isdigit() else 12
    ws = sample(n)
    print(len(ws), "flagged words;", dict(Counter(r for w in ws for r in w["why"])))
    est = J.estimate(len(ws), FLASH) + J.estimate(len(ws) * 0.35, PRO)
    print(f"estimate: Flash ${J.estimate(len(ws), FLASH):.3f} + Pro on ~35% ${J.estimate(len(ws) * 0.35, PRO):.3f} = ${est:.3f}; "
          f"spent so far ${J.spent():.3f} (cap ${J.CAP})")
    if "--go" not in a: sys.exit()
    items = crops(ws); (HERE / "out/confirm_crops").mkdir(exist_ok=True)
    import cv2
    for it in items: cv2.imwrite(str(HERE / "out/confirm_crops" / (it["id"].replace(":", "_") + ".png")), it["img"])
    r1 = J.judge(items, FLASH, tag="confirm", limit_usd=1.0)
    second = [it for it in items if it["id"] in r1 and r1[it["id"]]["verdict"] != "right"]
    print(len(second), "to Pro; estimate", round(J.estimate(len(second), PRO), 3))
    r2 = J.judge(second, PRO, batch=6, tag="confirm2", limit_usd=1.0)
    res = []
    for w, it in zip(ws, items):
        f = r1.get(it["id"]); p = r2.get(it["id"]); fin = p or f
        res.append(dict(id=it["id"], text=w["text"], conf=w["conf"], why=w["why"], flash=f and f["verdict"], pro=p and p["verdict"],
                        verdict=fin and fin["verdict"], judge_text=fin and fin["text"], judge_why=fin and fin["why"]))
    json.dump(res, open(HERE / "out/confirm.json", "w"), ensure_ascii=False, indent=1)
    c = Counter(r["verdict"] for r in res)
    print("verdicts", dict(c), f"cleared {c['right']}/{len(res)}; spent ${J.spent():.3f}")
