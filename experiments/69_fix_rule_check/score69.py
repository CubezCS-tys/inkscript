"""Experiment 69, step 3c: score each condition on every judged unit.

    score69.py A B [A2 B2 ...]     pairs of tags to compare (A = with the bullet, B = without), e.g. v36 nofix
                                    -> out/score.json + printed tables

Truth of a unit: out/labels69.tsv (judged here on the scans: AZ / AZM = the print is Azure's text, a right word / a
misprint; U = not decidable; else the printed text), or experiment 66's label of the saved fix on it (G: the print is
the saved fix's text; B / M: the print is Azure's text). A condition is right on a unit when its text equals the
print (Persian look-alikes folded, Unicode NFC, spaces ignored, ٫ = . as a decimal point).
Kinds: "letters" (the outputs or the truth differ in letter shapes or digits: dots, a letter swapped / added /
dropped), "ortho" (they differ only in hamza, alif maqsura / ya, ta marbuta / ha: d30guard43.ORTH), "marks" (only
vowel marks / shadda), "punct" (only punctuation).
"""
from __future__ import annotations

import json
import random
import sys
import unicodedata
from collections import Counter, defaultdict

import common69 as C
import d30guard43 as G
from units69 import FOLD


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s.translate(FOLD)).replace("٫", ".")
    return "".join(s.split())


def letters(s: str) -> str:
    return "".join(c for c in norm(s) if unicodedata.category(c)[0] in "LN")


def lm(s: str) -> str:
    return "".join(c for c in norm(s) if unicodedata.category(c)[0] in "LNM")


def orth(s: str) -> str:
    return letters(s).translate(G.ORTH)


def labels() -> dict:
    out = {}
    for ln in open(C.OUT / "labels69.tsv", encoding="utf-8"):
        if ln.strip() and not ln.startswith("#"):
            uid, truth, *why = ln.rstrip("\n").split("\t")
            out[uid] = truth
    return out


def truth_of(u, L):
    if u["uid"] in L:
        t = L[u["uid"]]
        if t == "U":
            return None, None
        if t in ("AZ", "AZM"):
            return u["azure"], t
        return t, "text"
    j = u.get("judged")
    if j and j["lab"] in "GBM":
        if j["lab"] == "G":
            return u["outs"]["saved"], "G66"
        return u["azure"], "AZM" if j["lab"] == "M" else "AZ"
    return None, None


def kind(u, t):
    vals = [v for k, v in u["outs"].items()] + [u["azure"], t]
    if len({orth(v) for v in vals}) > 1:
        return "letters"
    if len({letters(v) for v in vals}) > 1:
        return "ortho"
    if len({lm(v) for v in vals}) > 1:
        return "marks"
    return "punct"


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return round((c - h) / d, 3), round((c + h) / d, 3)


def boot(rows, f, B=4000, seed=69):
    """95% interval of f(rows) resampling pages."""
    by = defaultdict(list)
    for r in rows:
        by[r["page_key"]].append(r)
    keys = sorted(by)
    rnd = random.Random(seed)
    vals = []
    for _ in range(B):
        s = [r for k in (rnd.choice(keys) for _ in keys) for r in by[k]]
        vals.append(f(s))
    vals.sort()
    return vals[int(0.025 * B)], vals[int(0.975 * B)]


def main(tags):
    L = labels()
    U = list(C.jlines(C.UNITS))
    pairs = [(tags[i], tags[i + 1]) for i in range(0, len(tags), 2)]
    conds = [c for a, b in pairs for c in (a, b, a + "+g", b + "+g")]
    rows, und = [], Counter()
    for u in U:
        if any(c not in u["outs"] for c in conds):
            continue
        o = {c: norm(u["outs"][c]) for c in conds}
        if len(set(o.values())) <= 1:
            continue                                     # every condition writes the same: no difference to score
        t, tk = truth_of(u, L)
        if t is None:
            und[u["stratum"]] += 1
            continue
        az = norm(u["azure"])
        r = dict(uid=u["uid"], page_key=f"{u['stem']}|{u['page']}", stratum=u["stratum"], poor=u["poor"],
                 kind=kind(u, t), truth_kind=tk, azure_right=(norm(t) == az), judged66=bool(u.get("judged")),
                 right={c: o[c] == norm(t) or (kind(u, t) == "letters" and letters(o[c]) == letters(t))
                        for c in conds},
                 changed={c: o[c] != az for c in conds})
        rows.append(r)
    res = dict(units_scored=len(rows), undecidable=sum(und.values()), by_pair={})
    for a, b in pairs:
        for g in ("", "+g"):
            A, Bc = a + g, b + g
            for subset_name, sub in (("all", rows), ("letters", [r for r in rows if r["kind"] == "letters"]),
                                     ("letters, poor print", [r for r in rows if r["kind"] == "letters" and r["poor"]]),
                                     ("letters, clean print", [r for r in rows if r["kind"] == "letters" and not r["poor"]]),
                                     ("ortho (hamza, ya, ta marbuta)", [r for r in rows if r["kind"] == "ortho"]),
                                     ("marks", [r for r in rows if r["kind"] == "marks"]),
                                     ("punct", [r for r in rows if r["kind"] == "punct"])):
                d = [r for r in sub if r["right"][A] != r["right"][Bc]]
                aw = sum(r["right"][A] for r in d)
                bw = len(d) - aw
                # how each disagreement arises: one abstains (keeps Azure) while the other changes the word
                cnt = Counter()
                for r in d:
                    who = A if r["right"][A] else Bc
                    other = Bc if who == A else A
                    if not r["changed"][who] and r["changed"][other]:
                        cnt[f"{who} kept the print (other's change wrong)"] += 1
                    elif r["changed"][who] and not r["changed"][other]:
                        cnt[f"{who} fixed (other kept Azure's misreading)"] += 1
                    else:
                        cnt[f"{who} right, both changed"] += 1
                ci = boot(sub, lambda s: sum(r["right"][A] for r in s) - sum(r["right"][Bc] for r in s)) if sub else None
                res["by_pair"][f"{A} vs {Bc} | {subset_name}"] = dict(
                    units=len(sub), right_A=sum(r["right"][A] for r in sub), right_B=sum(r["right"][Bc] for r in sub),
                    differ=len(d), A_better=aw, B_better=bw, net_A_minus_B=aw - bw, net_ci95_pages=ci, how=dict(cnt))
    C.jdump(C.OUT / "score.json", res)
    C.jdump(C.OUT / "score_rows.json", rows, indent=0)
    print(f"units scored {len(rows)}; not decidable {sum(und.values())} {dict(und)}")
    for k, v in res["by_pair"].items():
        print(f"{k:55s} n={v['units']:3d} right {v['right_A']:3d} vs {v['right_B']:3d}  differ {v['differ']:3d}: "
              f"A better {v['A_better']:3d}, B better {v['B_better']:3d}, net {v['net_A_minus_B']:+d} {v['net_ci95_pages']}")
        for h, n in sorted(v["how"].items()):
            print(f"{'':58s}{n:3d}  {h}")


if __name__ == "__main__":
    main(sys.argv[1:])
