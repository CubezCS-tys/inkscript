"""Experiment 60: answers -> today's rules43 (+ the letter fix, as production since 2026-10-22) -> enrich43 ->
masters43 (JATS DTD + ALTO XSD checked), with experiment 43's own code, into this experiment's out/.

    build60.py --run t1 --set c --argon-raw ../43_rehearsal/out/v33_300b_fix3/raw --plan out/plan_t1.json
        out/t1/hybrid_raw   per article: Claude's answer for every chunk it gave, Argon's for the rest (a master
                            needs every chunk; only Claude's pages are scored)
        out/t1/build        rules/ masters/ letters.json  (Claude)
        out/t1/argon_build  the same articles, every chunk Argon's, through the same code today (the fair twin)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

import common60 as K
from common60 import OUT, jl

sys.path.insert(0, str(K.E43))


def link_raw(run, argon_raw: Path, stems, arts, ST) -> tuple[Path, dict]:
    dst = OUT / run / "hybrid_raw"
    dst.mkdir(parents=True, exist_ok=True)
    src = OUT / run / "raw"
    who = {}
    for s in stems:
        for x, y in ST.chunks(arts[s]):
            n = f"{s}_c{x:03d}-{y:03d}.json"
            f = src / n if (src / n).exists() else argon_raw / n
            who[n] = "claude" if f.parent == src else "argon"
            t = dst / n
            if t.exists() or t.is_symlink():
                t.unlink()
            os.symlink(os.path.relpath(f.resolve(), dst), t)
    K.jdump(OUT / run / "hybrid_who.json", who)
    return dst, who


def build(raw: Path, dst: Path, stems, arts):
    """pictures43.build with this experiment's paths (and lettersfix43's letter fix + lean memory)."""
    import lettersfix43 as LF
    import masters43 as M43
    import replay43 as RP
    from masters43 import ST
    from inkscript.enrich.schemas import validate_alto, validate_jats
    LF.LOG["letters"].clear()
    LF.LOG["letters_foreign"].clear()
    rules = dst / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    bad = []
    for s in stems:
        a = arts[s]
        fs = [raw / f"{s}_c{x:03d}-{y:03d}.json" for x, y in ST.chunks(a)]
        if not all(f.exists() for f in fs):
            print(f"  {s}: chunk missing, skipped", flush=True)
            continue
        for f in fs:
            rec = ST.jl(f)
            ans, log = RP.apply_rules(a, rec)
            RP.jdump(rules / f.name, dict(rec, answer=ans, rules43=log))
        r = M43.build43(a, rules, dst / "masters", True, run=dst.parent.name)
        j = validate_jats(dst / "masters" / f"{s}.jats.xml")
        al = validate_alto(dst / "masters" / f"{s}.alto.xml")
        if j or al or r.get("error"):
            bad.append(dict(stem=s, error=r.get("error"), jats=j[:3], alto=al[:3]))
        print(f"  {s:24} {'ERROR ' + r['error'] if r.get('error') else 'ok'}{' INVALID' if j or al else ''}",
              flush=True)
    c = Counter(k for e in LF.LOG["letters"] if e["placed"] for k in e["kinds"])
    (dst / "letters.json").write_text(json.dumps(dict(kinds=dict(c), words=len(LF.LOG["letters"])),
                                                 ensure_ascii=False), encoding="utf-8")
    K.jdump(dst / "validity.json", dict(articles=len(stems), invalid=bad))
    print(f"invalid: {bad}" if bad else "all JATS DTD + ALTO XSD valid", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--set", default="c")
    ap.add_argument("--argon-raw", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--which", choices=["claude", "argon", "both"], default="both")
    ap.add_argument("--stems", nargs="*")
    args = ap.parse_args()
    K.pipeline()
    import lettersfix43 as LF
    LF.lean()
    LF.install()
    import masters43 as M43
    M43.ST.PAGES = K.E43 / "out" / "pages"
    arts = K.articles(args.set)
    stems = [s for s in jl(args.plan) if not args.stems or s in args.stems]
    argon_raw = Path(args.argon_raw).resolve()
    if args.which in ("claude", "both"):
        raw, who = link_raw(args.run, argon_raw, stems, arts, M43.ST)
        print(f"hybrid: {Counter(who.values())}", flush=True)
        build(raw, OUT / args.run / "build", stems, arts)
    if args.which in ("argon", "both"):
        build(argon_raw, OUT / args.run / "argon_build", stems, arts)


if __name__ == "__main__":
    main()
