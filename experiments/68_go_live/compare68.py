"""Experiment 68: the rebuild with experiment 66's D30 guard changes printed text ONLY where the guard refused a fix.

For each of the four runs, experiment 65's masters (<run>_fix61) vs this rebuild (<run>_fix61_d30):
  * ALTO words page by page and the text of every JATS element the ALTO points at (compare65's readers); every
    difference must be a refused fix: the old text holds Gemini's word ('to'), the new one Azure's ('from');
  * every refusal experiment 66 simulated (simulate66.py run -> out/decisions.jsonl, keep = false) must appear in the
    new JATS as named-content[@content-type="model-suggestion"] (text = Azure's word, xlink:title = Gemini's) and NOT
    in back/notes reader-fixes;
  * the guard's own log (plain/rules/*.json rules43.fixes_refused_d30) counted beside it.

    compare68.py [run ...]      -> out/compare68.json, a summary on stdout
"""
from __future__ import annotations

import difflib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "65_fix_leaks"))
import compare65 as C  # noqa: E402

E43 = HERE.parent / "43_rehearsal" / "out"
RUNS = {"j0130_final": "j0130_final", "v2_55": "v2_55", "v33_300b_fix3_lettersfix": "v33_300b_fix3_lettersfix",
        "v33_300_final_lettersfix": "v33_300_final_lettersfix"}
XL = "{http://www.w3.org/1999/xlink}"


def refused66():
    out = defaultdict(list)
    for ln in open(HERE.parent / "66_d30_guard" / "out" / "decisions.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        if not r["keep"]:
            out[(r["run"], r["stem"])].append(r)
    return out


def chunks(a: list[str], b: list[str]):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return [(" ".join(a[i1:i2]), " ".join(b[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]


def explained(old: str, new: str, refs: list[dict]) -> bool:
    """old (exp 65) -> new (guard): undo refused fixes in old (to -> from) and get new."""
    for r in refs:              # a multi-word fix ('إذا شعرت' -> 'إذ شعرت'): the word diff shows only its changed part
        if (old, new) in chunks((r["to"] or "").split(), (r["frm"] or "").split()):
            return True
    t = old
    for r in sorted(refs, key=lambda r: -len(r["to"])):
        if r["to"] in t:
            t = t.replace(r["to"], r["frm"])
    return " ".join(t.split()) == " ".join(new.split())


def flags(jats: Path):
    """(inline model-suggestion spans, back-note flags whose why is the guard's, reader fixes) as
    (from, to, line) / (from, to) tuples."""
    root = etree.parse(str(jats)).getroot()
    ms = [(" ".join("".join(e.itertext()).split()), e.get(XL + "title")) for e in root.iter("named-content")
          if e.get("content-type") == "model-suggestion"]
    notes, fixes = [], []
    for n in root.iter("notes"):
        for p in n.findall("p"):
            nc = {x.get("content-type"): " ".join("".join(x.itertext()).split()) for x in p.iter("named-content")}
            if n.get("notes-type") == "reader-fixes":
                fixes.append((nc.get("azure-reading"), nc.get("print"), nc.get("alto-line")))
            elif n.get("notes-type") == "suspected-misprints" and (nc.get("why") or "").startswith(
                    "model suggestion, not applied (D30 guard"):
                notes.append((nc.get("printed"), nc.get("proposed-correction"), nc.get("alto-line")))
    return ms, notes, fixes


def guard_log(run: str) -> dict:
    out = defaultdict(list)
    for f in (E43 / f"{run}_fix61_d30" / "plain" / "rules").glob("*.json"):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for r in ((j.get("rules43") or {}).get("fixes_refused_d30")) or []:
            out[j.get("stem") or f.name.split("_c")[0]].append(dict(line=str(r.get("line")), frm=r.get("from"),
                                                                     to=r.get("to")))
    return out


def one(run: str, R: dict) -> dict:
    old, new = E43 / f"{run}_fix61" / "masters", E43 / f"{run}_fix61_d30" / "masters"
    rep = dict(run=run, masters=0, alto_same=0, blocks_same=0, alto_chunks=0, alto_unexplained=[],
               block_chunks=0, blocks_unexplained=[], refused66=0, flag_found=0, flag_missing_inline=[],
               note_found=0, note_missing=[], still_fixed=[], flags_model_suggestion=0, notes_model_suggestion=0,
               guard_log_refused=0, guard_still_fixed=[], guard_note_missing=[], sim_not_live=[], live_not_sim=[],
               words_old=0, words_new=0)
    G = guard_log(run)
    for oj in sorted(old.glob("*.jats.xml")):
        stem = oj.name[:-len(".jats.xml")]
        nj = new / oj.name
        refs = R.get((RUNS[run], stem), [])
        both = refs + G.get(stem, [])
        rep["masters"] += 1
        oa, na = old / f"{stem}.alto.xml", new / f"{stem}.alto.xml"
        wo, wn = C.alto_words(oa), C.alto_words(na)
        rep["words_old"] += sum(not w.startswith("#page") for w in wo)
        rep["words_new"] += sum(not w.startswith("#page") for w in wn)
        if wo == wn:
            rep["alto_same"] += 1
        else:
            for a, b in chunks(wo, wn):
                rep["alto_chunks"] += 1
                if not explained(a, b, both):
                    rep["alto_unexplained"].append(dict(stem=stem, old=a[:200], new=b[:200]))
        want = C.alto_targets(oa) | C.alto_targets(na)
        bo, bn = C.jats_blocks(oj, want), C.jats_blocks(nj, want)
        same = True
        for k in set(bo) | set(bn):
            if bo.get(k) == bn.get(k):
                continue
            same = False
            o, n = (bo.get(k) or ("", ""))[1], (bn.get(k) or ("", ""))[1]
            for a, b in chunks(o.split(), n.split()):
                rep["block_chunks"] += 1
                if not explained(a, b, both):
                    rep["blocks_unexplained"].append(dict(stem=stem, block=k, old=a[:200], new=b[:200]))
        rep["blocks_same"] += same
        ms, notes, fixes = flags(nj)
        rep["flags_model_suggestion"] += len(ms)
        rep["notes_model_suggestion"] += len(notes)
        msc, nts, fx = Counter(ms), Counter(notes), Counter(fixes)
        for r in refs:
            rep["refused66"] += 1
            if msc[(r["frm"], r["to"])] > 0:
                msc[(r["frm"], r["to"])] -= 1
                rep["flag_found"] += 1
            else:
                rep["flag_missing_inline"].append(dict(stem=stem, line=r["line"], frm=r["frm"], to=r["to"]))
            if nts[(r["frm"], r["to"], r["line"])] > 0:
                rep["note_found"] += 1
            else:
                rep["note_missing"].append(dict(stem=stem, line=r["line"], frm=r["frm"], to=r["to"]))
            if fx[(r["frm"], r["to"], r["line"])] > 0:
                rep["still_fixed"].append(dict(stem=stem, line=r["line"], frm=r["frm"], to=r["to"]))
        for r in G.get(stem, []):
            rep["guard_log_refused"] += 1
            if fx[(r["frm"], r["to"], r["line"])] > 0:
                rep["guard_still_fixed"].append(dict(stem=stem, **r))
            if nts[(r["frm"], r["to"], r["line"])] == 0:
                rep["guard_note_missing"].append(dict(stem=stem, **r))
        sim = {(r["line"], r["frm"], r["to"]) for r in refs}
        live = {(r["line"], r["frm"], r["to"]) for r in G.get(stem, [])}
        rep["sim_not_live"] += [dict(stem=stem, line=a, frm=b, to=c) for a, b, c in sorted(sim - live)]
        rep["live_not_sim"] += [dict(stem=stem, line=a, frm=b, to=c) for a, b, c in sorted(live - sim)]
    return rep


def main():
    runs = sys.argv[1:] or list(RUNS)
    R = refused66()
    out = {}
    for run in runs:
        r = one(run, R)
        out[run] = r
        print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in r.items()}, ensure_ascii=False))
    (HERE / "out").mkdir(exist_ok=True)
    (HERE / "out" / "compare68.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
