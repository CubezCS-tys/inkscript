"""Judge the patched cutter's boxes with experiment 18's calibrated judge (same crops, same two questions, same model,
temperature 0, 8 crops a request), on 18's sample words A, B, C.

A box that is the same as one 18 already judged (same word, letter and pixels -> the same crop) takes 18's verdict:
18's cache is copied into out/judge_cache.jsonl and never re-paid. Only boxes the patch moved are asked — mixed,
shuffled, with a CONTROL set of 18's own boxes asked again (id + '#r', same crop; cutter-before and equal slices
alike), so that the judge sees boxes of every method in the same requests and its run-to-run drift is measured.
Spend logged to out/spend.jsonl; cap $10 for this experiment.

    ../../.venv/bin/python judge21.py [--dry] [--control=120]
"""
import sys, json, random, shutil
from pathlib import Path
HERE = Path(__file__).resolve().parent; E18 = HERE.parents[0] / "18_boxes"
sys.path.insert(0, str(E18))
import judge18 as J, run18 as R

OUT = HERE / "out"
J.CACHE = OUT / "judge_cache.jsonl"; J.SPEND = OUT / "spend.jsonl"; J.CAP = 10.0
if not J.CACHE.exists(): shutil.copy(E18 / "out/judge_cache.jsonl", J.CACHE)


def sample_with_new():
    """18's sample with a 'cutter_new' method per word (the patched build's boxes)."""
    S = json.load(open(E18 / "out/sample.json")); N = json.load(open(OUT / "boxes_new.json"))
    for s, ws in S.items():
        for w in ws:
            n = N.get(R.wid(w)); w["cutter_new"] = n["cells"] if n else None; w["nchar_new"] = n["nchar"] if n else None
    return S


METHODS = {"A": ("cutter", "cutter_new", "equal", "feeler"), "B": ("cutter", "cutter_new", "equal"), "C": ("cutter", "cutter_new", "equal")}


def items_of(S):
    items, ref = {}, {}
    for s, ws in S.items():
        for w in ws:
            for m in METHODS[s]:
                if w.get(m) is None: continue
                for k, cell in enumerate(w[m], 1):
                    a, b = int(round(cell[0])), int(round(cell[1])); iid = f"{R.wid(w)}-{k}-{a}-{b}"
                    items[iid] = dict(id=iid, doc=w["doc"], page=w["page"], box=w["box"], cell=[a, b], letters=list(w["text"]), k=k)
                    ref[(s, R.wid(w), m, k)] = iid
    return items, ref


if __name__ == "__main__":
    S = sample_with_new(); items, ref = items_of(S)
    done = J.cached(R.MODEL)
    new = [it for it in items.values() if not (it["id"] + ":b2" in done and it["id"] + ":b3" in done)]
    nctl = int(next((x.split("=")[1] for x in sys.argv if x.startswith("--control=")), 120))
    old_ids = sorted({ref[k] for k in ref if k[2] in ("cutter", "equal")})
    ctl = [dict(items[i], id=i + "#r") for i in random.Random(2121).sample(old_ids, nctl)]
    todo = new + ctl
    print(f"boxes moved by the patch and not yet judged: {len(new)}; control re-asks: {len(ctl)}; "
          f"estimate ~${len(todo) * 0.0028:.2f} for both questions; spent so far ${J.spent():.3f}")
    if "--dry" in sys.argv: sys.exit()
    for mode in ("graded", "blind"):
        J.judge(todo, R.MODEL, tag=f"e21-{mode}", mode=mode, max_usd=min(4.0, 9.5 - J.spent()))
    print("spent", J.spent())
