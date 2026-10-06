"""Calibrate the judge on the owner's gold sheets (experiment 12) before trusting it.

The owner marked every word of two pages (0005-032-001-001 p2, 1110-000-001-001 p1, Azure's reading) right or
wrong. On words they marked right, the judge is shown the word's ink with two readings:
  * PAIR    — the real reading against a look-alike (one dot group changed, ة/ه, ى/ي, hamza added/removed).
              Half the look-alikes are chosen to be real words (seen elsewhere in the corpus), so the judge
              cannot win on "which one is a word"; the rest are whatever look-alike the word allows.
              Right answer: the real reading.
  * NEITHER — two different look-alikes, the real reading absent. Right answer: NEITHER (with the real text).
And the owner's doubtful/inconsistent words are shown too, unscored, to see what the judge makes of them.

    .venv/bin/python calibrate.py MODEL [--batch 6] [--n 60]        # per gold page: n pairs + n/4 neithers
"""
import sys, json, random, glob
from pathlib import Path
from collections import Counter
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import judge as J

GOLD = REPO / "experiments/12_gold/gold"
DOCS = HERE / "out/gold_docs"

DOT_GROUPS = ["بتثني", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق"]
SWAP = {}
for g in DOT_GROUPS:
    for c in g: SWAP.setdefault(c, []).extend([("dots", d) for d in g if d != c])
HAMZA = {"ا": ["أ", "إ"], "أ": ["ا", "إ"], "إ": ["ا", "أ"], "آ": ["ا"], "و": ["ؤ"], "ؤ": ["و"], "ئ": ["ي"]}
for c, l in HAMZA.items(): SWAP.setdefault(c, []).extend([("hamza", d) for d in l])


def lookalikes(word):
    """Every one-letter look-alike of a word, with its kind."""
    out = []; L = len(word)
    for i, c in enumerate(word):
        last = i == L - 1
        if last and c == "ة": out.append(("ta", word[:i] + "ه"))
        if last and c == "ه": out.append(("ta", word[:i] + "ة"))
        if last and c == "ى": out.append(("ya", word[:i] + "ي"))
        if last and c == "ي": out.append(("ya", word[:i] + "ى"))
        for kind, d in SWAP.get(c, []):
            if c == "ي" and last: continue                        # final ي/ى handled above; ي -> ب at the end looks nothing alike
            if d == "ي" and last: continue
            out.append((kind, word[:i] + d + word[i + 1:]))
    return [(k, w) for k, w in out if w != word]


def lexicon():
    c = Counter()
    for f in list(glob.glob(str(REPO / "experiments/14_vs_azure/out/tryout_2026-10-05/azure/*/*.json"))) + \
             [str(REPO / "tests/fixtures/0582-004-009-012/azure/0582-004-009-012/0582-004-009-012.json")] + glob.glob(str(DOCS / "*/*.json")):
        j = json.load(open(f)); ar = j.get("analyzeResult", j)
        for p in ar["pages"]:
            for w in p.get("words", []): c[J.plain(w["content"]).strip("،.:؛\"()[]«»!؟-")] += 1
    return c


ARABIC = lambda s: s and all("ء" <= ch <= "ي" for ch in s)


def items(n=60, seed=17):
    rng = random.Random(seed); lex = lexicon(); out = []; info = []
    for f, stem, pn in [("0005-032-001-001_p2_azure.gold.json", "0005-032-001-001", 2), ("1110-000-001-001_p1_azure.gold.json", "1110-000-001-001", 1)]:
        g = json.load(open(GOLD / f)); gray = J.page_image(DOCS / stem / f"{stem}.pdf", pn)
        words = [w for w in g["words"] if w["cls"] == "correct" and ARABIC(J.plain(w["reading"])) and len(J.plain(w["reading"])) >= 2]
        words = [w for w in words if lookalikes(J.plain(w["reading"]))]
        rng.shuffle(words)
        has = [w for w in words if any(lex[x[1]] > 0 for x in lookalikes(J.plain(w["reading"])))]
        rest = [w for w in words if w not in has]
        words = [x for pair in zip(has, rest) for x in pair] + has[len(rest):] + rest[len(has):]   # alternate: real-word look-alike available / not
        for k, w in enumerate(words[: n + n // 4]):
            real = J.plain(w["reading"]); la = lookalikes(real)
            inlex = [x for x in la if lex[x[1]] > 0]
            if k < n:
                pick = rng.choice(inlex) if (k % 2 == 0 and inlex) else rng.choice(la)
                out.append(dict(id=f"cal:{stem}:{w['i']}:pair", img=J.crop(gray, w["box"]), r1=real, r2=pick[1], blue=False))
                info.append(dict(id=out[-1]["id"], test="pair", kind=pick[0], realword=lex[pick[1]] > 0, real=real, alt=pick[1], stem=stem, box=w["box"]))
            elif len(la) >= 2:
                a, b = rng.sample(la, 2)
                out.append(dict(id=f"cal:{stem}:{w['i']}:neither", img=J.crop(gray, w["box"]), r1=a[1], r2=b[1], blue=False))
                info.append(dict(id=out[-1]["id"], test="neither", kind=a[0] + "+" + b[0], real=real, alt=a[1] + " / " + b[1], stem=stem, box=w["box"]))
        # the owner's doubtful words, and the two readings of 1110 p1 that the owner marked both right / inconsistently
        special = [(w, None) for w in g["words"] if w["cls"] == "unsure"]
        if stem == "1110-000-001-001":
            special += [(w, alt) for w in g["words"] for (r, alt) in (("طرح", "صرح"), ("التكويني", "التكوينى")) if J.plain(w["reading"]) == r]
        for w, alt in special:
            real = J.plain(w["reading"]); alt = alt or (lookalikes(real) or [("", real + "ا")])[0][1]
            out.append(dict(id=f"cal:{stem}:{w['i']}:special", img=J.crop(gray, w["box"]), r1=real, r2=alt, blue=False))
            info.append(dict(id=out[-1]["id"], test="special", kind="owner: " + w["cls"], real=real, alt=alt, stem=stem, box=w["box"]))
    return out, info


def score(info, res):
    rows = []
    for d in info:
        r = res.get(d["id"])
        if r is None: continue
        if d["test"] == "pair": ok = r["verdict"] == "r1"
        elif d["test"] == "neither": ok = r["verdict"] == "neither"
        else: ok = None
        rows.append(dict(d, verdict=r["verdict"], text=r["text"], why=r["why"], ok=ok, wrote_real=J.plain(r["text"]) == d["real"] if r["verdict"] == "neither" else None))
    return rows


def summary(rows):
    s = {}
    pairs = [r for r in rows if r["test"] == "pair"]
    for name, sub in [("pairs", pairs), ("pairs, look-alike a real word", [r for r in pairs if r["realword"]]),
                      ("pairs, look-alike not a word", [r for r in pairs if not r["realword"]])] + \
                     [(f"pairs, {k}", [r for r in pairs if r["kind"] == k]) for k in ("dots", "hamza", "ta", "ya")] + \
                     [("neither", [r for r in rows if r["test"] == "neither"])]:
        v = Counter(r["verdict"] for r in sub)
        s[name] = dict(n=len(sub), right=sum(bool(r["ok"]) for r in sub), wrong_pick=v["r2"] + (v["r1"] if name == "neither" else 0),
                       neither=v["neither"], unsure=v["unsure"])
    return s


if __name__ == "__main__":
    model = sys.argv[1]; a = sys.argv[2:]
    batch = int(a[a.index("--batch") + 1]) if "--batch" in a else 6
    n = int(a[a.index("--n") + 1]) if "--n" in a else 60
    its, info = items(n)
    if "--dry" in a:
        print(len(its), Counter(d["test"] for d in info), Counter(d["kind"] for d in info), sum(d.get("realword", 0) for d in info)); sys.exit()
    tag = f"cal-b{batch}"
    if batch != 6:                                                   # a different batch size is a different experiment: own cache ids
        for it in its: it["id"] += f":b{batch}"
        for d in info: d["id"] += f":b{batch}"
    res = J.judge(its, model, batch=batch, tag=tag)
    rows = score(info, res)
    (HERE / "out/calibration").mkdir(parents=True, exist_ok=True)
    json.dump(dict(model=model, batch=batch, rows=rows, summary=summary(rows)), open(HERE / f"out/calibration/{model}_b{batch}.json", "w"), ensure_ascii=False, indent=1)
    for k, v in summary(rows).items(): print(f"{k:34s} {v}")
    for r in rows:
        if r["ok"] is False or r["test"] == "special": print(r["test"], r["kind"], r["real"], "|", r["alt"], "->", r["verdict"], r["text"], "|", r["why"])
    print(f"spent so far ${J.spent():.3f}")
