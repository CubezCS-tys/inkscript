"""Can the judge tell a box on the right letter from one shifted off it? Run before any measurement.

Items from the fixture's words (not the measured sample):
  sep_true    a letter that is its own piece of ink (ا د ر و … or a final letter after one), its box = that piece:
              right by construction.                                                    -> expect exactly [k]
  sep_whole   that letter asked about, but the box is its neighbour's piece (a whole letter off).  -> expect not [k]
  sep_half    the letter's own box moved by half its width towards a neighbour.            -> expect not [k]
  join_whole  a letter inside a joined piece, the box is a neighbour's cutter box.          -> expect not [k]
  join_half   a letter inside a joined piece, its cutter box moved by half its width.     -> expect not [k]

    .venv/bin/python calibrate.py MODEL [--n 30]
"""
import sys, json, glob, random
from pathlib import Path
import judge18 as J

HERE = Path(__file__).resolve().parent


def eligible(w):
    return 3 <= len(w["text"]) <= 9 and not w["lig"]


def build(n=30, seed=18):
    rnd = random.Random(seed); words = []
    for f in sorted(glob.glob(str(HERE / "out/words/0582_p*.json"))): words += [w for w in json.load(open(f)) if eligible(w)]
    rnd.shuffle(words); items = {k: [] for k in ("sep_true", "sep_whole", "sep_half", "join_whole", "join_half")}
    for w in words:
        L = len(w["text"]); C = w["cutter"]; base = dict(doc=w["doc"], page=w["page"], box=w["box"], letters=list(w["text"]))
        wid = f"{w['doc']}-{w['page']}-{w['line']}-{w['word']}"
        sep = [k for k in range(L) if not w["joined"][k] and C[k][1] - C[k][0] >= 6]
        jn = [k for k in range(L) if w["joined"][k] and w["nchar"][k] == 1]
        if sep:
            k = rnd.choice(sep); nb = k + rnd.choice([-1, 1]) if 0 < k < L - 1 else (1 if k == 0 else L - 2)
            a, b = C[k]; d = (b - a) / 2 * (1 if nb < k else -1)            # reading order runs right to left: k-1 is to the right
            for kind, cell in (("sep_true", (a, b)), ("sep_whole", tuple(C[nb])), ("sep_half", (a + d, b + d))):
                if len(items[kind]) < (2 * n if kind == "sep_true" else n):
                    items[kind].append(dict(base, id=f"cal-{kind}-{wid}-{k}", cell=list(cell), k=k + 1, kind=kind))
        if jn:
            k = rnd.choice(jn); nb = k + rnd.choice([-1, 1]) if 0 < k < L - 1 else (1 if k == 0 else L - 2)
            a, b = C[k]; d = (b - a) / 2 * (1 if nb < k else -1)
            for kind, cell in (("join_whole", tuple(C[nb])), ("join_half", (a + d, b + d))):
                if len(items[kind]) < n:
                    items[kind].append(dict(base, id=f"cal-{kind}-{wid}-{k}", cell=list(cell), k=k + 1, kind=kind))
        if all(len(v) >= (2 * n if k == "sep_true" else n) for k, v in items.items()): break
    return [it for v in items.values() for it in v]


def score(items, ans):
    out = {}
    for it in items:
        a = ans.get(it["id"])
        if a is None: continue
        v = a.get("verdict") or ("RIGHT" if J.right(a, it["k"]) else "RIGHT-unclean" if J.right(a, it["k"], True) else "unparsed" if a["pos"] is None else "WRONG")
        o = out.setdefault(it["kind"], {}); o[v] = o.get(v, 0) + 1
    return out


if __name__ == "__main__":
    model = sys.argv[1]; n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 30
    items = build(n); print(len(items), "items")
    mode = "blind" if "--blind" in sys.argv else "graded"
    ans = J.judge(items, model, tag="calibrate-" + mode, max_usd=1.5, mode=mode)
    res = score(items, ans); print(model, json.dumps(res))
    with open(HERE / "out/calibration.jsonl", "a") as f: f.write(json.dumps(dict(model=model, version=J.VERSIONS[mode], res=res)) + "\n")
