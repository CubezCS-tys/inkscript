"""Draw the sample, build one judge item per distinct (word, letter, box), ask both judge questions.

Samples (seeded, drawn once and written to out/sample.json):
  A  unseen pages, words where the feeler reads every joined piece as Azure does: cutter, feeler, equal
  B  unseen pages, the other words (the feeler read a piece differently): cutter, equal
  C  the fixture (0582): cutter, equal
Words of 2-7 letters, no lam-alef ligature (one glyph in every method, its two letters cross), no vowel marks
(collect.py already drops them: the PDF stores the marks and Chrome slices per character).

An item's id names the word, the letter and the box's pixels — never the method; two methods giving the same box
(to the pixel) share one judgement, since the judge would see the same picture.

    .venv/bin/python run18.py A 130 [B 50 C 50] [--dry]
"""
import sys, json, glob, random
from pathlib import Path
import judge18 as J

HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
MODEL = "gemini-3.8-flash"


def words():
    W = [w for f in sorted(glob.glob(str(OUT / "words/*.json"))) for w in json.load(open(f))]
    return [w for w in W if 2 <= len(w["text"]) <= 7 and not w["lig"]]


def draw(sizes, seed=1818):
    path = OUT / "sample.json"
    S = json.load(open(path)) if path.exists() else {}
    W = words(); rnd = random.Random(seed)
    pools = {"A": [w for w in W if w["split"] == "unseen" and w["feeler"] is not None],
             "B": [w for w in W if w["split"] == "unseen" and w["feeler"] is None],
             "C": [w for w in W if w["split"] == "fixture"]}
    for s, n in sizes.items():
        pool = pools[s][:]; rnd.shuffle(pool); have = S.get(s, [])
        ids = {wid(w) for w in have}
        S[s] = have + [w for w in pool if wid(w) not in ids][:max(0, n - len(have))]
    json.dump(S, open(path, "w"), ensure_ascii=False)
    return S


def wid(w):
    return f"{w['doc']}-{w['page']}-{w['line']}-{w['word']}"


def methods_of(sample):
    return ("cutter", "feeler", "equal") if sample == "A" else ("cutter", "equal")


def items_of(S):
    """{item id: item}, and per (sample, word, method, k) the item id."""
    items, ref = {}, {}
    for s, ws in S.items():
        for w in ws:
            for m in methods_of(s):
                for k, cell in enumerate(w[m], 1):
                    a, b = int(round(cell[0])), int(round(cell[1]))
                    iid = f"{wid(w)}-{k}-{a}-{b}"
                    items[iid] = dict(id=iid, doc=w["doc"], page=w["page"], box=w["box"], cell=[a, b], letters=list(w["text"]), k=k)
                    ref[(s, wid(w), m, k)] = iid
    return items, ref


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    sizes = {a[i]: int(a[i + 1]) for i in range(0, len(a), 2)}
    S = draw(sizes); S = {s: S[s] for s in sizes}
    items, ref = items_of(S)
    print({s: len(ws) for s, ws in S.items()}, "words;", len(ref), "boxes;", len(items), "distinct items;",
          f"estimate ~${len(items) * 0.0026:.2f} for both questions at Flash; spent so far ${J.spent():.3f}")
    if "--dry" in sys.argv: sys.exit()
    todo = list(items.values())
    part = next((x.split("=")[1] for x in sys.argv if x.startswith("--part=")), None)      # i/n: run n processes side by side
    if part:
        i, n = map(int, part.split("/")); todo = [it for it in todo if int(J.hashlib.md5(it["id"].encode()).hexdigest(), 16) % n == i]
    modes = next((x.split("=")[1].split(",") for x in sys.argv if x.startswith("--mode=")), ["graded", "blind"])
    for mode in modes:
        J.judge(todo, MODEL, tag=f"run-{''.join(sizes)}-{mode}", mode=mode, max_usd=9.6 - J.spent())
