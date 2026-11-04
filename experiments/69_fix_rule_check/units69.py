"""Experiment 69, step 3a: every word the variants (and the saved answer) change, as comparable units.

    units69.py TAG [TAG ...]       -> out/units.jsonl, out/fixes69.jsonl

For each window page and each condition (saved answer's fixes on that page; each TAG's fixes; each TAG's fixes after
experiment 66's D30 guard, "TAG+g"), the page's Azure lines are corrected by the condition's fixes the way the
masters apply them (first occurrence of `from` in the line -> `to`), then compared with Azure's line word by word
(difflib on whitespace tokens). A UNIT is a stretch of Azure's words that some condition changes (overlapping or
touching stretches of all conditions merged), with each condition's text for it. A unit is matched to experiment
66's judged fix when the saved answer's fix touching it is that fix (same line, same from / to).
"""
from __future__ import annotations

import difflib
import json
import sys
from collections import defaultdict

import common69 as C
import run69
import d30guard43 as G
import masters43 as M43
import replay43 as RP
import rules43 as RU
from masters43 import ST


# Persian look-alikes: the pipeline's letter fix (lettersfix43) writes them as Arabic by code, whatever Gemini does,
# so units are compared after this folding
FOLD = str.maketrans({"ی": "ي", "ک": "ك", "ھ": "ه", "ہ": "ه", "ڪ": "ك", "ۀ": "ة", "ۃ": "ة"})


def apply(text: str, fixes: list) -> str:
    for f in fixes:
        frm, to = str(f.get("from") or ""), str(f.get("to") or "")
        if frm and frm in text:
            text = text.replace(frm, to, 1)
    return text


def ops(a_tok, b_tok):
    return difflib.SequenceMatcher(None, a_tok, b_tok, autojunk=False).get_opcodes()


def spans(op):
    return [(i1, i2) for t, i1, i2, j1, j2 in op if t != "equal"]


def out_for(op, b_tok, s, e):
    res = []
    for t, i1, i2, j1, j2 in op:
        if t == "equal":
            lo, hi = max(i1, s), min(i2, e)
            if lo < hi:
                res += b_tok[j1 + lo - i1:j1 + hi - i1]
        elif (i1 < i2 and s <= i1 and i2 <= e) or (i1 == i2 and s <= i1 <= e):
            res += b_tok[j1:j2]
    return " ".join(res)


def merge(iv):
    iv = sorted(iv)
    out = []
    for s, e in iv:
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def main(tags):
    W = G.lexicon()
    J = C.judged()
    pages = json.load(open(C.OUT / "pages69.json", encoding="utf-8"))
    meta = {(c["stem"], c["page"]): c for c in pages}
    sids_at = defaultdict(list)
    for c in pages:
        sids_at[(c["stem"], c["page"])] += c["sids"]
    ST.PAGES = C.OUT / "pages"
    fo = open(C.FIXES, "w", encoding="utf-8")
    uo = open(C.UNITS, "w", encoding="utf-8")
    nu = 0
    for a in run69.windows():
        p = a["first"]
        c = meta[(a["stem"], p)]
        lines = RP.chunk_lines(a, p, p)
        words = M43.azure_words(a)
        folder = C.RUNS[c["run"]][0]
        saved = json.loads((C.E43 / "out" / folder / "raw" / f"{c['chunk']}.json").read_text(encoding="utf-8"))
        conds = {"saved": [f for f in saved["answer"].get("fixes") or [] if isinstance(f, dict)
                           and RU.base_of(str(f.get("line") or ""), lines)]}
        missing = []
        for t in tags:
            rf = C.OUT / t / "raw" / f"{a['stem']}_c{p:03d}-{p:03d}.json"
            if not rf.exists():
                missing.append(t)
                continue
            ans = json.loads(rf.read_text(encoding="utf-8"))["answer"]
            fx = [f for f in ans.get("fixes") or [] if isinstance(f, dict)]
            kept = []
            for k, f in enumerate(fx):
                feat = G.features(f, lines, words, W)
                ok, why = G.decide(feat)
                fo.write(json.dumps(dict(tag=t, stem=a["stem"], page=p, k=k, line=f.get("line"), frm=f.get("from"),
                                         to=f.get("to"), why=f.get("why"), guard_keep=ok, guard_why=why,
                                         cls=feat["cls"], conf_min=feat["conf_min"]), ensure_ascii=False) + "\n")
                if ok:
                    kept.append(f)
            conds[t] = fx
            conds[t + "+g"] = kept
            conds[t + ":sic"] = [s for s in ans.get("sic") or [] if isinstance(s, dict)]
        by_line = defaultdict(dict)
        for cn, fx in conds.items():
            if cn.endswith(":sic"):
                continue
            for f in fx:
                b = RU.base_of(str(f.get("line") or ""), lines)
                if b:
                    by_line[b].setdefault(cn, []).append(f)
        for b, per in sorted(by_line.items()):
            text = lines[b]["text"]
            A = text.split()
            res = {}
            for cn in conds:
                if cn.endswith(":sic"):
                    continue
                Bt = apply(text, per.get(cn, [])).split()
                res[cn] = (ops(A, Bt), Bt)
            units = merge([s for o, _ in res.values() for s in spans(o)])
            for s, e in units:
                outs = {cn: out_for(o, Bt, s, e) for cn, (o, Bt) in res.items()}
                az = " ".join(A[s:e])
                if all(v.translate(FOLD) == az.translate(FOLD) for v in outs.values()):
                    continue
                # experiment 66's judged fix on this unit (the saved fix whose from/to make the saved text here)
                jl = None
                for sid in sids_at[(a["stem"], p)]:
                    r = J[sid]
                    if RU.base_of(r["line"], lines) == b and r["to"] and r["frm"] in text and \
                            out_for(*(lambda B2: (ops(A, B2), B2))(apply(text, [{"from": r["frm"], "to": r["to"]}]).split()), s, e) != az:
                        jl = dict(sid=sid, lab=r["lab"], why=r["lab_why"], frm=r["frm"], to=r["to"])
                ws = words(b)
                box = None
                if len(ws) == len(A) and e > s:
                    sel = ws[s:e]
                elif e > s:
                    sel = G.span_words(text, az, ws)
                else:
                    sel = ws[max(0, s - 1):s + 1] if len(ws) == len(A) else []
                if sel:
                    box = [min(w["box"][0] for w in sel), min(w["box"][1] for w in sel),
                           max(w["box"][2] for w in sel), max(w["box"][3] for w in sel)]
                confs = [w.get("conf") for w in (sel or [])]
                sics = {t: [s_ for s_ in conds.get(t + ":sic", []) if RU.base_of(str(s_.get("line") or ""), lines) == b]
                        for t in tags}
                nu += 1
                uo.write(json.dumps(dict(uid=f"{a['stem']}|{b}|{s}-{e}", stem=a["stem"], page=p, line=b, s=s, e=e,
                                         azure=az, outs=outs, judged=jl, box=box, confs=confs, text=text,
                                         run=c["run"], stratum=c["stratum"], poor=c["poor"],
                                         sic={t: [x.get("text") for x in v] for t, v in sics.items()}),
                                    ensure_ascii=False) + "\n")
        if missing:
            print("missing", a["stem"], p, missing)
        ST._az.pop(a["stem"], None)
    print(nu, "units")


if __name__ == "__main__":
    main(sys.argv[1:])
