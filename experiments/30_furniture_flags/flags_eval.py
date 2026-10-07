"""Block-level marks instead of word flags (experiment 30), scored on experiment 19's judged words with experiment 27's
verdicts and signals (judged_context.py adds the block and page context). Nothing judged or paid again.

    PYTHONPATH=src .venv/bin/python experiments/30_furniture_flags/flags_eval.py   -> out/flags_eval.json and a table

Rates are weighted as in experiments 19, 22 and 27 (N/n per document and stratum); counts are unweighted, with 95%
Wilson intervals. "Covered" = a judged error left unflagged but inside a marked block (the block's mark tells the
reader to check it).
"""
import json
import math
from pathlib import Path

from inkscript.enrich.trust import in_region, reasons, refine

HERE = Path(__file__).resolve().parent


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def base(f):
    s = dict(f["sig"], quran=tuple(f["sig"]["quran"]))
    if s["quran"][0] == "match":
        return [], s
    return refine(reasons(s), s, dict(key="k"), {"k": f["other_docs"]}), s


def rule_before(f):
    return base(f)[0]


def rule_after(rel=0.5, specific=None, tail=True):
    def r(f):
        why, s = base(f)
        kw = dict(rel=rel, tail=tail) if specific is None else dict(rel=rel, specific=specific, tail=tail)
        return in_region(why, s, f["ctx"], **kw)
    return r


def measure(F, rule):
    sw = sf = se = sfe = 0.0
    nf = nfe = ne = cov = 0
    for f in F:
        fl = bool(rule(f))
        w, t = f["weight"], f["truth"]
        sw += w
        se += w * t
        ne += t
        if fl:
            sf += w
            sfe += w * t
            nf += 1
            nfe += t
        elif t and f["ctx"]["marks"]:
            cov += 1
    return dict(words=len(F), flagged_w=sf / sw, flagged_n=nf, caught=nfe, errors=ne, caught_ci=wilson(nfe, ne),
                caught_or_covered=nfe + cov, precision=nfe / nf if nf else 0.0, precision_ci=wilson(nfe, nf),
                left_w=(se - sfe) / (sw - sf) if sw > sf else 0.0)


if __name__ == "__main__":
    F = json.load(open(HERE / "out" / "judged_context.json"))
    M = [f for f in F if f["ctx"]["marks"]]
    rules = {"before (experiment 27's rule)": rule_before}
    for rel in (0.0, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6):
        rules[f"after: in marked blocks, conf < {rel} x median, lowest tenth"] = rule_after(rel)
        rules[f"after: in marked blocks, conf < {rel} x median"] = rule_after(rel, tail=False)
    rules["after (0.5), ornament kept as specific"] = rule_after(0.5, ("quran", "gemini", "persian", "speck", "latin", "ornament"))
    res = {}
    print(f"{'rule':58s} {'set':8s} {'words':>5} {'flag%':>6} {'n':>4} {'caught':>7} {'95% CI':>13} {'+cov':>4} {'prec':>5}")
    for name, rule in rules.items():
        res[name] = {}
        for sname, S in (("all", F), ("marked", M)):
            m = measure(S, rule)
            res[name][sname] = m
            print(f"{name:58s} {sname:8s} {m['words']:5d} {100 * m['flagged_w']:6.2f} {m['flagged_n']:4d} "
                  f"{m['caught']:3d}/{m['errors']:<3d} {m['caught_ci'][0]:.2f}-{m['caught_ci'][1]:.2f} "
                  f"{m['caught_or_covered']:4d} {m['precision']:5.2f}")
    lost = [dict(doc=f["doc"], text=f["text"], conf=f["sig"]["conf"], marks=f["ctx"]["marks"], med=f["ctx"]["block_med"],
                 cause=f["cause"], why=base(f)[0]) for f in M if f["truth"] and rule_before(f) and not rule_after(0.5)(f)]
    print("errors no longer flagged word by word (covered by the block mark):", lost)
    (HERE / "out" / "flags_eval.json").write_text(json.dumps(dict(results=res, lost=lost), ensure_ascii=False, indent=1),
                                                encoding="utf-8")
