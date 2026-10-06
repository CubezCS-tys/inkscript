"""Tally the judge's rulings: out/judged.json -> out/summary.json (and a printout).

Disagreement verdicts, from the judge's answer:
  azure     — Azure's reading matches the ink (the feeler is wrong)
  feeler    — the feeler's reading matches the ink (Azure is wrong)
  neither   — both wrong; the judge wrote what it says
  unsure    — the ink cannot settle it
Agreement check: the agreed reading against a look-alike; 'neither' or the look-alike = the agreed reading is wrong.
"""
import json, sys
from pathlib import Path
from collections import Counter, defaultdict
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from judge import plain

V = {"r1": "azure", "r2": "feeler", "neither": "neither", "unsure": "unsure"}
ORDER = ["azure", "feeler", "neither", "unsure"]


def edit(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1): prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
    return d[-1]


def tally(rows):
    c = Counter(r["v"] for r in rows); n = len(rows)
    return dict(n=n, **{k: c[k] for k in ORDER}, **{k + "_pct": round(100 * c[k] / max(1, n), 1) for k in ORDER})


def main():
    J = json.load(open(HERE / "out/judged.json")); items = [f for f in J["items"] if "verdict" in f]
    for f in items:
        f["v"] = V[f["verdict"]]
        if f["v"] == "neither" and f.get("text"):
            t = plain(f["text"]).replace(" ", ""); a = f["azure"].replace(" ", ""); o = f["other"].replace(" ", "")
            ea, eo = edit(t, a), edit(t, o)
            f["closer"] = "azure" if ea < eo else "feeler" if eo < ea else "tie"
    dis = [f for f in items if f["test"] == "dis"]; agr = [f for f in items if f["test"] == "agree"]
    L = lambda n: str(n) if n < 5 else "5+"
    S = dict(model=J["model"], disagreements=tally(dis),
             by_book={d: tally([f for f in dis if f["doc"] == d]) for d in sorted({f["doc"] for f in dis})},
             by_len={l: tally([f for f in dis if L(f["letters"]) == l]) for l in ["1", "2", "3", "4", "5+"]},
             by_kind={k: tally([f for f in dis if f["kind"] == k]) for k, _ in Counter(f["kind"] for f in dis).most_common()},
             neither_closer=dict(Counter(f.get("closer", "no text") for f in dis if f["v"] == "neither")),
             agreements=dict(n=len(agr), wrong=sum(f["v"] in ("neither", "feeler") for f in agr),
                             neither=sum(f["v"] == "neither" for f in agr), picked_lookalike=sum(f["v"] == "feeler" for f in agr),
                             unsure=sum(f["v"] == "unsure" for f in agr)))
    a = S["agreements"]; a["wrong_pct"] = round(100 * a["wrong"] / max(1, a["n"]), 1)
    # what each piece-level rate implies across all pieces read: disagreement share from the extraction
    pieces = dis_all = 0
    for p in (HERE / "out/pieces").glob("*.json"):
        for r in json.load(open(p)): pieces += 1; dis_all += r["azure_units"] != r["feel_units"]
    S["pieces"] = dict(total=pieces, disagree=dis_all, disagree_pct=round(100 * dis_all / max(1, pieces), 1))
    json.dump(S, open(HERE / "out/summary.json", "w"), ensure_ascii=False, indent=1)
    json.dump(dict(model=J["model"], items=items), open(HERE / "out/judged_tallied.json", "w"), ensure_ascii=False)
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
