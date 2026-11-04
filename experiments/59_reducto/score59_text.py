"""Experiment 59: text accuracy on the truth pages sent to Reducto, scored exactly as exp 58 / exp 41.

    /home/appuser/inkscript/.venv/bin/python score59_text.py r1 [r1_verbatim legacy_ag ...]  -> out/text_scores.json

Same measures as experiments 41 and 58 (score41.words/bag: 1 - F1 of the word multisets, vowel marks count; folded
after inkscript.gold.text.folded; order-sensitive CER folded; letter classes; letter substitutions), on the same
pages for every reader: Azure (exp 41's lines, our text), Azure + Argon fixes (exp 41's per-page numbers), Indra
(exp 58, img300) and each Reducto variant.  Reducto's text = its blocks in its order, HTML tags removed (table cells
and line breaks become spaces, <sub>/<sup> glued to their word as printed).
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "41_azure_structure"))
sys.path.insert(0, str(E / "58_indra_ocr"))
import score41 as S  # noqa: E402
from structure import page_lines  # noqa: E402
from score58_text import CLASSES, fold_words, letter_subs, indra_lines  # noqa: E402
from inkscript.gold.text import distance, folded  # noqa: E402

OUT = HERE / "out"


def strip_html(s):
    s = re.sub(r"</t[dh]>|<br\s*/?>|</tr>|</p>|</li>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"^#+\s*", "", s, flags=re.M)
    s = s.replace("**", "")
    return s


def reducto_blocks(variant, pid):
    f = OUT / "reducto" / variant / f"{pid}.json"
    if not f.exists():
        return None
    j = json.loads(f.read_text())
    out = []
    for ch in j.get("chunks_full") or []:
        for b in ch["blocks"]:
            out.append(b)
    return out


def reducto_lines(variant, pid):
    bl = reducto_blocks(variant, pid)
    if bl is None:
        return None
    lines = []
    for b in bl:
        if b["type"] == "Figure":       # its content is a model's description of the picture, not print
            continue
        for ln in strip_html(b["content"]).split("\n"):
            if ln.strip():
                lines.append(ln.strip())
    return lines


def main(variants):
    s41 = json.loads((E / "41_azure_structure/out/scores.json").read_text())
    arts = {a["stem"]: a for a in S.sample()}
    units = [u for u in json.loads((OUT / "units59.json").read_text()) if "text" in u["sets"]]
    ids = {u["id"] for u in units}
    rows = []
    for r in s41["truth_pages"]:
        stem, p = r["stem"], r["page"]
        pid = f"{stem}_p{p:03d}"
        if pid not in ids:
            continue
        kind, doc, tl = S.truth_of(stem, p)
        dig = kind == "bd"
        cands = {"azure": [l["text"] for l in page_lines(arts[stem], p)[0]]}
        il = indra_lines("img300", pid)
        if il is not None:
            cands["indra"] = il
        for v in variants:
            rl = reducto_lines(v, pid)
            if rl is not None:
                cands["reducto/" + v] = rl
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
    names = ["azure", "indra"] + ["reducto/" + v for v in variants]
    tot = {}
    for kind in ("all", "gold", "bd"):
        rs = [x for x in rows if kind == "all" or x["kind"] == kind]
        t = {"pages": len(rs),
             "argon": sum(x["argon"]["bag_err"] for x in rs) / sum(x["argon"]["bag_n"] for x in rs)}
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
    (OUT / "text_scores.json").write_text(json.dumps(dict(rows=rows, totals=tot), ensure_ascii=False, indent=1))
    for kind, t in tot.items():
        print(f"== {kind} ({t['pages']} pages)  Azure+Argon (exp 41) {100 * t['argon']:.2f}%")
        for nm in names:
            if nm in t:
                x = t[nm]
                print(f"  {nm:22s} words wrong {100 * x['words_wrong']:5.2f}%  folded {100 * x['words_wrong_folded']:5.2f}%"
                      f"  CER folded ordered {100 * x['cer_folded_ordered']:5.2f}%")
    print("\nper page (words wrong %):")
    for x in rows:
        print(f"  {x['id']} {x['kind']:4s} " + "  ".join(
            f"{nm.split('/')[-1]} {100 * x[nm]['bag_err'] / max(x[nm]['bag_n'], 1):5.1f}" for nm in names if nm in x))


if __name__ == "__main__":
    main(sys.argv[1:])
