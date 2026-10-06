"""Fewer false flags without losing caught errors: the product's trust rule (src/inkscript/enrich/trust.py) and
candidate refinements, scored on experiment 19's judged words (truth as experiment 22 defines it; verdicts
reused, nothing paid).

    python flags_eval.py features      -> out/flag_features.json  (product signals for every judged word)
    python flags_eval.py               -> out/flag_eval.json and a table

Each judged word is found in the product's own reading of its document (enrich.document.load) by page and box;
its signals are the product's (trust.signals, ink on the scan), plus what the refinements need: the paragraph
role and page-1 title (jats.front_matter), the word's matching key counted among the document's other confident
readings, and in other documents (out/lexicon.json.gz, built by lexicon.py; the word's own document left out).
Rates are weighted as in experiments 19 and 22 (N/n per document and stratum), counts unweighted beside them.
"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
E22 = Path("/home/yassine/inkscript/experiments/22_trust/out")


def features():
    from inkscript.enrich import trust as T
    from inkscript.enrich.document import load, is_real
    from inkscript.enrich.jats import front_matter
    from inkscript.enrich.quran import check_document, norm
    rows = json.load(open(E22 / "judged_signals.json"))["rows"]
    lex = json.load(gzip.open(OUT / "lexicon.json.gz", "rt", encoding="utf-8"))
    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["doc"]].append(r)
    out = []
    for n, (stem, rs) in enumerate(sorted(by_doc.items()), 1):
        d = E19 / "docs" / stem
        doc = load(d / f"{stem}.json")
        quotes = check_document(doc)
        sig = T.signals(doc, quotes, None)
        pages = {r["page"] for r in rs}
        sub = dict(words=[w for w in doc["words"] if w["page"] in pages])
        ink = T._ink(d / f"{stem}.pdf", sub)
        fm = front_matter(doc)
        title_paras = set([fm["title"]] + fm.get("rubric", []) + fm.get("authors", [])) if fm else set()
        same = Counter(w["n"] for w in doc["words"] if (w["conf"] or 0) >= 0.95 and w["n"])
        for r in rs:
            cand = [w for w in doc["words"] if w["page"] == r["page"]
                    and all(abs(a - b) <= 3 for a, b in zip(w["box"], r["box"]))]
            if not cand:
                out.append(dict(id=r["id"], found=False))
                continue
            w = cand[0]
            s = dict(sig[w["idx"]])
            s["ink"] = ink.get(w["idx"], 0.0)
            k = w["n"]
            mine = same[k] - (1 if (w["conf"] or 0) >= 0.95 and k else 0)
            other = {doc_: c for doc_, c in lex.get(k, {}).items() if doc_ != stem} if k else {}
            out.append(dict(id=r["id"], found=True, doc=stem, page=w["page"], text=w["text"], real=is_real(w["text"]),
                            sig={**s, "quran": list(s["quran"])}, role=doc["roles"][w["para"]],
                            title=w["para"] in title_paras, same_doc=mine, other_docs=len(other),
                            other_count=sum(other.values()), weight=r["w"], stratum=r["stratum"], year=r["year"],
                            truth=bool(r["err"]) and r["cause"] != "judge wrong"
                            and not (r["cause"] == "encoding" and not r["persian"]), cause=r["cause"],
                            judge=r["judge"], verdict=r["verdict"]))
        print(f"{n}/{len(by_doc)} {stem}", flush=True)
    (OUT / "flag_features.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- rules

def product(f):
    """The product's rule as of experiment 24 (trust.reasons), on the product's own signals."""
    from inkscript.enrich.trust import reasons
    s = dict(f["sig"], quran=tuple(f["sig"]["quran"]))
    if s["quran"][0] == "match":
        return []                                            # verified: never flagged
    return reasons(s)


def local_refine(why, s, ctx, title_conf=None, lex=None, same=None):
    if why != ["conf"]:
        return why
    c = s["conf"]
    if title_conf is not None and (ctx["title"] or s["h_rel"] >= 1.5) and c >= title_conf:
        return []
    if lex and ctx["other_docs"] >= lex[0] and c >= lex[1]:
        return []
    if same and ctx["same_doc"] >= same[0] and c >= same[1]:
        return []
    return why


def refined(f, **kw):
    from inkscript.enrich.trust import reasons
    kw.pop("local", None)
    s = dict(f["sig"], quran=tuple(f["sig"]["quran"]))
    if s["quran"][0] == "match":
        return []
    return local_refine(reasons(s), s, dict(title=f["title"], role=f["role"], same_doc=f["same_doc"],
                                            other_docs=f["other_docs"]), **kw)


def product27(f):
    """The product's rule since experiment 27 (trust.refine), the lexicon counted without the word's own document."""
    from inkscript.enrich.trust import reasons, refine
    s = dict(f["sig"], quran=tuple(f["sig"]["quran"]))
    if s["quran"][0] == "match":
        return []
    return refine(reasons(s), s, dict(key="k"), {"k": f["other_docs"]})


def measure(rows, rule):
    sw = sf = se = sfe = 0.0
    nf = nfe = ne = 0
    lost = []
    for r in rows:
        fl = bool(rule(r))
        w = r["weight"]
        sw += w
        se += w * r["truth"]
        ne += r["truth"]
        if fl:
            sf += w
            sfe += w * r["truth"]
            nf += 1
            nfe += r["truth"]
        elif r["truth"]:
            lost.append(r)
    return dict(flagged=sf / sw, caught_w=sfe / se, left=(se - sfe) / (sw - sf), precision_w=sfe / sf if sf else 0,
                n_flagged=nf, n_caught=nfe, n_errors=ne, precision_n=nfe / nf if nf else 0), lost


if __name__ == "__main__":
    if sys.argv[1:2] == ["features"]:
        features()
        sys.exit()
    F = [f for f in json.load(open(OUT / "flag_features.json")) if f.get("found") and f["real"]]
    print(len(F), "judged words found in the product's reading,", sum(f["truth"] for f in F), "errors")
    base, base_lost = measure(F, product)
    res = {"product (experiment 24)": base}
    print(f"{'rule':58s} {'flag%':>6} {'n':>4} {'caught':>7} {'prec':>6} {'left%':>6}")
    show = lambda name, m: print(f"{name:58s} {100 * m['flagged']:6.2f} {m['n_flagged']:4d} {m['n_caught']:3d}/{m['n_errors']:<3d} "
                                 f"{m['precision_n']:6.3f} {100 * m['left']:6.3f}")
    show("product (experiment 24)", base)
    variants = {
        "title: conf flag on title/large type only below 0.5": dict(title_conf=0.5, lex=None, same=None),
        "lexicon: conf flag dropped if >=5 other docs & conf>=0.5": dict(title_conf=None, lex=(5, 0.5), same=None),
        "lexicon: >=10 other docs & conf>=0.5": dict(title_conf=None, lex=(10, 0.5), same=None),
        "lexicon: >=5 other docs & conf>=0.6": dict(title_conf=None, lex=(5, 0.6), same=None),
        "same doc: >=2 confident readings elsewhere & conf>=0.5": dict(title_conf=None, lex=None, same=(2, 0.5)),
        "same doc: >=3 & conf>=0.6": dict(title_conf=None, lex=None, same=(3, 0.6)),
        "title + lexicon(5, 0.5)": dict(title_conf=0.5, lex=(5, 0.5), same=None),
        "title + lexicon(5, 0.6)": dict(title_conf=0.5, lex=(5, 0.6), same=None),
        "title + lexicon(5, 0.5) + same(2, 0.5)": dict(title_conf=0.5, lex=(5, 0.5), same=(2, 0.5)),
    }
    lost_by = {}
    CHOSEN = "product (experiment 27): + common word at conf >= 0.6 not flagged"
    m, lost = measure(F, product27)
    res[CHOSEN] = m
    lost_by[CHOSEN] = [dict(text=f["text"], cause=f["cause"], judge=f["judge"], conf=f["sig"]["conf"]) for f in lost if f not in base_lost]
    show(CHOSEN, m)
    for name, kw in variants.items():
        m, lost = measure(F, lambda f, kw=kw: refined(f, **kw))
        res[name] = m
        lost_by[name] = [dict(text=f["text"], cause=f["cause"], judge=f["judge"], conf=f["sig"]["conf"], stratum=f["stratum"])
                         for f in lost if f not in base_lost]
        show(name, m)
    for name, l in lost_by.items():
        if l:
            print(" lost by", name, l)
    (OUT / "flag_eval.json").write_text(json.dumps(dict(results=res, lost=lost_by, chosen=CHOSEN), ensure_ascii=False, indent=1),
                                        encoding="utf-8")
