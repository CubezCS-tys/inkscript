"""The benchmark every feeling method is judged on: fixed documents, fixed splits, fixed metrics.

Four scanned documents in four typefaces. Each has TRAIN pages (what a method may remember), DEV pages (what it
may be tuned on, as often as it likes) and TEST pages (read once, at the end, by `--final`; never tuned on).
The truth is Azure's reading, not a hand check — "right" means "the same as Azure".

    python bench.py cache                       # extract every piece once (slow; ~1-2 GB peak), into out/cache/
    python bench.py run METHOD [--final]        # METHOD = a module in methods/ with learn(train) and read(model, rec)
    python bench.py table                       # every logged run, as a table (out/results.md)

A record (one connected piece of ink) has: doc, page, units (letters, reading order), forms, rise, q (the blind
geometry: pen path, trunk, ink positions, dots, candidate cut places — no text in it), and for train records
`cuts`: the letter cutter's own cuts (pen path + facts + the document's atlas), the letter boundaries a method
may learn from. Dev/test records carry `ref_cuts`: the cutter's cuts made knowing the text, for comparison.
"""
import sys, json, time, pickle, importlib, resource
from pathlib import Path
from collections import Counter
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[0] / "10_atlas_reader"))
OUT = HERE / "out"; CACHE = OUT / "cache"; LOG = OUT / "results.jsonl"
REPO = HERE.parents[1]
DATA = REPO / "experiments/14_vs_azure/out/tryout_2026-10-05/azure"      # fetched from s3://mandumah-source-docs on 2026-10-05
FIX = REPO / "tests/fixtures/0582-004-009-012"

SUITE = {
    "0582": dict(azure=FIX / "azure/0582-004-009-012/0582-004-009-012.json", scan=FIX / "input/0582-004-009-012.pdf",
                 train=[1, 2, 3], dev=[4], test=[5]),
    "0618": dict(azure=DATA / "0618-021-002-004/0618-021-002-004.json", scan=DATA / "0618-021-002-004/0618-021-002-004.pdf",
                 train=[2, 3, 4, 5, 6, 7, 8, 9], dev=[10, 11], test=[12, 13, 14, 15]),
    "1036": dict(azure=DATA / "1036-010-038-007/1036-010-038-007.json", scan=DATA / "1036-010-038-007/1036-010-038-007.pdf",
                 train=[2, 3, 4, 5, 6], dev=[7], test=[8, 9]),
    "0772": dict(azure=DATA / "0772-033-037-005/0772-033-037-005.json", scan=DATA / "0772-033-037-005/0772-033-037-005.pdf",
                 train=[1, 2, 3, 4, 5, 7], dev=[8], test=[10, 12]),
}


def build_cache(doc):
    from reader import pieces_of, blind
    from inkscript.geometry import penpath as P
    cfg = SUITE[doc]; az, sc = str(cfg["azure"]), str(cfg["scan"]); out = {"train": [], "dev": [], "test": []}
    plans = []
    for split in ("train", "dev", "test"):
        for pn, pc, (units, forms), lg in pieces_of(az, sc, cfg[split]):
            if not lg or lg["rise"] < 10: continue
            q = blind(pc, lg)
            rec = dict(doc=doc, page=pn, units=units, forms=forms, rise=float(lg["rise"]), q=q)
            if q is not None:
                for k in ("cache",): q.pop(k, None)
            if len(units) >= 2 and q is not None:
                p = P.plan(units, pc["blobs"], lg, forms)
                if p is not None and p["G"]["W"] == q["G"]["W"]:
                    if split == "train": plans.append((p, rec))
                    else: rec["ref_cuts"] = sorted(int(c) for c in p["cuts"])
            out[split].append(rec)
    P.solve([p for p, _ in plans])                                    # the cutter's cuts, with this document's atlas
    for p, rec in plans:
        rec["cuts"] = sorted(int(c) for c in p["cuts"])
    CACHE.mkdir(parents=True, exist_ok=True)
    pickle.dump(out, open(CACHE / f"{doc}.pkl", "wb"))
    print(doc, {k: len(v) for k, v in out.items()}, f"train pieces with cutter cuts: {len(plans)}", flush=True)


def load(doc):
    return pickle.load(open(CACHE / f"{doc}.pkl", "rb"))


def edit(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1): prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
    return d[-1]


def base(u):
    from inkscript.geometry.penpath import _base
    return _base(u)


def score(recs, outs):
    """Pieces right (whole piece as Azure reads it), letter accuracy (1 - edits / letters), by piece length, and
    cut agreement with the cutter on pieces read right (in strokes)."""
    n = ok = ch = err = 0; by, okb = Counter(), Counter(); cut = []; unread = 0
    for rec, o in zip(recs, outs):
        truth = [base(u) for u in rec["units"]]; n += 1; b = min(len(truth), 5); by[b] += 1; ch += len(truth)
        if o is None:
            unread += 1; err += len(truth); continue
        got, cuts = [base(x) for x in o[0]], o[1]; e = edit(got, truth); err += e
        if e == 0:
            ok += 1; okb[b] += 1
            ref = rec.get("ref_cuts")
            if ref and len(ref) == len(cuts) and rec["q"] is not None:
                st = max(1.0, rec["q"]["G"]["stroke"]); cut += [abs(x - y) / st for x, y in zip(sorted(cuts), ref)]
    c = np.array(cut)
    return dict(pieces=n, right=ok, piece_acc=round(100 * ok / max(1, n), 2), letter_acc=round(100 * (1 - err / max(1, ch)), 2),
                by_len={str(k): [okb[k], by[k]] for k in sorted(by)}, unread=unread,
                cut_within_stroke=round(100 * float((c <= 1).mean()), 1) if len(c) else None, cuts=len(c))


def run(method, final=False, docs=None, note=""):
    m = importlib.import_module(f"methods.{method}")
    split = "test" if final else "dev"; res = {}; t0 = time.time()
    for doc in docs or SUITE:
        data = load(doc); t = time.time()
        model = m.learn(data["train"])
        outs = [m.read(model, r) if r["q"] is not None else None for r in data[split]]
        res[doc] = score(data[split], outs); res[doc]["seconds"] = round(time.time() - t, 1)
        print(doc, res[doc], flush=True)
    tot = dict(pieces=sum(r["pieces"] for r in res.values()), right=sum(r["right"] for r in res.values()))
    tot["piece_acc"] = round(100 * tot["right"] / max(1, tot["pieces"]), 2)
    tot["mean_doc_piece_acc"] = round(float(np.mean([r["piece_acc"] for r in res.values()])), 2)
    tot["mean_doc_letter_acc"] = round(float(np.mean([r["letter_acc"] for r in res.values()])), 2)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    entry = dict(method=method, split=split, when=time.strftime("%Y-%m-%d %H:%M"), note=note, total=tot, docs=res,
                 seconds=round(time.time() - t0, 1), peak_gb=round(peak, 2))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f: f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print("TOTAL", split, tot, f"peak {peak:.2f} GB", flush=True)
    return entry


def table():
    rows = [json.loads(l) for l in open(LOG)] if LOG.exists() else []
    docs = list(SUITE)
    out = ["| when | method | split | pieces right (all) | mean per doc | letters (mean) | " + " | ".join(docs) + " | note |",
           "|---|---|---|---|---|---|" + "---|" * len(docs) + "---|"]
    for r in rows:
        t = r["total"]
        out.append(f"| {r['when']} | {r['method']} | {r['split']} | {t['piece_acc']}% | {t['mean_doc_piece_acc']}% | {t['mean_doc_letter_acc']}% | "
                   + " | ".join(f"{r['docs'][d]['piece_acc']}%" if d in r["docs"] else "" for d in docs) + f" | {r.get('note', '')} |")
    (OUT / "results.md").write_text("\n".join(out) + "\n"); print("\n".join(out))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "cache":
        for d in (a[1:] or SUITE): build_cache(d)
    elif a[0] == "run":
        note = next((x.split("=", 1)[1] for x in a if x.startswith("--note=")), "")
        docs = next((x.split("=", 1)[1].split(",") for x in a if x.startswith("--docs=")), None)
        run(a[1], final="--final" in a, docs=docs, note=note)
    elif a[0] == "table":
        table()
