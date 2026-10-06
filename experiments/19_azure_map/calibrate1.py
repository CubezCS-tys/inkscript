"""Calibrate the single-reading judge on the owner's gold pages (experiment 12) before trusting it on the archive.

On words the owner marked right (0005-032-001-001 p2, 1110-000-001-001 p1):
  * TRUE   — the word shown with its real reading. Right answer RIGHT; anything else is a false alarm.
  * PERTURB — another such word shown with ONE mark changed: a dot group, ة/ه, ى/ي, hamza (experiment 17's
              look-alikes), a dropped letter or an added alef. Right answer WRONG; anything else is a miss.
              Whether the judge's "text" then gives back the real word is scored too.
  * the owner's two doubtful words, unscored.
Then on the archive (calibrate1.py MODEL --archive): judged archive words shown with one mark changed — the miss
rate on the prints the archive actually has (small, faint, old), per stratum, through the same two stages as
the run (Flash, then Pro on what Flash flags). Run after run.py.

    .venv/bin/python calibrate1.py MODEL [--n 100]
    .venv/bin/python calibrate1.py MODEL --archive [--n 160]
"""
import sys, json, random
from pathlib import Path
from collections import Counter, defaultdict
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]; OUT = HERE / "out"
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO / "experiments/17_judge"))
import judge1 as J
import judge as J17
from calibrate import lookalikes                 # experiment 17: every one-mark look-alike of a word, with its kind

GOLD = REPO / "experiments/12_gold/gold"; DOCS = REPO / "experiments/17_judge/out/gold_docs"
ARABIC = lambda s: s and all("ء" <= ch <= "ي" for ch in s)


def perturb(word, rng):
    """One change to the word: a look-alike (dots, ta, ya, hamza), a dropped letter, or an added alef."""
    la = lookalikes(word); r = rng.random()
    if len(word) >= 3 and r < 0.15:
        k = rng.randrange(len(word)); return "drop", word[:k] + word[k + 1:]
    if r < 0.25:
        k = rng.randrange(1, len(word) + 1)
        if k < len(word) and word[k - 1] in "اأإآ": k = 0
        w = word[:k] + "ا" + word[k:]
        if w != word: return "add", w
    if la: return rng.choice(la)
    return None


def gold_items(n, seed=19):
    rng = random.Random(seed); items = []; info = []
    for f, stem, pn in [("0005-032-001-001_p2_azure.gold.json", "0005-032-001-001", 2), ("1110-000-001-001_p1_azure.gold.json", "1110-000-001-001", 1)]:
        g = json.load(open(GOLD / f)); gray = J17.page_image(DOCS / stem / f"{stem}.pdf", pn)
        ws = [w for w in g["words"] if w["cls"] == "correct" and len(J17.plain(w["reading"])) >= 2]
        rng.shuffle(ws); half = n // 2
        for k, w in enumerate(ws[:half]):
            items.append(dict(id=f"cal:{stem}:{w['i']}:true", img=J17.crop(gray, w["box"]), reading=w["reading"]))
            info.append(dict(id=items[-1]["id"], test="true", kind="", real=w["reading"], shown=w["reading"]))
        k = half
        for w in ws[half:]:
            if sum(1 for d in info if d["test"] == "perturb" and d["id"].startswith(f"cal:{stem}")) >= half: break
            real = J17.plain(w["reading"])
            if not ARABIC(real): continue
            p = perturb(real, rng)
            if not p: continue
            items.append(dict(id=f"cal:{stem}:{w['i']}:perturb", img=J17.crop(gray, w["box"]), reading=p[1]))
            info.append(dict(id=items[-1]["id"], test="perturb", kind=p[0], real=real, shown=p[1]))
        for w in g["words"]:
            if w["cls"] == "unsure":
                items.append(dict(id=f"cal:{stem}:{w['i']}:special", img=J17.crop(gray, w["box"]), reading=w["reading"]))
                info.append(dict(id=items[-1]["id"], test="special", kind="owner unsure", real=w["reading"], shown=w["reading"]))
    return items, info


def archive_items(n, model, seed=19):
    """Archive words the judge called RIGHT, shown with one mark changed: the miss rate on the archive's own prints."""
    import cv2
    rng = random.Random(seed); sample = json.load(open(OUT / "sample.json")); res = J.cached(model)
    ok = [w for w in sample if res.get(w["id"] + J.VERSION, {}).get("verdict") == "right" and ARABIC(J17.plain(w["text"])) and len(J17.plain(w["text"])) >= 2]
    by = defaultdict(list)
    for w in ok: by[w["stratum"]].append(w)
    per = max(8, n // max(1, len(by))); items = []; info = []
    for st, v in sorted(by.items()):
        rng.shuffle(v)
        for w in v[:per]:
            p = perturb(J17.plain(w["text"]), rng)
            if not p: continue
            img = cv2.imread(str(OUT / "crops" / (w["id"].replace(":", "_") + ".png")))
            items.append(dict(id=f"acal:{w['id']}", img=img, reading=p[1]))
            info.append(dict(id=items[-1]["id"], test="perturb", kind=p[0], real=J17.plain(w["text"]), shown=p[1], stratum=st, word=w["id"]))
    return items, info


def score(info, res):
    rows = []
    for d in info:
        r = res.get(d["id"])
        if r is None: continue
        ok = (r["verdict"] == "right") if d["test"] == "true" else ((r["verdict"] == "wrong") if d["test"] == "perturb" else None)
        rows.append(dict(d, verdict=r["verdict"], text=r["text"], why=r["why"], ok=ok,
                         gave_back=(J17.plain(r["text"]) == J17.plain(d["real"])) if r["verdict"] == "wrong" else None))
    return rows


def summary(rows, key=None):
    out = {}
    groups = [("true (false alarm = not RIGHT)", [r for r in rows if r["test"] == "true"]),
              ("perturbed (miss = not WRONG)", [r for r in rows if r["test"] == "perturb"])]
    groups += [(f"perturbed: {k}", [r for r in rows if r["test"] == "perturb" and r["kind"] == k]) for k in sorted({r["kind"] for r in rows if r["test"] == "perturb"})]
    if key: groups += [(f"perturbed in {k}", [r for r in rows if r["test"] == "perturb" and r.get(key) == k]) for k in sorted({r.get(key) for r in rows if r["test"] == "perturb"})]
    for name, sub in groups:
        out[name] = dict(n=len(sub), ok=sum(bool(r["ok"]) for r in sub), verdicts=dict(Counter(r["verdict"] for r in sub)),
                         gave_back=sum(bool(r["gave_back"]) for r in sub))
    return out


if __name__ == "__main__":
    model = sys.argv[1]; a = sys.argv[2:]
    arch = "--archive" in a
    n = int(a[a.index("--n") + 1]) if "--n" in a else (160 if arch else 100)
    its, info = archive_items(n, model) if arch else gold_items(n)
    print(len(its), "items; estimate $%.2f" % J.estimate(len(its), model), "; spent so far $%.3f" % J.spent())
    if "--dry" in a: print(Counter((d["test"], d["kind"]) for d in info)); sys.exit()
    res = J.judge(its, model, tag="acal" if arch else "cal")
    if arch:                       # as in the run: what Flash does not call RIGHT goes to Pro, whose verdict then stands
        flag = [it for it in its if it["id"] in res and res[it["id"]]["verdict"] != "right"]
        res2 = J.judge(flag, "gemini-3.1-pro-preview", batch=6, tag="acal2")
        res = {**res, **res2}
    rows = score(info, res); s = summary(rows, "stratum" if arch else None)
    (OUT / "calibration").mkdir(exist_ok=True)
    json.dump(dict(model=model, rows=rows, summary=s), open(OUT / "calibration" / f"{model}{'_archive' if arch else ''}.json", "w"), ensure_ascii=False, indent=1)
    for k, v in s.items(): print(f"{k:40s} {v}")
    for r in rows:
        if r["ok"] is False or r["test"] == "special": print(r["test"], r["kind"], r.get("stratum", ""), r["real"], "| shown", r["shown"], "->", r["verdict"], r["text"], "|", r["why"])
    print(f"spent so far ${J.spent():.3f}")
