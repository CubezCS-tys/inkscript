"""Pick the judge: a small calibration on the kind of question experiment 27 asks (a Quran word on the ink).

Items come from the 20-document set (experiment 24): words of Quran quotations that equal their verse word and that
Azure read with confidence >= 0.9, so the print, Azure and the verse agree. Each is shown with two readings:
  pair     the printed word against a look-alike (a dot group, a hamza, ة/ه, ى/ي, or a letter dropped — Azure's
           typical errors on vowelled text, experiment 20); right answer: the printed word
  neither  two look-alikes, the printed word absent; right answer: NEITHER
Half the items are vowelled quotations. Run on both candidate models; spend goes to out/spend.jsonl.

    python calibrate.py gemini-3.8-flash gemini-3.1-pro-preview [--n 24] [--go]
"""
import json, random, sys
from collections import Counter
from pathlib import Path
from inkscript.enrich.document import load
from inkscript.enrich.quran import check_document
from inkscript.enrich.judge import Judge, plain
from inkscript.enrich import judge as J

HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
SET = Path("/home/yassine/inkscript/experiments/24_product/out/set"); AZ = Path("/home/yassine/inkscript/experiments/24_product/out/azure")
DOT_GROUPS = ["بتثني", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق"]
SWAP = {}
for g in DOT_GROUPS:
    for c in g: SWAP.setdefault(c, []).extend([("dots", d) for d in g if d != c])
for c, l in {"ا": ["أ", "إ"], "أ": ["ا", "إ"], "إ": ["ا", "أ"], "و": ["ؤ"], "ؤ": ["و"], "ئ": ["ي"]}.items():
    SWAP.setdefault(c, []).extend([("hamza", d) for d in l])


def lookalikes(word):
    out = []; L = len(word)
    for i, c in enumerate(word):
        last = i == L - 1
        if last and c == "ة": out.append(("ta", word[:i] + "ه"))
        if last and c == "ى": out.append(("ya", word[:i] + "ي"))
        if last and c == "ي": out.append(("ya", word[:i] + "ى"))
        for kind, d in SWAP.get(c, []):
            if last and "ي" in (c, d): continue
            out.append((kind, word[:i] + d + word[i + 1:]))
        if 0 < i < L - 1 and c not in "اأإ": out.append(("drop", word[:i] + word[i + 1:]))
    return [(k, w) for k, w in out if w != word]


def items(n, seed=27):
    rng = random.Random(seed); cand = {True: [], False: []}
    for sj in sorted(SET.glob("w*/*.shapes.json")):
        stem = sj.name[:-12]; doc = load(AZ / stem / f"{stem}.json", sj)
        for q in check_document(doc):
            for o in q["ops"]:
                if o["kind"] != "exact" or len(o["doc"]) != 1: continue
                w = doc["words"][o["doc"][0]]
                t = plain(w["text"])
                if (w["conf"] or 0) < 0.9 or len(t) < 3 or not all("ء" <= c <= "ي" for c in t): continue
                vow = len(J.TASHKEEL.findall(w["text"])) >= 2
                cand[vow].append(dict(stem=stem, page=w["page"], box=w["box"], real=t, id=w["id"], vowelled=vow))
    out = []
    for vow in (True, False):
        rng.shuffle(cand[vow]); k = 0
        for c in cand[vow]:
            la = lookalikes(c["real"])
            if len(la) < 2: continue
            scan = AZ / c["stem"] / f"{c['stem']}.pdf"
            if k < n // 2:
                kind, alt = rng.choice(la)
                out.append(dict(id=f"cal27:{c['stem']}:{c['id']}:pair", scan=scan, page=c["page"], box=c["box"], r1=c["real"], r2=alt,
                                test="pair", kind=kind, vowelled=vow, real=c["real"]))
            elif k < n // 2 + n // 6:
                (k1, a1), (k2, a2) = rng.sample(la, 2)
                out.append(dict(id=f"cal27:{c['stem']}:{c['id']}:neither", scan=scan, page=c["page"], box=c["box"], r1=a1, r2=a2,
                                test="neither", kind=k1 + "+" + k2, vowelled=vow, real=c["real"]))
            else: break
            k += 1
    return out


def reverse_items():
    """The other direction: quotation words where the print is NOT the verse's word — the author's wording or the
    print's spelling (و/ف, داود, a pronoun changed), read by Azure with confidence >= 0.95. Right answer: the printed
    reading. A judge that leans towards the Quran's word would fail these and still pass `items`."""
    from inkscript.enrich.corrections import propose, corrected_text
    out = []
    for sj in sorted(SET.glob("w*/*.shapes.json")):
        stem = sj.name[:-12]; doc = load(AZ / stem / f"{stem}.json", sj)
        by_id = {w["id"]: w for w in doc["words"]}
        quotes = check_document(doc)
        _, skipped = propose(doc, quotes)
        for s in skipped:
            if s["category"] not in ("wording", "spelling") or len(s["ids"]) != 1 or not s["verse"]:
                continue
            w = by_id[s["ids"][0]]
            if (w["conf"] or 0) < 0.95:
                continue
            verse = corrected_text(w["text"], [dict(w=x, v=x) for x in s["verse"].split()])
            if plain(verse) == plain(w["out"]):
                continue
            out.append(dict(id=f"cal27:{stem}:{w['id']}:reverse", scan=AZ / stem / f"{stem}.pdf", page=w["page"], box=w["box"],
                            r1=w["out"], r2=verse, test="pair", kind="reverse:" + s["category"], vowelled=False, real=w["out"]))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]; n = int(a[a.index("--n") + 1]) if "--n" in a else 24
    models = [m for m in a if m.startswith("gemini")]
    its = items(n)
    if "--reverse" in a:
        its = reverse_items()
    print(len(its), Counter((i["test"], i["vowelled"]) for i in its), Counter(i["kind"] for i in its))
    res_all = {}
    for m in models:
        j = Judge(m, OUT / "judge_cache.jsonl", OUT / "spend.jsonl", cap=6.0, tag="calibration")
        print(f"{m}: estimate ${j.estimate(len(its)):.3f}, spent so far ${j.spent():.3f}")
        if "--go" not in a: continue
        res = j.judge(its); rows = []
        for it in its:
            r = res.get(it["id"])
            if not r: continue
            ok = r["verdict"] == ("r1" if it["test"] == "pair" else "neither")
            rows.append(dict({k: v for k, v in it.items() if k != "scan"}, verdict=r["verdict"], text=r["text"], why=r["why"], ok=ok))
        s = {}
        for name, sub in [("pair", [r for r in rows if r["test"] == "pair"]), ("pair vowelled", [r for r in rows if r["test"] == "pair" and r["vowelled"]]),
                          ("pair plain", [r for r in rows if r["test"] == "pair" and not r["vowelled"]]), ("neither", [r for r in rows if r["test"] == "neither"])]:
            s[name] = dict(n=len(sub), right=sum(r["ok"] for r in sub), verdicts=dict(Counter(r["verdict"] for r in sub)))
        res_all[m] = dict(summary=s, rows=rows, spent_this_run=j.this_run)
        print(m, json.dumps(s, ensure_ascii=False))
        for r in rows:
            if not r["ok"]: print("  miss:", r["test"], r["kind"], r["real"], "|", r["r1"], r["r2"], "->", r["verdict"], r["text"], "|", r["why"])
    if "--go" in a:
        (OUT / ("calibration_reverse.json" if "--reverse" in a else "calibration.json")).write_text(json.dumps(res_all, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
