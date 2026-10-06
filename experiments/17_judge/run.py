"""Have the judge rule on the feeler's disagreements with Azure, and check a sample of agreements.

DISAGREEMENT item: the word in its line, the disputed piece underlined; A/B = Azure's word and the same word with
that piece read as the feeler reads it (the rest of the word is Azure's in both, so they differ only there).
AGREEMENT item: the piece both read alike; A/B = that word and a one-letter look-alike changed inside the piece
(the calibration's PAIR test, on real pages). The judge saying NEITHER, or picking the look-alike, flags the
agreed reading as wrong.

    .venv/bin/python run.py MODEL [--dis 800] [--agree 200] [--dry]
Writes out/judged.json (every item with its facts and verdict) and out/crops/<id>.png for the report.
"""
import sys, json, random, glob
from pathlib import Path
from collections import Counter, defaultdict
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "16_feel"))
import judge as J, calibrate as C
import cv2

SCAN = {"0618": "0618-021-002-004", "1036": "1036-010-038-007", "0772": "0772-033-037-005"}
DATA = REPO / "experiments/14_vs_azure/out/tryout_2026-10-05/azure"

RASM = {}
for g in ["بتثنيئى", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق", "اأإآ", "وؤ", "هة"]:
    for c in g: RASM[c] = g[0]
HAMZA = [set("اأإآ"), set("وؤ"), set("يئى")]


def kind(az, fe):
    """What kind of difference between Azure's letters and the feeler's (base letters, reading order)."""
    if len(az) == len(fe):
        d = [(a, b) for a, b in zip(az, fe) if a != b]
        if len(d) == 1:
            a, b = d[0]
            if {a, b} == {"ى", "ي"}: return "ى/ي"
            if {a, b} == {"ة", "ه"}: return "ة/ه"
            if any(a in s and b in s for s in HAMZA) and ("ء" in a + b or {a, b} & set("أإآؤئ")): return "hamza"
            if RASM.get(a, a) == RASM.get(b, b): return "dots"
            return "other letter"
        return "several letters"
    if abs(len(az) - len(fe)) == 1:
        lo, hi = (az, fe) if len(az) < len(fe) else (fe, az)
        if any(hi[:i] + hi[i + 1:] == lo for i in range(len(hi))):
            return "letter missing (feeler)" if len(fe) < len(az) else "letter extra (feeler)"
    return "several letters"


def word_with(r, k, text):
    toks = defaultdict(str)
    for j, (t, tk) in enumerate(zip(r["piece_texts"], r["piece_toks"])): toks[tk] += text if j == k else t
    return " ".join(toks[x] for x in sorted(toks))


def strip(s):
    return J.plain(s).strip("،.:؛\"()[]«»!؟-,")


def build(n_dis, n_agree, seed=17):
    rng = random.Random(seed); recs = []
    for f in sorted(glob.glob(str(HERE / "out/pieces/*.json"))): recs += json.load(open(f))
    dis = [r for r in recs if r["azure_units"] != r["feel_units"]]
    agr = [r for r in recs if r["azure_units"] == r["feel_units"]]
    dis = rng.sample(dis, min(n_dis, len(dis))) if n_dis < len(dis) else dis
    # agreements: the same share per book as the pieces themselves
    by = defaultdict(list)
    for r in agr: by[r["doc"]].append(r)
    pick = []
    for d, l in by.items(): pick += rng.sample(l, min(len(l), round(n_agree * len(l) / len(agr))))
    items, facts = [], []
    for test, rows in (("dis", dis), ("agree", pick)):
        for r in rows:
            iid = f"{test}:{r['doc']}:{r['page']}:{r['line']}:{r['word']}:{r['piece']}"
            az_word = strip(word_with(r, r["piece"], r["azure_piece"]))
            if test == "dis":
                alt = strip(word_with(r, r["piece"], "".join(r["feel_units"]))); k = kind(r["azure_units"], r["feel_units"])
            else:
                la = C.lookalikes(J.plain(r["azure_piece"]))
                if not la: continue
                kk, p2 = rng.choice(la); alt = strip(word_with(r, r["piece"], p2)); k = kk
            if alt == az_word: continue
            facts.append(dict(id=iid, test=test, doc=r["doc"], page=r["page"], azure=az_word, other=alt, kind=k,
                              azure_piece="".join(r["azure_units"]), feel_piece="".join(r["feel_units"]),
                              letters=len(r["azure_units"]), word_box=r["word_box"], piece_box=r["piece_box"], npieces=r["npieces"]))
    return facts


def main(model, n_dis, n_agree, dry):
    facts = build(n_dis, n_agree)
    print(Counter((f["test"], f["doc"]) for f in facts)); print(Counter(f["kind"] for f in facts if f["test"] == "dis"))
    if dry: return
    (HERE / "out/crops").mkdir(parents=True, exist_ok=True); items = []
    for f in sorted(facts, key=lambda f: (f["doc"], f["page"])):
        g = J.page_image(DATA / SCAN[f["doc"]] / f"{SCAN[f['doc']]}.pdf", f["page"])
        img = J.crop(g, f["word_box"], f["piece_box"] if f["npieces"] > 1 else None)
        cv2.imwrite(str(HERE / f"out/crops/{f['id'].replace(':', '_')}.png"), img)
        items.append(dict(id=f["id"], img=img, r1=f["azure"], r2=f["other"], blue=f["npieces"] > 1))
    res = J.judge(items, model, batch=6, tag="run")
    for f in facts:
        r = res.get(f["id"])
        if r: f.update(verdict=r["verdict"], text=r["text"], why=r["why"], A=r["A"], B=r["B"])
    json.dump(dict(model=model, items=facts), open(HERE / "out/judged.json", "w"), ensure_ascii=False, indent=1)
    print("judged", sum("verdict" in f for f in facts), "of", len(facts), f"spent ${J.spent():.3f}")


if __name__ == "__main__":
    a = sys.argv[1:]
    get = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    main(a[0], get("--dis", 800), get("--agree", 200), "--dry" in a)
