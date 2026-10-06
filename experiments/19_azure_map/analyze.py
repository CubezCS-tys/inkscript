"""Turn the verdicts into the map: error rate by stratum, decade, print class; kinds of error; does Azure's confidence
predict them?  -> out/summary.json, out/judged.json

Final verdict per word: Flash's RIGHT stands; a word Flash did not call RIGHT takes Pro's verdict (Pro's RIGHT clears it).
Kinds come from comparing Azure's reading with the judge's text (short vowels and kashida removed):
  punct     only punctuation differs (not a letter error)
  ya ta hamza dots   one look-alike class (ى/ي, ة/ه, hamza forms, same skeleton with other dots)
  digits    a digit differs
  latin     the word is Latin and differs
  space     the same letters, split or merged differently
  edge      the judge's text is Azure's minus a first or last letter (a letter the tint did not reach, or Azure added it)
  drop/add  Azure dropped / added one letter inside the word
  other     anything bigger
  box       the yellow area did not hold one word (a boxing fault, not a reading fault)
  unsure    the ink cannot settle it
A *letter error* is any wrong verdict except punct (and box, unsure). Rates are weighted (each sampled word stands for
N/n words of its document and stratum), 95% intervals by bootstrap over documents (2,000 draws).
"""
import json, re, sys, random
from pathlib import Path
from collections import Counter, defaultdict
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
sys.path.insert(0, str(HERE))
import judge1 as J
import strata as S
FLASH, PRO = "gemini-3.8-flash", "gemini-3.1-pro-preview"
TASH = re.compile("[ً-ْٰـ]")
PUNCT = re.compile(r"[^\wء-ي٠-٩۰-۹کی]|_")
HAM = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ئ": "ى", "ء": None})
RASM = str.maketrans({c: g[0] for g in ["بتثنيى", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق", "هة"] for c in g})
DIG = re.compile(r"[0-9٠-٩۰-۹]")
LETTER_KINDS = ["dots", "hamza", "ya", "ta", "drop", "add", "edge", "space", "digits", "latin", "other"]


def plain(s): return TASH.sub("", s or "").strip()


def kind(az, ju):
    a, j = plain(az), plain(ju)
    if a == j: return "harakat"
    pa, pj = PUNCT.sub("", a), PUNCT.sub("", j)
    if pa == pj: return "punct"
    if S.LATIN.search(pa + pj): return "latin"
    if DIG.search(pa + pj) and DIG.sub("", pa) == DIG.sub("", pj): return "digits"
    if DIG.search(pa + pj): return "digits"
    if pa.replace(" ", "") == pj.replace(" ", ""): return "space"
    if len(pa) == len(pj):
        diff = [(x, y) for x, y in zip(pa, pj) if x != y]
        if all({x, y} == {"ى", "ي"} for x, y in diff): return "ya"
        if all({x, y} == {"ة", "ه"} for x, y in diff): return "ta"
    if pa.translate(HAM) == pj.translate(HAM): return "hamza"
    if len(pa) == len(pj) and pa.translate(RASM) == pj.translate(RASM): return "dots"
    if pa.translate(HAM).translate(RASM) == pj.translate(HAM).translate(RASM): return "dots"
    if len(pa) == len(pj) + 1 and (pa[1:] == pj or pa[:-1] == pj): return "edge"
    if len(pa) == len(pj) + 1 and any(pa[:k] + pa[k + 1:] == pj for k in range(len(pa))): return "add"
    if len(pj) == len(pa) + 1 and any(pj[:k] + pj[k + 1:] == pa for k in range(len(pj))): return "drop"
    return "other"


def final():
    sample = json.load(open(OUT / "sample.json")); f = J.cached(FLASH); p = J.cached(PRO)
    rows = []
    for w in sample:
        rf = f.get(w["id"] + J.VERSION)
        if rf is None: continue
        rp = p.get(w["id"] + J.VERSION) if rf["verdict"] != "right" else None
        r = rp or rf
        v = r["verdict"]; k = None
        if v == "wrong": k = kind(w["text"], r["text"])
        elif v in ("box", "unsure"): k = v
        if k == "harakat": v, k = "right", None          # the judge wrote the same letters: nothing wrong with them
        err = v == "wrong" and k not in ("punct",)
        rows.append(dict(w, flash=rf["verdict"], flash_text=rf["text"], pro=rp["verdict"] if rp else None, pro_text=rp["text"] if rp else None,
                         verdict=v, judge=r["text"], why=r["why"], harakat=r.get("harakat"), kind=k, err=bool(err),
                         punct=v == "wrong" and k == "punct", w=w["N"] / w["n"]))
    return rows


def rate(rows, key="err"):
    sw = sum(r["w"] for r in rows); return sum(r["w"] * r[key] for r in rows) / sw if sw else float("nan")


def boot(rows, key="err", reps=2000, seed=19):
    by = defaultdict(list)
    for r in rows: by[r["doc"]].append(r)
    docs = list(by); rng = random.Random(seed); vals = []
    for _ in range(reps):
        pick = [r for d in (rng.choice(docs) for _ in docs) for r in by[d]]
        if pick: vals.append(rate(pick, key))
    vals.sort(); return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def block(rows, key="err"):
    lo, hi = boot(rows, key) if rows else (float("nan"),) * 2
    return dict(n=len(rows), errors=sum(r[key] for r in rows), docs=len({r["doc"] for r in rows}), rate=rate(rows, key), lo=lo, hi=hi)


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]; neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg: return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


if __name__ == "__main__":
    rows = final(); docs = json.load(open(OUT / "docs.json")); pop = json.load(open(OUT / "population.json"))
    out = dict(n_words=len(rows), n_docs=len({r["doc"] for r in rows}))
    out["docs"] = dict(drawn=len(docs), kinds=dict(Counter(d["kind"] for d in docs.values())),
                       born_digital_by_decade={dec: dict(Counter(d["kind"] for d in docs.values() if ((d.get("year") or "?")[:3] + "0s") == dec))
                                               for dec in sorted({(d.get("year") or "?")[:3] + "0s" for d in docs.values()})})
    out["overall"] = block(rows); out["overall_with_punct"] = block([dict(r, e2=r["err"] or r["punct"]) for r in rows], "e2")
    out["box"] = block([dict(r, b=r["verdict"] == "box") for r in rows], "b")
    out["unsure"] = block([dict(r, b=r["verdict"] == "unsure") for r in rows], "b")
    out["strata"] = {st: dict(block([r for r in rows if r["stratum"] == st]), label=S.LABEL[st],
                              share=sum(p["N"].get(st, 0) for p in pop.values()) / sum(p["words"] for p in pop.values()))
                     for st in S.STRATA}
    dec = lambda r: ((docs[r["doc"]].get("year") or "?")[:3] + "0s") if (docs[r["doc"]].get("year") or "?")[:1] in "12" else "unknown"
    out["decades"] = {d: block([r for r in rows if dec(r) == d]) for d in sorted({dec(r) for r in rows})}
    out["print"] = {k: block([r for r in rows if docs[r["doc"]]["kind"] == k]) for k in ("scan", "scan+real-font")}
    out["kinds"] = dict(Counter(r["kind"] for r in rows if r["kind"]))
    out["kinds_by_stratum"] = {st: dict(Counter(r["kind"] for r in rows if r["kind"] and r["stratum"] == st)) for st in S.STRATA}
    # Per document: how concentrated are the errors?
    per = defaultdict(lambda: [0, 0, 0.0])
    for r in rows: per[r["doc"]][0] += 1; per[r["doc"]][1] += r["err"]
    out["per_doc"] = sorted([dict(doc=d, n=v[0], errors=v[1], year=docs[d].get("year"), journal=docs[d].get("journal")) for d, v in per.items()], key=lambda x: -x["errors"] / x["n"])
    # Confidence
    cr = [r for r in rows if r["conf"] is not None and r["verdict"] in ("right", "wrong")]
    out["confidence"] = dict(auc=auc([1 - r["conf"] for r in cr], [r["err"] for r in cr]), n=len(cr), errors=sum(r["err"] for r in cr))
    th = []
    for t in (0.5, 0.7, 0.8, 0.9, 0.95, 0.98):
        lowr = [r for r in cr if r["conf"] < t]
        we = sum(r["w"] * r["err"] for r in cr); wl = sum(r["w"] for r in lowr)       # weighted: as the archive would see it
        th.append(dict(t=t, flagged_share=rate([dict(r, f=r["conf"] < t) for r in cr], "f"),
                       recall=sum(r["w"] * r["err"] for r in lowr) / we if we else float("nan"),
                       precision=sum(r["w"] * r["err"] for r in lowr) / wl if wl else float("nan"), flagged_n=len(lowr),
                       errors_caught_n=sum(r["err"] for r in lowr)))
    out["confidence"]["thresholds"] = th
    # Encoding slips (code-level, every word of every scanned document)
    out["encoding_slips"] = dict(words=sum(p["words"] for p in pop.values()), slips=sum(sum(p["slips"].values()) for p in pop.values()),
                                 docs_with=sum(1 for p in pop.values() if sum(p["slips"].values())))
    # Harakat on vowelled words
    vw = [r for r in rows if S.HARAKAT.search(r["text"]) and r["verdict"] == "right"]
    out["harakat"] = dict(n=len(vw), differ=sum(r["harakat"] == "DIFFER" for r in vw))
    out["flash_pro"] = dict(flagged_by_flash=sum(r["flash"] != "right" for r in rows), pro_cleared=sum(r["pro"] == "right" for r in rows))
    # The agent's look at every letter error (out/look.json: id -> [cause, note]); not the owner's.
    lk = json.load(open(OUT / "look.json")) if (OUT / "look.json").exists() else {}
    TEXT = {"misread", "hamza added", "ya", "superscript", "ligature", "encoding", "latin"}; NOTTEXT = {"speck", "decorative", "handwriting"}
    for r in rows: r["cause"] = (lk.get(r["id"]) or [None])[0] if r["err"] else None
    if lk:
        out["causes"] = dict(Counter(r["cause"] for r in rows if r["err"]))
        out["confirmed"] = block([dict(r, c=r["err"] and r["cause"] in TEXT | NOTTEXT) for r in rows], "c")
        out["printed_text"] = block([dict(r, c=r["err"] and r["cause"] in TEXT) for r in rows], "c")
        out["printed_arabic"] = block([dict(r, c=r["err"] and r["cause"] in TEXT - {"latin"}) for r in rows], "c")
        out["not_text"] = block([dict(r, c=r["err"] and r["cause"] in NOTTEXT) for r in rows], "c")
        out["cause_rates"] = {c: block([dict(r, c=r["cause"] == c) for r in rows], "c") for c in out["causes"]}
        out["conf_by_cause"] = {c: dict(n=sum(1 for r in rows if r["cause"] == c), below_08=sum(1 for r in rows if r["cause"] == c and (r["conf"] or 0) < 0.8),
                                        median_conf=sorted(r["conf"] or 0 for r in rows if r["cause"] == c)[sum(1 for r in rows if r["cause"] == c) // 2])
                                for c in out["causes"]}
    out["spend"] = J.spent()
    json.dump(rows, open(OUT / "judged.json", "w"), ensure_ascii=False, indent=0)
    json.dump(out, open(OUT / "summary.json", "w"), ensure_ascii=False, indent=1)
    o = out
    print(f"{o['n_words']} words / {o['n_docs']} docs  overall {o['overall']['rate']:.2%} [{o['overall']['lo']:.2%}, {o['overall']['hi']:.2%}] ({o['overall']['errors']} errors)")
    for st, b in o["strata"].items(): print(f"  {st:10s} n={b['n']:4d} err={b['errors']:3d} {b['rate']:.2%} [{b['lo']:.2%}, {b['hi']:.2%}] share={b['share']:.1%}")
    for d, b in o["decades"].items(): print(f"  {d:8s} n={b['n']:4d} docs={b['docs']} err={b['errors']:3d} {b['rate']:.2%} [{b['lo']:.2%}, {b['hi']:.2%}]")
    print(" print", {k: (b["n"], b["errors"], round(b["rate"], 4)) for k, b in o["print"].items()})
    print(" kinds", o["kinds"]); print(" conf", o["confidence"]); print(" slips", o["encoding_slips"], " harakat", o["harakat"], o["flash_pro"])
    for k in ("confirmed", "printed_text", "printed_arabic", "not_text"):
        if k in o: print(f" {k:15s} {o[k]['errors']:3d}  {o[k]['rate']:.2%} [{o[k]['lo']:.2%}, {o[k]['hi']:.2%}]")
    if "conf_by_cause" in o: print(" conf by cause", o["conf_by_cause"])
    print(" box", o["box"]["errors"], " unsure", o["unsure"]["errors"], " with punct", round(o["overall_with_punct"]["rate"], 4))
