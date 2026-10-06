"""Judge a variant's letter boxes with experiment 18's calibrated judge (Gemini Flash, same crop, the graded and the
blind question, temperature 0, 8 crops a request; right = both). A box with the same pixels as one already judged
(18, 21 — their cache is copied into out/judge_cache.jsonl) keeps that verdict and is never re-paid. Only boxes the
variant moved are asked, shuffled with a CONTROL of 21's own after-boxes asked again (id + '#r') to measure drift.
Spend: out/spend.jsonl; cap $10 for this experiment.

    ../../.venv/bin/python judge25.py VARIANT [--dry] [--control=60]
"""
import sys, json, random, shutil
from pathlib import Path
HERE = Path(__file__).resolve().parent; E18 = HERE.parent / "18_boxes"; E21 = HERE.parent / "21_better_boxes"
sys.path.insert(0, str(E18))
import judge18 as J, run18 as R

OUT = HERE / "out"
J.CACHE = OUT / "judge_cache.jsonl"; J.SPEND = OUT / "spend.jsonl"; J.CAP = 10.0
if not J.CACHE.exists(): shutil.copy(E21 / "out/judge_cache.jsonl", J.CACHE)
METHODS = {"A": ("cutter_new",), "B": ("cutter_new",), "C": ("cutter_new",)}


def after_cells(variant):
    """{wid: cells}: the variant's boxes where it moved them, else 21's PDF boxes (= today, as judged in 21)."""
    T = json.load(open(OUT / "boxes_today.json")); V = json.load(open(OUT / f"boxes_{variant}.json")); N = json.load(open(E21 / "out/boxes_new.json"))
    out = {}
    for wid, cells in V.items():
        same = all(abs(a - c) <= 0.5 for x, y in zip(cells, T[wid]) for a, c in zip(x, y))
        out[wid] = N[wid]["cells"] if (same and wid in N) else cells
    return out


def items_of(S, cellsets):
    """cellsets: {name: {wid: cells}} -> items {iid: item}, ref {(sample, wid, name, k): iid}"""
    items, ref = {}, {}
    for s, ws in S.items():
        for w in ws:
            for name, cs in cellsets.items():
                if R.wid(w) not in cs: continue
                for k, cell in enumerate(cs[R.wid(w)], 1):
                    a, b = int(round(cell[0])), int(round(cell[1])); iid = f"{R.wid(w)}-{k}-{a}-{b}"
                    items[iid] = dict(id=iid, doc=w["doc"], page=w["page"], box=w["box"], cell=[a, b], letters=list(w["text"]), k=k)
                    ref[(s, R.wid(w), name, k)] = iid
    return items, ref


def before_cells():
    N = json.load(open(E21 / "out/boxes_new.json")); return {k: v["cells"] for k, v in N.items()}


if __name__ == "__main__":
    variant = sys.argv[1]; S = json.load(open(E18 / "out/sample.json"))
    items, ref = items_of(S, {"before": before_cells(), "after": after_cells(variant)})
    done = J.cached(R.MODEL)
    new = [it for it in items.values() if not (it["id"] + ":b2" in done and it["id"] + ":b3" in done)]
    nctl = int(next((x.split("=")[1] for x in sys.argv if x.startswith("--control=")), 60))
    before_ids = sorted({v for k, v in ref.items() if k[2] == "before"})
    ctl = [dict(items[i], id=i + "#r") for i in random.Random(2525).sample(before_ids, nctl)]
    ctl = [c for c in ctl if not (c["id"] + ":b2" in done and c["id"] + ":b3" in done)]
    todo = new + ctl
    print(f"{variant}: boxes moved and not yet judged: {len(new)}; control re-asks to do: {len(ctl)}; "
          f"estimate ~${len(todo) * 0.0028:.2f} (both questions); spent so far ${J.spent():.3f}")
    if "--dry" in sys.argv or not todo: sys.exit()
    for mode in ("graded", "blind"):
        J.judge(todo, R.MODEL, tag=f"e25-{variant}-{mode}", mode=mode, max_usd=min(3.0, 9.5 - J.spent()))
    print("spent", J.spent())
