"""Experiment 58: text accuracy on exp 41's 34 truth pages (20 owner gold, 14 born-digital), no calls.

    /home/appuser/inkscript/.venv/bin/python score58_text.py img300 [pdf200 ...]   -> out/text_scores.json

Measures (exp 41's own functions, imported read-only from 41_azure_structure/score41.py):
  words wrong          1 - F1 of the word multisets vs the truth (vowel marks count, punctuation and tatweel ignored,
                       tanween+alef either order; born-digital digits folded) -- exp 41's headline measure
  words wrong, folded  the same after inkscript.gold.text.folded (vowel marks, alef/hamza forms, ى/ي, ة/ه, Persian
                       look-alikes, digits folded: what search needs)
  CER folded, ordered  edit distance of the page text in the reader's own line order / truth chars (order counts)
  letters              letter classes counted in truth vs reader (Persian ی ک, vowel marks, hamza forms, ة/ه) and the
                       letter substitutions from aligned words
Azure = Azure's lines in Azure's order (exp 41's "azure"); Argon = exp 41's argon run (copied from out/scores.json).
"""
from __future__ import annotations

import difflib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "41_azure_structure"))
import score41 as S  # noqa: E402
from structure import page_lines  # noqa: E402
from inkscript.gold.text import distance, faithful, folded  # noqa: E402

OUT = HERE / "out"
HARAKAT = set("ًٌٍَُِّْٰ")
HAMZA = set("أإآءئؤ")
CLASSES = {"Persian ی": set("ی"), "Persian ک": set("ک"), "vowel marks": HARAKAT, "hamza forms": HAMZA,
           "ة": set("ة"), "ى": set("ى")}


def fold_words(lines, dig):
    s = " ".join(lines)
    if dig:
        s = s.translate(S.DIG)
    return Counter(folded(s).split())


def letter_subs(truth_lines, read_lines):
    """Substituted letters inside aligned words (faithful text), as 'truth>read' pairs."""
    t = faithful(" ".join(truth_lines)).split()
    r = faithful(" ".join(read_lines)).split()
    out = Counter()
    sm = difflib.SequenceMatcher(None, t, r, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "replace":
            continue
        for a, b in zip(t[i1:i2], r[j1:j2]):
            cm = difflib.SequenceMatcher(None, a, b, autojunk=False)
            for o, x1, x2, y1, y2 in cm.get_opcodes():
                if o == "replace" and x2 - x1 == y2 - y1:
                    for c1, c2 in zip(a[x1:x2], b[y1:y2]):
                        out[f"{c1}>{c2}"] += 1
                elif o == "delete":
                    for c in a[x1:x2]:
                        out[f"{c}>∅"] += 1
                elif o == "insert":
                    for c in b[y1:y2]:
                        out[f"∅>{c}"] += 1
    return out


def indra_lines(variant, pid):
    f = OUT / "indra" / variant / f"{pid}.json"
    if not f.exists():
        return None
    return [ln["text"] for ln in json.loads(f.read_text())["lines"] if ln["text"].strip()]


def main(variants):
    s41 = json.loads((E / "41_azure_structure/out/scores.json").read_text())
    arts = {a["stem"]: a for a in S.sample()}
    rows = []
    for r in s41["truth_pages"]:
        stem, p = r["stem"], r["page"]
        pid = f"{stem}_p{p:03d}"
        kind, doc, tl = S.truth_of(stem, p)
        dig = kind == "bd"
        cands = {"azure": [l["text"] for l in page_lines(arts[stem], p)[0]]}
        for v in variants:
            il = indra_lines(v, pid)
            if il is not None:
                cands["indra/" + v] = il
        row = dict(id=pid, kind=kind, truth_words=sum(S.words(tl, dig).values()),
                   argon=dict(bag_err=r["argon"]["bag_err"], bag_n=r["argon"]["bag_n"]))
        tf = folded(" ".join(tl).translate(S.DIG) if dig else " ".join(tl))
        for name, pl in cands.items():
            e, n = S.bag(S.words(pl, dig), S.words(tl, dig))
            fe, fn = S.bag(fold_words(pl, dig), fold_words(tl, dig))
            pf = folded(" ".join(pl).translate(S.DIG) if dig else " ".join(pl))
            cls = {k: [sum(c in ch for c in " ".join(tl)), sum(c in ch for c in " ".join(pl))]
                   for k, ch in CLASSES.items()}
            row[name] = dict(bag_err=e, bag_n=n, fbag_err=fe, fbag_n=fn, fcer=distance(pf, tf), fchars=len(tf),
                             classes=cls, subs=dict(letter_subs(tl, pl).most_common()))
        rows.append(row)
    # totals
    names = ["azure"] + ["indra/" + v for v in variants]
    tot = {}
    for kind in ("all", "gold", "bd"):
        rs = [x for x in rows if kind == "all" or x["kind"] == kind]
        t = {"pages": len(rs), "argon words wrong": sum(x["argon"]["bag_err"] for x in rs) / sum(x["argon"]["bag_n"] for x in rs)}
        for nm in names:
            rr = [x[nm] for x in rs if nm in x]
            if len(rr) < len(rs):
                continue
            t[nm] = dict(words_wrong=sum(x["bag_err"] for x in rr) / sum(x["bag_n"] for x in rr),
                         words_wrong_folded=sum(x["fbag_err"] for x in rr) / sum(x["fbag_n"] for x in rr),
                         cer_folded_ordered=sum(x["fcer"] for x in rr) / sum(x["fchars"] for x in rr))
            cls = Counter()
            for x in rr:
                for k, (a, b) in x["classes"].items():
                    cls[k + " truth"] += a
                    cls[k + " read"] += b
            t[nm]["classes"] = dict(cls)
            subs = Counter()
            for x in rr:
                subs.update(x["subs"])
            t[nm]["top_subs"] = subs.most_common(40)
        tot[kind] = t
    res = dict(rows=rows, totals=tot)
    (OUT / "text_scores.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for kind, t in tot.items():
        print(f"== {kind} ({t['pages']} pages)  Argon (exp 41) {100 * t['argon words wrong']:.2f}%")
        for nm in names:
            if nm in t:
                x = t[nm]
                print(f"  {nm:22s} words wrong {100 * x['words_wrong']:5.2f}%  folded {100 * x['words_wrong_folded']:5.2f}%"
                      f"  CER folded ordered {100 * x['cer_folded_ordered']:5.2f}%")


if __name__ == "__main__":
    main(sys.argv[1:])
